<script setup lang="ts">
import { defineAsyncComponent, ref, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ApiRequestError } from '../../../api/errors'
import ServiceErrorState from '../../../shared/components/ServiceErrorState.vue'
import AnalysisWorkbench from '../../analysis/components/AnalysisWorkbench.vue'
import { getStock } from '../../stocks/api'
import type { StockDetail } from '../../stocks/types'
import { collectPrices, getPriceHistory } from '../api'
import type { PriceCollectionResult } from '../types'
import { toCandleChartData, formatDecimalPrice, type CandleChartData } from '../utils/chart-data'

const PriceCandleChart = defineAsyncComponent(() => import('../components/PriceCandleChart.vue'))
const route = useRoute()
const router = useRouter()
const DAY_OPTIONS = [30, 60, 90, 120, 260] as const

function isPresetDay(value: number): boolean {
  return DAY_OPTIONS.some((day) => day === value)
}

function validDays(raw: unknown): number {
  const value = Number(raw)
  return Number.isInteger(value) && value >= 1 && value <= 260 ? value : 90
}

const days = ref(validDays(route.query.days))
const collectDays = ref(90)
const stock = ref<StockDetail | null>(null)
const chart = ref<CandleChartData | null>(null)
const loading = ref(false)
const collecting = ref(false)
const loadError = ref<unknown>(null)
const collectError = ref<unknown>(null)
const uncertainCollection = ref(false)
const collectResult = ref<PriceCollectionResult | null>(null)
const refreshKey = ref(0)
let collectionRequestId = 0

watch(
  () => route.params.stockId,
  () => {
    // 切换股票时，旧采集请求可能仍在服务端执行，但旧页面的结果不能显示在新股票上。
    collectionRequestId += 1
    collecting.value = false
    collectError.value = null
    collectResult.value = null
    uncertainCollection.value = false
    collectDays.value = 90
  },
)

watch(
  () => [route.params.stockId, route.query.days, refreshKey.value] as const,
  (_newValue, _oldValue, onCleanup) => {
    const controller = new globalThis.AbortController()
    onCleanup(() => controller.abort())
    const stockId = Number(route.params.stockId)
    days.value = validDays(route.query.days)
    stock.value = null
    chart.value = null
    loadError.value = null
    if (!Number.isSafeInteger(stockId) || stockId < 1) {
      loadError.value = new ApiRequestError('股票编号必须是正整数', 422)
      loading.value = false
      return
    }
    loading.value = true
    void Promise.all([
      getStock(stockId, controller.signal),
      getPriceHistory(stockId, days.value, controller.signal),
    ])
      .then(([stockResult, priceResult]) => {
        if (controller.signal.aborted) return
        const converted = toCandleChartData(priceResult.items)
        stock.value = stockResult
        chart.value = converted
      })
      .catch((error: unknown) => {
        if (!controller.signal.aborted) loadError.value = error
      })
      .finally(() => {
        if (!controller.signal.aborted) loading.value = false
      })
  },
  { immediate: true },
)

function changeDays(value: number): void {
  void router.replace({ query: { ...route.query, days: value } })
}

function reload(): void {
  refreshKey.value += 1
}

async function collect(): Promise<void> {
  const stockId = Number(route.params.stockId)
  if (
    !stock.value ||
    stock.value.id !== stockId ||
    stock.value.status === 'archived' ||
    collecting.value
  )
    return
  if (
    !Number.isSafeInteger(collectDays.value) ||
    collectDays.value < 1 ||
    collectDays.value > 260
  ) {
    collectError.value = new ApiRequestError('采集条数必须为 1～260 的整数', 422)
    return
  }
  const requestId = ++collectionRequestId
  collecting.value = true
  collectError.value = null
  uncertainCollection.value = false
  collectResult.value = null
  try {
    const result = await collectPrices(stockId, collectDays.value)
    // 页面显示采集结果后，重新 GET 已保存行情；不能假装客户端已有新行情。
    if (collectionRequestId !== requestId || Number(route.params.stockId) !== stockId) return
    collectResult.value = result
    ElMessage.success('日线采集完成，正在刷新历史行情')
    reload()
  } catch (error: unknown) {
    if (collectionRequestId !== requestId || Number(route.params.stockId) !== stockId) return
    if (
      error instanceof ApiRequestError &&
      (error.kind === 'timeout' || error.kind === 'network')
    ) {
      collectError.value = error
      uncertainCollection.value = true
    } else {
      collectError.value = error
    }
  } finally {
    if (collectionRequestId === requestId) collecting.value = false
  }
}
</script>

