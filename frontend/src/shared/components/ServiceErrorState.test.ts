import { ElButton } from 'element-plus'
import { createSSRApp } from 'vue'
import { renderToString } from 'vue/server-renderer'
import { describe, expect, it } from 'vitest'
import { ApiRequestError } from '../../api/errors'
import ServiceErrorState from './ServiceErrorState.vue'

// 在 Node 中真实渲染组件，核对用户能否看到按钮；不访问浏览器或后端。
async function renderError(canRetry?: boolean): Promise<string> {
  const app = createSSRApp(ServiceErrorState, {
    error: new ApiRequestError('服务器内部错误', 500),
    retryLabel: '重新加载详情与行情',
    ...(canRetry === undefined ? {} : { canRetry }),
  })
  app.component('ElButton', ElButton)
  return renderToString(app)
}

describe('错误页面的重试按钮', () => {
  it('GET 页面不传 canRetry 时仍显示按钮', async () => {
    expect(await renderError()).toContain('重新加载详情与行情')
  })

  it('采集 POST 明确禁用重试时不显示按钮', async () => {
    expect(await renderError(false)).not.toContain('重新加载详情与行情')
  })
})
