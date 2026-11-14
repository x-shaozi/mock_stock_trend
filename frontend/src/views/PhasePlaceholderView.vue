<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ApiRequestError } from '../api/errors'
import { getHealth } from '../api/health'

defineProps<{ title: string; description: string }>()

const health = ref<'checking' | 'online' | 'offline'>('checking')
const healthNote = ref('正在检查 FastAPI HTTP 服务…')

onMounted(async () => {
  try {
    const result = await getHealth()
    health.value = result.status === 'ok' ? 'online' : 'offline'
    healthNote.value =
      result.status === 'ok'
        ? 'FastAPI HTTP 进程可访问（不代表 MySQL 连接已验证）'
        : '健康检查未返回预期状态'
  } catch (error: unknown) {
    health.value = 'offline'
    healthNote.value = error instanceof ApiRequestError ? error.message : '健康检查失败'
  }
})
</script>

<template>
  <section class="page-content">
    <div class="page-heading">
      <div>
        <div class="eyebrow">STOCK TREND LAB · FRONTEND S0</div>
        <h1>{{ title }}</h1>
        <p class="muted">{{ description }}</p>
      </div>
      <el-tag type="info" effect="plain">工程骨架</el-tag>
    </div>
    <div class="panel section-card">
      <h2>前后端连接检查</h2>
      <p class="muted">
        当前 S0 只验证前端工程、主题切换和 FastAPI 健康接口。后续阶段才实现股票业务。
      </p>
      <div class="status-row">
        <el-tag
          :type="health === 'online' ? 'success' : health === 'offline' ? 'danger' : 'warning'"
        >
          {{
            health === 'online' ? 'HTTP 已连通' : health === 'offline' ? 'HTTP 未连通' : '检查中'
          }}
        </el-tag>
        <span>{{ healthNote }}</span>
      </div>
      <p class="hint">
        API: <code>/api/health</code> → Vite 代理 → FastAPI <code>127.0.0.1:18000/health</code>
      </p>
    </div>
  </section>
</template>