<template>
  <section class="page-content">
    <div class="page-heading">
      <div>
        <div class="eyebrow">STOCK TREND LAB · DAILY PRICES</div>
        <h1>{{ stock ? `${stock.symbol} · ${stock.name}` : '股票详情与历史日线' }}</h1>
        <p class="muted">只展示已保存的日 K 数据；不是实时行情，也不构成投资建议。</p>
      </div>
      <RouterLink
        to="/stocks"
        class="secondary-action"
        >返回股票列表</RouterLink
      >
    </div>

    <ServiceErrorState
      v-if="loadError && !loading"
      :error="loadError"
      retry-label="重新加载详情与行情"
      @retry="reload"
    />
    <div
      v-else-if="loading"
      v-loading="true"
      class="panel section-card"
      style="min-height: 160px"
      aria-live="polite"
    >
      正在加载股票与历史行情…
    </div>
    <template v-else-if="stock && chart">
      <div class="stock-detail-meta panel section-card">
        <div>
          <span class="hint">股票代码</span><strong>{{ stock.symbol }}</strong>
        </div>
        <div>
          <span class="hint">市场</span
          ><strong>{{ stock.market === 'CN' ? '中国 A 股' : '美国股票' }}</strong>
        </div>
        <div>
          <span class="hint">追踪状态</span
          ><strong>{{ stock.status === 'archived' ? '已归档' : '正常追踪' }}</strong>
        </div>
        <div>
          <span class="hint">已返回日线</span><strong>{{ chart.rows.length }} 条</strong>
        </div>
      </div>

      <div class="panel section-card daily-price-panel">
        <div class="price-toolbar">
          <div>
            <h2>历史行情 · 日 K</h2>
            <p class="muted">按最近的完整交易日查询，支持缩放与成交量联动。</p>
          </div>
          <div class="price-actions">
            <label
              for="history-days"
              class="hint"
              >显示条数</label
            >
            <el-select
              id="history-days"
              :model-value="days"
              class="days-select"
              aria-label="查询最近多少条日线"
              @change="changeDays"
            >
              <el-option
                v-if="!isPresetDay(days)"
                :value="days"
                :label="`${days} 条`"
              />
              <el-option
                v-for="value in DAY_OPTIONS"
                :key="value"
                :value="value"
                :label="`${value} 条`"
              />
            </el-select>
            <el-button @click="reload">刷新行情</el-button>
          </div>
        </div>

        <template v-if="chart.dates.length">
          <div class="price-basis">
            <el-tag effect="plain">来源：{{ chart.source }}</el-tag>
            <el-tag effect="plain">复权：{{ chart.adjustment }}</el-tag>
            <el-tag effect="plain">币种：{{ chart.currency }}</el-tag>
            <span class="hint">最新交易日：{{ chart.dates[chart.dates.length - 1] }}</span>
          </div>
          <PriceCandleChart
            :data="chart"
            :market="stock.market"
          />
          <div class="last-candle hint">
            最新一条收盘价：{{
              formatDecimalPrice(chart.rows[chart.rows.length - 1]!.close_price, chart.currency)
            }}
            · 交易日期：{{ chart.dates[chart.dates.length - 1] }}
          </div>
        </template>
        <el-empty
          v-else
          description="暂无已保存的日线行情，可在下方采集历史日线"
        />
      </div>

      <div
        id="price-collect"
        class="panel section-card price-collect-panel"
      >
        <h2>采集历史日线</h2>
        <p class="muted">
          采集最近 1～260 条完整交易日日线，写入 MySQL。该操作会请求外部行情服务。
        </p>
        <div class="price-actions">
          <label
            for="collect-days"
            class="hint"
            >采集条数</label
          >
          <el-input-number
            id="collect-days"
            v-model="collectDays"
            :min="1"
            :max="260"
            :step="10"
            :disabled="stock.status === 'archived' || collecting"
            aria-label="采集多少条交易日日线"
          />
          <el-button
            type="primary"
            :loading="collecting"
            :disabled="stock.status === 'archived'"
            @click="collect"
            >采集日线</el-button
          >
        </div>
        <el-alert
          v-if="stock.status === 'archived'"
          title="已归档股票不可重新采集行情，但可查看已保存的历史数据。"
          type="warning"
          show-icon
          :closable="false"
          class="state-note"
        />
        <div
          v-if="collectResult"
          class="collect-result"
          role="status"
        >
          采集完成：新增 {{ collectResult.inserted }} 条、更新
          {{ collectResult.updated }} 条、未变化 {{ collectResult.unchanged }} 条。
        </div>
        <ServiceErrorState
          v-if="collectError"
          :error="collectError"
          :can-retry="false"
        />
        <el-alert
          v-if="uncertainCollection"
          class="state-note"
          type="warning"
          show-icon
          :closable="false"
          title="无法确认本次采集是否已完成：请先刷新已保存行情，不要立即再次提交采集。"
        />
        <el-button
          v-if="collectError"
          link
          type="primary"
          @click="reload"
          >先刷新已保存行情</el-button
        >
      </div>
      <AnalysisWorkbench
        :stock-id="stock.id"
        :archived="stock.status === 'archived'"
      />
    </template>
  </section>
</template>
