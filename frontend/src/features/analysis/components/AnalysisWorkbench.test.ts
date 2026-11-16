import {
  ElAlert,
  ElButton,
  ElEmpty,
  ElInputNumber,
  ElLoading,
  ElPagination,
  ElTable,
  ElTableColumn,
} from 'element-plus'
import { createSSRApp } from 'vue'
import { renderToString } from 'vue/server-renderer'
import { describe, expect, it, vi } from 'vitest'
import { listAnalysisRuns, submitAnalysisRun } from '../api'
import AnalysisWorkbench from './AnalysisWorkbench.vue'

vi.mock('../api', () => ({
  listAnalysisRuns: vi.fn().mockResolvedValue({
    stock_id: 10,
    symbol: '600941.SH',
    market: 'CN',
    items: [],
    total: 0,
    page: 1,
    page_size: 10,
  }),
  submitAnalysisRun: vi.fn(),
}))

async function renderWorkbench(archived: boolean): Promise<string> {
  const app = createSSRApp(AnalysisWorkbench, { stockId: 10, archived })
  // 使用真实 Element Plus 按钮，核对归档时最终输出的 disabled 属性。
  app.component('ElAlert', ElAlert)
  app.component('ElButton', ElButton)
  app.component('ElInputNumber', ElInputNumber)
  app.component('ElEmpty', ElEmpty)
  app.component('ElPagination', ElPagination)
  app.component('ElTable', ElTable)
  app.component('ElTableColumn', ElTableColumn)
  app.use(ElLoading)
  return renderToString(app)
}

describe('S3 趋势分析工作台', () => {
  it('归档股票仍查询历史批次，但分析按钮禁用', async () => {
    const html = await renderWorkbench(true)
    expect(vi.mocked(listAnalysisRuns)).toHaveBeenCalledWith(10, 1, 10, expect.any(AbortSignal))
    expect(html).toContain('该股票已归档')
    expect(html).toMatch(/<button[^>]*disabled[^>]*>.*运行分析/s)
    expect(submitAnalysisRun).not.toHaveBeenCalled()
  })

  it('正常追踪的股票展示单独的分析条数输入', async () => {
    const html = await renderWorkbench(false)
    expect(html).toContain('分析条数')
    expect(html).toContain('运行分析')
    expect(html).not.toContain('该股票已归档')
  })
})
