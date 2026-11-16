<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ApiRequestError } from '../../../api/errors'
import ServiceErrorState from '../../../shared/components/ServiceErrorState.vue'
import { listAnalysisRuns, submitAnalysisRun } from '../api'
import { formatAnalysisValue, formatComputedAt } from '../utils/analysis-chart-data'
import { isValidAnalysisDays } from '../utils/analysis-days'
import type { AnalysisRunListResponse, RunSubmitOutcome } from '../types'

const props = defineProps<{ stockId: number; archived: boolean }>()
const page = ref(1)
const pageSize = 10
const refreshVersion = ref(0)
const list = ref<AnalysisRunListResponse | null>(null)
const listLoading = ref(false)
const listError = ref<unknown>(null)
const runDays = ref(90)
const canRun = computed(() => isValidAnalysisDays(runDays.value))
const running = ref(false)
const runError = ref<unknown>(null)
const runUncertain = ref(false)
const outcome = ref<RunSubmitOutcome | null>(null)
let submitGeneration = 0

watch(
  () => props.stockId,
  () => {
    // 页面复用同一组件展示另一只股票时，清除上一只股票的分析结果。
    // 递增序号使尚未完成的旧 POST 无权再更新当前页面。
    submitGeneration += 1
    running.value = false
    page.value = 1
    runDays.value = 90
    runError.value = null
    runUncertain.value = false
    outcome.value = null
  },
)

onBeforeUnmount(() => {
  // POST 无法像只读 GET 一样安全地“取消服务端计算”，这里只阻止旧响应更新已离开的页面。
  submitGeneration += 1
})

watch(
  () => [props.stockId, page.value, refreshVersion.value] as const,
  ([stockId, pageNumber], _oldValue, onCleanup) => {
    const controller = new globalThis.AbortController()
    onCleanup(() => controller.abort())
    listLoading.value = true
    list.value = null
    listError.value = null
    void listAnalysisRuns(stockId, pageNumber, pageSize, controller.signal)
      .then((result) => {
        if (controller.signal.aborted) return
        const lastPage = Math.max(1, Math.ceil(result.total / pageSize))
        if (page.value > lastPage) {
          page.value = lastPage
          return
        }
        list.value = result
      })
      .catch((error: unknown) => {
        if (!controller.signal.aborted) {
          list.value = null
          listError.value = error
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) listLoading.value = false
      })
  },
  { immediate: true },
)

function reloadRuns(): void {
  refreshVersion.value += 1
}

async function runAnalysis(): Promise<void> {
  if (running.value || props.archived) return
  if (!canRun.value) {
    runError.value = new ApiRequestError('分析条数必须为 35～260 的整数', 422)
    return
  }

  const requestStockId = props.stockId
  const requestGeneration = ++submitGeneration
  running.value = true
  runError.value = null
  runUncertain.value = false
  outcome.value = null
  try {
    const result = await submitAnalysisRun(requestStockId, runDays.value)
    if (requestGeneration !== submitGeneration || requestStockId !== props.stockId) return
    outcome.value = result
    ElMessage.success(result.created ? '分析已保存为新批次' : '已更新符合条件的现有批次')
    page.value = 1
    reloadRuns()
  } catch (error: unknown) {
    if (requestGeneration !== submitGeneration || requestStockId !== props.stockId) return
    runError.value = error
    // POST 可能已经在服务端保存。网络错误与超时后，由用户先查询批次再决定是否重试。
    runUncertain.value =
      error instanceof ApiRequestError && (error.kind === 'network' || error.kind === 'timeout')
  } finally {
    if (requestGeneration === submitGeneration) running.value = false
  }
}
</script>

