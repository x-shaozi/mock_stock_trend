<script setup lang="ts">
import { RouterLink } from 'vue-router'
import type { Stock, StockStatus } from '../types'

defineProps<{
  items: Stock[]
  loading: boolean
  busyId: number | null
  status: StockStatus
}>()

const emit = defineEmits<{
  archive: [stock: Stock]
  restore: [stock: Stock]
}>()
</script>

<template>
  <el-table
    v-loading="loading"
    :data="items"
    row-key="id"
    class="stock-table"
  >
    <el-table-column
      label="股票代码"
      min-width="160"
    >
      <template #default="{ row }">
        <RouterLink
          class="table-link"
          :to="`/stocks/${row.id}`"
          >{{ row.symbol }}</RouterLink
        >
      </template>
    </el-table-column>
    <el-table-column
      prop="name"
      label="股票名称"
      min-width="190"
      show-overflow-tooltip
    />
    <el-table-column
      label="市场"
      width="100"
    >
      <template #default="{ row }">
        <el-tag
          size="small"
          effect="plain"
          >{{ row.market === 'CN' ? 'A 股' : '美股' }}</el-tag
        >
      </template>
    </el-table-column>
    <el-table-column
      label="操作"
      width="180"
      align="right"
    >
      <template #default="{ row }">
        <el-button
          v-if="status === 'active'"
          link
          type="primary"
          :disabled="busyId !== null"
          @click="emit('archive', row)"
        >
          {{ busyId === row.id ? '处理中…' : '归档' }}
        </el-button>
        <el-button
          v-else
          link
          type="primary"
          :disabled="busyId !== null"
          @click="emit('restore', row)"
        >
          {{ busyId === row.id ? '处理中…' : '恢复追踪' }}
        </el-button>
      </template>
    </el-table-column>
  </el-table>
</template>
