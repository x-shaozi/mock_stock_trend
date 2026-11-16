<script setup lang="ts">
import { computed } from 'vue'
import { describeRequestError } from '../../api/errors'

const props = withDefaults(
  defineProps<{
    error: unknown
    retryLabel?: string
    busy?: boolean
    canRetry?: boolean
  }>(),
  // Vue 会把省略的布尔属性视为 false；GET 错误页需要默认显示重试按钮。
  { retryLabel: '', busy: false, canRetry: true },
)
const emit = defineEmits<{ retry: [] }>()
const display = computed(() => describeRequestError(props.error))
</script>

<template>
  <section
    class="service-error"
    role="alert"
    aria-live="polite"
  >
    <div class="service-error-title">{{ display.title }}</div>
    <p class="muted">{{ display.detail }}</p>
    <el-button
      v-if="canRetry && display.retryable"
      type="primary"
      :loading="busy"
      @click="emit('retry')"
      >{{ retryLabel || '重新连接' }}</el-button
    >
  </section>
</template>