<template>
  <section
    class="panel section-card analysis-workbench"
    aria-label="趋势分析工作区"
  >
    <div class="price-toolbar">
      <div>
        <h2>趋势分析 · v1</h2>
        <p class="muted">
          使用数据库中已保存的完整日线计算。分析条数与上面的 K 线显示条数互不影响。
        </p>
      </div>
      <div class="price-actions">
        <label
          class="hint"
          for="analysis-days"
          >分析条数</label
        >
        <el-input-number
          id="analysis-days"
          v-model="runDays"
          :min="35"
          :max="260"
          :step="5"
          :disabled="props.archived || running"
          aria-label="分析最近多少条已保存日线"
        />
        <el-button
          type="primary"
          :loading="running"
          :disabled="props.archived || running || !canRun"
          @click="runAnalysis"
          >运行分析</el-button
        >
        <span
          v-if="!canRun && !props.archived"
          class="hint"
          role="alert"
          >请填写 35～260 的整数</span
        >
      </div>
    </div>

    <el-alert
      v-if="props.archived"
      class="state-note"
      type="warning"
      title="该股票已归档：可以查看历史分析，但不能发起新分析。"
      show-icon
      :closable="false"
    />
    <el-alert
      v-if="runUncertain"
      class="state-note"
      type="warning"
      title="分析请求结果尚未确认：请先刷新下方的历史批次，避免重复提交。"
      show-icon
      :closable="false"
    />
    <ServiceErrorState
      v-if="runError"
      :error="runError"
      :can-retry="false"
    />
    <a
      v-if="runError instanceof ApiRequestError && runError.errorCode === 'INSUFFICIENT_HISTORY'"
      class="table-link"
      href="#price-collect"
      >返回上方采集更多日线</a
    >

    <div
      v-if="outcome"
      class="analysis-run-result"
      role="status"
    >
      <div class="analysis-score-card">
        <span class="hint"
          >{{ outcome.created ? '新建分析批次' : '已重算现有批次' }} #{{
            outcome.data.run_id
          }}</span
        >
        <strong class="analysis-score">{{ outcome.data.latest.trend_score }} / 100</strong>
        <span>{{ outcome.data.latest.trend_label }}</span>
      </div>
      <div class="analysis-result-body">
        <div class="hint">
          计算范围：{{ outcome.data.start_date }} 至 {{ outcome.data.end_date }} ·
          {{ outcome.data.requested_days }} 条 · {{ outcome.data.rule_version }}
        </div>
        <p>{{ outcome.data.latest.summary }}</p>
        <div class="hint">
          MA5：{{ formatAnalysisValue(outcome.data.latest.ma5) }} · MA20：{{
            formatAnalysisValue(outcome.data.latest.ma20)
          }}
          · RSI14：{{ formatAnalysisValue(outcome.data.latest.rsi14) }} · MACD：{{
            formatAnalysisValue(outcome.data.latest.macd)
          }}
        </div>
        <RouterLink
          class="primary-action"
          :to="`/stocks/${props.stockId}/analysis/${outcome.data.run_id}`"
          >查看逐日分析快照</RouterLink
        >
      </div>
    </div>

    <div class="analysis-history-header">
      <div>
        <h2>已保存的分析批次</h2>
        <p class="muted">按计算时间排序。重复同条件分析可能更新既有批次，编号不一定新增。</p>
      </div>
      <el-button
        :disabled="listLoading"
        @click="reloadRuns"
        >刷新批次</el-button
      >
    </div>
    <ServiceErrorState
      v-if="listError"
      :error="listError"
      retry-label="重新读取历史批次"
      @retry="reloadRuns"
    />
    <div
      v-else
      v-loading="listLoading"
      style="min-height: 80px"
    >
      <el-empty
        v-if="!listLoading && list && list.total === 0"
        description="暂时没有保存的分析批次，可运行一次趋势分析"
      />
      <el-table
        v-else-if="list && list.items.length"
        :data="list.items"
        class="stock-table"
        style="width: 100%"
      >
        <el-table-column
          prop="run_id"
          label="批次"
          min-width="80"
        />
        <el-table-column
          prop="requested_days"
          label="条数"
          min-width="75"
        />
        <el-table-column
          prop="end_date"
          label="结束日"
          min-width="125"
        />
        <el-table-column
          prop="rule_version"
          label="规则"
          min-width="80"
        />
        <el-table-column
          label="计算时间"
          min-width="190"
        >
          <template #default="scope">{{ formatComputedAt(scope.row.computed_at) }}</template>
        </el-table-column>
        <el-table-column
          label="操作"
          min-width="90"
          fixed="right"
        >
          <template #default="scope">
            <RouterLink
              class="table-link"
              :to="`/stocks/${props.stockId}/analysis/${scope.row.run_id}`"
              >查看</RouterLink
            >
          </template>
        </el-table-column>
      </el-table>
      <div
        v-if="list && list.total > pageSize"
        class="pagination-bar"
      >
        <span class="hint">共 {{ list.total }} 个批次</span>
        <el-pagination
          :current-page="page"
          :page-size="pageSize"
          :total="list.total"
          layout="prev, pager, next"
          background
          @current-change="(value: number) => (page = value)"
        />
      </div>
    </div>
  </section>
</template>
