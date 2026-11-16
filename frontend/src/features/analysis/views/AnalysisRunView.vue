<script setup lang="ts">
import { computed, defineAsyncComponent, ref, watch } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import { ApiRequestError } from '../../../api/errors'
import ServiceErrorState from '../../../shared/components/ServiceErrorState.vue'
import { getAnalysisRun } from '../api'
import type { AnalysisRunDetailResponse } from '../types'
import {
  formatAnalysisValue,
  formatComputedAt,
  pageAnalysisRows,
  toAnalysisChartData,
  type AnalysisChartData,
} from '../utils/analysis-chart-data'

const AnalysisIndicatorsChart = defineAsyncComponent(
  () => import('../components/AnalysisIndicatorsChart.vue'),
)
const route = useRoute()
const detail = ref<AnalysisRunDetailResponse | null>(null)
const chart = ref<AnalysisChartData | null>(null)
const loading = ref(false)
const loadError = ref<unknown>(null)
const refreshVersion = ref(0)
const rowsPage = ref(1)
const pageSize = 20
const latest = computed(() => chart.value?.rows.at(-1))
const shownRows = computed(() => {
  return pageAnalysisRows(chart.value?.rows ?? [], rowsPage.value, pageSize)
})

watch(
  () => [route.params.stockId, route.params.runId, refreshVersion.value] as const,
  (_params, _oldValue, onCleanup) => {
    const controller = new globalThis.AbortController()
    onCleanup(() => controller.abort())
    detail.value = null
    chart.value = null
    loadError.value = null
    rowsPage.value = 1

    const stockId = Number(route.params.stockId)
    const runId = Number(route.params.runId)
    if (![stockId, runId].every((id) => Number.isSafeInteger(id) && id > 0)) {
      loadError.value = new ApiRequestError('股票或批次编号必须为正整数', 422)
      loading.value = false
      return
    }

    loading.value = true
    // URL 编号或刷新动作变化时，取消前一个 GET；返回时再检查 signal，防止旧数据串页。
    void getAnalysisRun(stockId, runId, controller.signal)
      .then((response) => {
        if (controller.signal.aborted) return
        const converted = toAnalysisChartData(response)
        detail.value = response
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

function reload(): void {
  refreshVersion.value += 1
}
</script>

<template>
  <section class="page-content">
    <div class="page-heading">
      <div>
        <div class="eyebrow">STOCK TREND LAB · SAVED ANALYSIS</div>
        <h1>{{ detail ? `${detail.symbol} · 分析批次 #${detail.run_id}` : '已保存分析快照' }}</h1>
        <p class="muted">展示后端保存的历史分析结果；读取不会重新采集行情或重新计算。</p>
      </div>
      <RouterLink
        :to="`/stocks/${route.params.stockId}`"
        class="secondary-action"
        >返回股票详情</RouterLink
      >
    </div>

    <ServiceErrorState
      v-if="loadError && !loading"
      :error="loadError"
      retry-label="重新读取分析批次"
      @retry="reload"
    />
    <div
      v-else-if="loading"
      v-loading="true"
      class="panel section-card"
      style="min-height: 180px"
    >
      正在加载历史快照…
    </div>
    <template v-else-if="detail && chart">
      <div class="panel section-card analysis-meta">
        <div>
          <span class="hint">规则版本</span><strong>{{ detail.rule_version }}</strong>
        </div>
        <div>
          <span class="hint">输入范围</span>
          <strong
            >{{ detail.requested_days }} 条（{{ detail.start_date }} ～
            {{ detail.end_date }}）</strong
          >
        </div>
        <div>
          <span class="hint">来源 / 复权</span>
          <strong>{{ detail.source }} / {{ detail.adjustment }}</strong>
        </div>
        <div>
          <span class="hint">计算时间（本地）</span>
          <strong>{{ formatComputedAt(detail.computed_at) }}</strong>
        </div>
      </div>

      <div
        v-if="latest"
        class="panel section-card analysis-latest-panel"
      >
        <div class="analysis-score-card">
          <span class="hint">最新交易日 {{ latest.trade_date }}</span>
          <strong class="analysis-score"
            >{{ latest.trend_score ?? '—' }}<small> / 100</small></strong
          >
          <span>{{ latest.trend_label ?? '尚未形成完整评分' }}</span>
        </div>
        <div class="analysis-result-body">
          <h2>趋势评分与规则说明</h2>
          <p>{{ latest.summary ?? '当前交易日指标尚未满足评分条件。' }}</p>
          <div class="analysis-metric-chips">
            <span>收盘 {{ formatAnalysisValue(latest.close_price) }}</span>
            <span>MA5 {{ formatAnalysisValue(latest.ma5) }}</span>
            <span>MA20 {{ formatAnalysisValue(latest.ma20) }}</span>
            <span>RSI14 {{ formatAnalysisValue(latest.rsi14) }}</span>
            <span>MACD {{ formatAnalysisValue(latest.macd) }}</span>
          </div>
        </div>
      </div>

      <div class="panel section-card daily-price-panel">
        <h2>逐日技术指标</h2>
        <p class="muted">
          收盘价与 MA5/MA20、RSI14、MACD（DIF − DEA）分别展示；三张图共用交易日缩放。前 34
          条中尚未形成的指标保留空值。
        </p>
        <AnalysisIndicatorsChart :data="chart" />
      </div>

      <div class="panel section-card">
        <h2>逐日结果明细</h2>
        <p class="muted">
          原始分析结果最多 260 条。表格按交易日期从新到旧展示；“—”表示后端返回 null。
        </p>
        <el-table
          :data="shownRows"
          class="stock-table analysis-detail-table"
          style="width: 100%"
        >
          <el-table-column
            prop="trade_date"
            label="交易日期"
            width="122"
            fixed="left"
          />
          <el-table-column
            label="收盘价"
            min-width="110"
          >
            <template #default="scope">{{
              formatAnalysisValue(scope.row.close_price, 6)
            }}</template>
          </el-table-column>
          <el-table-column
            label="MA5"
            min-width="105"
          >
            <template #default="scope">{{ formatAnalysisValue(scope.row.ma5, 6) }}</template>
          </el-table-column>
          <el-table-column
            label="MA20"
            min-width="105"
          >
            <template #default="scope">{{ formatAnalysisValue(scope.row.ma20, 6) }}</template>
          </el-table-column>
          <el-table-column
            label="RSI14"
            min-width="90"
          >
            <template #default="scope">{{ formatAnalysisValue(scope.row.rsi14) }}</template>
          </el-table-column>
          <el-table-column
            label="MACD"
            min-width="110"
          >
            <template #default="scope">{{ formatAnalysisValue(scope.row.macd, 6) }}</template>
          </el-table-column>
          <el-table-column
            label="评分"
            min-width="80"
          >
            <template #default="scope">{{ scope.row.trend_score ?? '—' }}</template>
          </el-table-column>
          <el-table-column
            label="趋势"
            min-width="110"
          >
            <template #default="scope">{{ scope.row.trend_label ?? '—' }}</template>
          </el-table-column>
        </el-table>
        <div
          v-if="chart.rows.length > pageSize"
          class="pagination-bar"
        >
          <span class="hint">共 {{ chart.rows.length }} 条逐日记录</span>
          <el-pagination
            :current-page="rowsPage"
            :page-size="pageSize"
            :total="chart.rows.length"
            layout="prev, pager, next"
            background
            @current-change="(value: number) => (rowsPage = value)"
          />
        </div>
      </div>
      <p class="hint">
        历史快照仅描述已发生的价格变化，不是股价预测，也不构成投资建议。同条件重算可能更新原批次的内容及时间。
      </p>
    </template>
  </section>
</template>
