<script setup lang="ts">
import { ref, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ApiRequestError } from '../../../api/errors'
import { addStock, searchStocks } from '../api'
import type { Market, StockCandidate } from '../types'

const router = useRouter()
const route = useRoute()
const initialMarket = route.query.market === 'CN' ? 'CN' : 'US'
const market = ref<Market>(initialMarket)
const searchText = ref(typeof route.query.q === 'string' ? route.query.q.slice(0, 50) : '')
const items = ref<StockCandidate[]>([])
const searching = ref(false)
const searched = ref(false)
const searchError = ref('')
const creatingSymbol = ref('')
const createError = ref('')
const duplicate = ref<{ market: Market; symbol: string } | null>(null)
// 每次搜索得到新的编号；晚到的旧响应不会覆盖当前页面。
let searchId = 0

watch([market, searchText], () => {
  // 市场/关键词变更后，旧搜索结果不能继续用于登记。
  searchId += 1
  searching.value = false
  items.value = []
  searchError.value = ''
  searched.value = false
  duplicate.value = null
})

async function performSearch(): Promise<void> {
  // 只在提交表单时请求外部目录。输入框变化本身不发送网络请求。
  const query = searchText.value.trim()
  if (!query) {
    searchError.value = '请先输入股票代码或名称'
    return
  }
  if (query.length > 50) {
    searchError.value = '搜索内容不能超过 50 个字符'
    return
  }
  const requestId = ++searchId
  searching.value = true
  searchError.value = ''
  items.value = []
  searched.value = false
  await router.replace({ query: { market: market.value, q: query } })
  try {
    const candidates = await searchStocks(market.value, query)
    // 用户可能已经切换市场或修改关键词，此时丢弃旧搜索结果。
    if (requestId === searchId) {
      items.value = candidates
      searched.value = true
    }
  } catch (error: unknown) {
    if (requestId !== searchId) return
    searchError.value =
      error instanceof ApiRequestError
        ? error.errorCode === 'STOCK_CATALOG_UNAVAILABLE'
          ? '股票目录服务暂不可用，请稍后重试'
          : error.message
        : '搜索失败，请稍后重试'
  } finally {
    if (requestId === searchId) searching.value = false
  }
}

async function register(candidate: StockCandidate): Promise<void> {
  // 后端会按市场和代码再次核对目录；前端候选项的名称不作为保存依据。
  if (creatingSymbol.value) return
  creatingSymbol.value = candidate.symbol
  createError.value = ''
  duplicate.value = null
  try {
    await addStock({ market: candidate.market, symbol: candidate.symbol })
    ElMessage.success(`已添加 ${candidate.symbol}`)
    await router.push({
      path: '/stocks',
      query: { market: candidate.market, keyword: candidate.symbol },
    })
  } catch (error: unknown) {
    if (error instanceof ApiRequestError && error.errorCode === 'STOCK_ALREADY_EXISTS') {
      createError.value = '该股票已登记，可能在正常追踪列表或已归档列表中。'
      duplicate.value = { market: candidate.market, symbol: candidate.symbol }
    } else if (error instanceof ApiRequestError) {
      createError.value =
        error.issues?.map((issue) => `${issue.field}：${issue.message}`).join('；') || error.message
    } else {
      createError.value = '添加失败，请重试'
    }
  } finally {
    creatingSymbol.value = ''
  }
}
</script>

<template>
  <section class="page-content">
    <div class="page-heading">
      <div>
        <div class="eyebrow">STOCK TREND LAB · DISCOVER</div>
        <h1>添加股票</h1>
        <p class="muted">先从股票目录搜索候选项，选择后再加入本地追踪列表。</p>
      </div>
      <RouterLink
        to="/stocks"
        class="secondary-action"
        >返回我的股票</RouterLink
      >
    </div>
    <div class="panel section-card">
      <form
        class="stock-filter"
        @submit.prevent="performSearch"
      >
        <el-select
          v-model="market"
          aria-label="搜索市场"
          class="filter-market"
        >
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
          v-model="searchText"
          maxlength="50"
          clearable
          class="filter-keyword"
          aria-label="搜索代码或名称"
          placeholder="例如 AAPL、600519、苹果"
        />
        <el-button
          type="primary"
          native-type="submit"
          :loading="searching"
          >搜索</el-button
        >
      </form>
      <p class="hint">搜索按回车或点击按钮触发，不会每次输入都请求第三方数据源。</p>

      <el-alert
        v-if="searchError"
        class="state-note"
        type="error"
        show-icon
        :closable="false"
        :title="searchError"
      />
      <el-alert
        v-if="createError"
        class="state-note"
        type="warning"
        show-icon
        :closable="false"
        :title="createError"
      >
        <template #default>
          <div
            v-if="duplicate"
            class="alert-actions"
          >
            <RouterLink
              :to="{
                path: '/stocks',
                query: { market: duplicate.market, keyword: duplicate.symbol },
              }"
              class="table-link"
              >查看正常列表</RouterLink
            >
            <RouterLink
              :to="{
                path: '/stocks/archived',
                query: { market: duplicate.market, keyword: duplicate.symbol },
              }"
              class="table-link"
              >查看归档列表</RouterLink
            >
          </div>
        </template>
      </el-alert>

      <el-table
        v-if="items.length > 0"
        v-loading="searching"
        :data="items"
        class="stock-table"
        row-key="symbol"
      >
        <el-table-column
          label="股票代码"
          prop="symbol"
          min-width="140"
        />
        <el-table-column
          label="股票名称"
          prop="name"
          min-width="170"
          show-overflow-tooltip
        />
        <el-table-column
          label="交易所"
          prop="exchange"
          min-width="130"
        />
        <el-table-column
          label="操作"
          width="128"
          align="right"
        >
          <template #default="{ row }">
            <el-button
              link
              type="primary"
              :loading="creatingSymbol === row.symbol"
              :disabled="Boolean(creatingSymbol)"
              @click="register(row)"
              >添加追踪</el-button
            >
          </template>
        </el-table-column>
      </el-table>
      <el-empty
        v-else-if="searched && !searchError"
        description="没有找到符合条件的股票"
      />
      <el-empty
        v-else-if="!searching && !searchError"
        description="请选择市场并输入股票代码或名称"
      />
    </div>
  </section>
</template>
