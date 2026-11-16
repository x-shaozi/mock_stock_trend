import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiRequestError } from '../../api/errors'
import { collectPrices, getPriceHistory } from './api'

// 用假 HTTP 客户端核对前端发出的请求；测试不会访问真实后端或修改数据库。
const requests = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn() }))
vi.mock('../../api/http', () => ({ http: requests }))

beforeEach(() => vi.clearAllMocks())

describe('日线接口请求', () => {
  it('查询已存日线时传入股票编号、条数和取消信号', async () => {
    const history = { stock_id: 9, symbol: 'SNEJF', market: 'US', items: [] }
    const signal = new AbortController().signal
    requests.get.mockResolvedValueOnce({ data: history })

    await expect(getPriceHistory(9, 30, signal)).resolves.toEqual(history)
    expect(requests.get).toHaveBeenCalledExactlyOnceWith('/stocks/9/prices', {
      params: { days: 30 },
      signal,
    })
  })

  it('采集是一次 POST，成功后返回真实计数', async () => {
    const result = { stock_id: 9, symbol: 'SNEJF', inserted: 2, updated: 1, unchanged: 27 }
    requests.post.mockResolvedValueOnce({ data: result })

    await expect(collectPrices(9, 30)).resolves.toEqual(result)
    expect(requests.post).toHaveBeenCalledExactlyOnceWith('/stocks/9/prices/collect', undefined, {
      params: { days: 30 },
      timeout: 45_000,
    })
  })

  it('采集超时后直接报错，不自动再次提交', async () => {
    requests.post.mockRejectedValueOnce(
      new ApiRequestError('请求超时', undefined, undefined, undefined, 'timeout'),
    )

    await expect(collectPrices(9, 30)).rejects.toThrow('请求超时')
    expect(requests.post).toHaveBeenCalledTimes(1)
  })
})
