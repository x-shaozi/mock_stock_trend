import { beforeEach, describe, expect, it, vi } from 'vitest'
import { http } from '../../api/http'
import { getAnalysisRun, listAnalysisRuns, submitAnalysisRun } from './api'

vi.mock('../../api/http', () => ({
  http: { get: vi.fn(), post: vi.fn() },
}))

const getMock = vi.mocked(http.get)
const postMock = vi.mocked(http.post)

beforeEach(() => vi.clearAllMocks())

describe('S3 分析 API 契约', () => {
  it('POST 将分析天数放进 JSON 请求体，按 201/200 区分新建与重算', async () => {
    postMock.mockResolvedValueOnce({ status: 201, data: { run_id: 8 } })
    const created = await submitAnalysisRun(5, 90)
    expect(created.created).toBe(true)
    expect(postMock).toHaveBeenCalledWith(
      '/stocks/5/analysis-runs',
      { days: 90 },
      { timeout: 45_000 },
    )

    postMock.mockResolvedValueOnce({ status: 200, data: { run_id: 8 } })
    const updated = await submitAnalysisRun(5, 90)
    expect(updated.created).toBe(false)
    expect(updated.data.run_id).toBe(created.data.run_id)
  })

  it('POST 超时不会自动重复提交', async () => {
    postMock.mockRejectedValueOnce(new Error('timeout'))
    await expect(submitAnalysisRun(1, 35)).rejects.toThrow('timeout')
    expect(postMock).toHaveBeenCalledTimes(1)
  })

  it('GET 列表使用服务端分页，快照使用指定批次编号，并传递取消信号', async () => {
    const controller = new AbortController()
    getMock.mockResolvedValueOnce({ data: { items: [], total: 0 } })
    await listAnalysisRuns(2, 3, 10, controller.signal)
    expect(getMock).toHaveBeenCalledWith('/stocks/2/analysis-runs', {
      params: { page: 3, page_size: 10 },
      signal: controller.signal,
    })

    getMock.mockResolvedValueOnce({ data: { run_id: 8 } })
    await getAnalysisRun(2, 8, controller.signal)
    expect(getMock).toHaveBeenCalledWith('/stocks/2/analysis-runs/8', {
      signal: controller.signal,
    })
  })
})
