<script setup lang="ts">
import { ref, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ApiRequestError, describeRequestError } from '../../../api/errors'
import StockTable from '../components/StockTable.vue'
import { archiveStock, listStocks, restoreStock } from '../api'
import { buildStockListQuery, parseStockListQuery, PAGE_SIZES } from '../query'
import type { Market, Stock, StockStatus } from '../types'

const props = defineProps<{ status: StockStatus }>()
const route = useRoute()
const router = useRouter()

const items = ref<Stock[]>([])
const total = ref(0)
const loading = ref(false)
const errorMessage = ref('')
const busyId = ref<number | null>(null)
const refreshKey = ref(0)
const marketDraft = ref<Market | ''>('')
const keywordDraft = ref('')
const listState = ref(parseStockListQuery(route.query))

function errorText(error: unknown): string {
  if (error instanceof ApiRequestError) {
    if (error.httpStatus === 422) {
      return (
        error.issues?.map((issue) => `${issue.field}：${issue.message}`).join('；') || error.message
      )
    }
    const display = describeRequestError(error)
    return `${display.title}：${display.detail}`
  }
  return describeRequestError(error).detail
}

watch(
  () => [route.fullPath, props.status, refreshKey.value] as const,
  (_newValue, _oldValue, onCleanup) => {
    // URL、列表状态或刷新编号变化时重新读取一页数据。
    // Vue 会在下一次运行前调用 onCleanup，取消已过期的 HTTP 请求。
    const controller = new globalThis.AbortController()
    onCleanup(() => controller.abort())
    const query = parseStockListQuery(route.query)
    listState.value = query
    marketDraft.value = query.market
    keywordDraft.value = query.keyword
    errorMessage.value = ''
    loading.value = true
    // 清空上一组筛选结果，避免加载时短暂显示不属于当前条件的股票。
    items.value = []
    total.value = 0
    void listStocks(
      {
        status: props.status,
        page: query.page,
        page_size: query.pageSize,
        ...(query.market ? { market: query.market } : {}),
        ...(query.keyword ? { keyword: query.keyword } : {}),
      },
      controller.signal,
    )
      .then(async (data) => {
        if (controller.signal.aborted) return
        // 删除最后一条或用户输入超出范围的页码时，返回仍有记录的最后一页。
        const lastPage = Math.max(1, Math.ceil(data.total / query.pageSize))
        if (query.page > lastPage) {
          await router.replace({ query: buildStockListQuery({ ...query, page: lastPage }) })
          return
        }
        items.value = data.items
        total.value = data.total
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) return
        items.value = []
        total.value = 0
        errorMessage.value = errorText(error)
      })
      .finally(() => {
        if (!controller.signal.aborted) loading.value = false
      })
  },
  { immediate: true },
)

function applyFilters(): void {
  const query = {
    ...listState.value,
    page: 1,
    market: marketDraft.value,
    keyword: keywordDraft.value,
  }
  void router.push({ query: buildStockListQuery(query) })
}

function resetFilters(): void {
  marketDraft.value = ''
  keywordDraft.value = ''
  applyFilters()
}

function changePage(page: number): void {
  void router.push({ query: buildStockListQuery({ ...listState.value, page }) })
}

function changePageSize(pageSize: number): void {
  void router.push({ query: buildStockListQuery({ ...listState.value, page: 1, pageSize }) })
}

async function changeStatus(stock: Stock, target: StockStatus): Promise<void> {
  if (busyId.value !== null) return
  if (target === 'archived') {
    try {
      await ElMessageBox.confirm(
        `确认归档 ${stock.name}（${stock.symbol}）？历史数据不会删除。`,
        '确认归档',
        {
          confirmButtonText: '归档',
          cancelButtonText: '取消',
          type: 'warning',
        },
      )
    } catch {
      return
    }
  }
  busyId.value = stock.id
  try {
    if (target === 'archived') await archiveStock(stock.id)
    else await restoreStock(stock.id)
    ElMessage.success(target === 'archived' ? '股票已归档' : '股票已恢复追踪')
    refreshKey.value += 1
  } catch (error: unknown) {
    ElMessage.error(errorText(error))
  } finally {
    busyId.value = null
  }
}
</script>

<template>
  <section class="page-content">
    <div class="page-heading">
      <div>
        <div class="eyebrow">STOCK TREND LAB · STOCKS</div>
        <h1>{{ status === 'active' ? '我的股票' : '已归档股票' }}</h1>
        <p class="muted">
          {{
            status === 'active'
              ? '管理正在追踪的股票，点击股票代码查看历史日线与 K 线图。'
              : '查看历史归档记录，并恢复追踪。'
          }}
        </p>
      </div>
      <RouterLink
        v-if="status === 'active'"
        to="/stocks/add"
        class="primary-action"
        >+ 添加股票</RouterLink
      >
      <RouterLink
        v-else
        to="/stocks"
        class="secondary-action"
        >返回我的股票</RouterLink
      >
    </div>

    <div class="panel section-card">
      <form
        class="stock-filter"
        @submit.prevent="applyFilters"
      >
        <el-select
          v-model="marketDraft"
          placeholder="全部市场"
          aria-label="筛选市场"
          class="filter-market"
        >
          <el-option
            label="全部市场"
            value=""
          />
          <el-option
            label="中国 A 股"
            value="CN"
          />
          <el-option
            label="美国股票"
            value="US"
          />
        </el-select>
        <el-input
          v-model="keywordDraft"
          maxlength="50"
          clearable
          placeholder="按代码或名称筛选本地股票"
          aria-label="股票关键词"
          class="filter-keyword"
        />
        <el-button
          type="primary"
          native-type="submit"
          >查询</el-button
        >
        <el-button @click="resetFilters">重置</el-button>
      </form>

      <el-alert
        v-if="errorMessage"
        class="state-note"
        :title="errorMessage"
        type="error"
        show-icon
        :closable="false"
      >
        <template #default
          ><el-button
            link
            type="primary"
            @click="refreshKey += 1"
            >重新请求</el-button
          ></template
        >
      </el-alert>
      <div
        v-else-if="!loading && total === 0"
        class="empty-state"
      >
        <el-empty :description="status === 'active' ? '暂无符合条件的股票' : '没有归档记录'" />
        <RouterLink
          v-if="status === 'active'"
          to="/stocks/add"
          class="table-link"
          >搜索并添加股票</RouterLink
        >
      </div>
      <StockTable
        v-else
        :items="items"
        :loading="loading"
        :busy-id="busyId"
        :status="status"
        @archive="(stock) => changeStatus(stock, 'archived')"
        @restore="(stock) => changeStatus(stock, 'active')"
      />

      <div
        v-if="!errorMessage && total > 0"
        class="pagination-bar"
      >
        <span class="hint">共 {{ total }} 只股票</span>
        <el-pagination
          :current-page="listState.page"
          :page-size="listState.pageSize"
          :page-sizes="[...PAGE_SIZES]"
          :total="total"
          :disabled="loading"
          layout="sizes, prev, pager, next"
          background
          @current-change="changePage"
          @size-change="changePageSize"
        />
      </div>
    </div>
  </section>
</template>
