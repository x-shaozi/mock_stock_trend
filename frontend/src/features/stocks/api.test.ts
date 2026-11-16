import { beforeEach, describe, expect, it, vi } from 'vitest'
import { addStock, archiveStock, getStock, listStocks, restoreStock, searchStocks } from './api'

// 替换统一 HTTP 客户端：验证前端发出的路径与参数，不依赖真实 MySQL 或行情网站。
const requests = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  patch: vi.fn(),
}))

vi.mock('../../api/http', () => ({ http: requests }))

beforeEach(() => {
  vi.clearAllMocks()
})

describe('股票接口请求', () => {
  it('详情 GET 可独立读取已归档股票', async () => {
    const stock = { id: 9, symbol: 'SNEJF', name: 'Sony', market: 'US', status: 'archived' }
    const signal = new AbortController().signal
    requests.get.mockResolvedValueOnce({ data: stock })

    await expect(getStock(9, signal)).resolves.toEqual(stock)
    expect(requests.get).toHaveBeenCalledExactlyOnceWith('/stocks/9', { signal })
  })

  it('列表请求带上状态、筛选、分页和取消信号', async () => {
    const result = { items: [], total: 0, page: 2, page_size: 10 }
    const params = { status: 'archived' as const, market: 'CN' as const, page: 2, page_size: 10 }
    const signal = new AbortController().signal
    requests.get.mockResolvedValueOnce({ data: result })

    await expect(listStocks(params, signal)).resolves.toEqual(result)
    expect(requests.get).toHaveBeenCalledWith('/stocks', { params, signal })
  })

  it('目录搜索只返回响应中的候选股票', async () => {
    const candidate = { symbol: '688385.SH', name: '复旦微电', market: 'CN', exchange: 'SH' }
    requests.get.mockResolvedValueOnce({ data: { items: [candidate] } })

    await expect(searchStocks('CN', '复旦微电')).resolves.toEqual([candidate])
    expect(requests.get).toHaveBeenCalledWith('/stocks/search', {
      params: { market: 'CN', query: '复旦微电' },
    })
  })

  it('新增请求只提交市场和代码', async () => {
    const stock = { id: 9, symbol: 'MSFT', name: 'Microsoft', market: 'US' }
    requests.post.mockResolvedValueOnce({ data: stock })

    await expect(addStock({ market: 'US', symbol: 'MSFT' })).resolves.toEqual(stock)
    expect(requests.post).toHaveBeenCalledWith('/stocks', { market: 'US', symbol: 'MSFT' })
  })

  it('归档和恢复使用各自的 PATCH 路径', async () => {
    requests.patch
      .mockResolvedValueOnce({ data: { id: 9, symbol: 'MSFT', status: 'archived' } })
      .mockResolvedValueOnce({ data: { id: 9, symbol: 'MSFT', status: 'active' } })

    await expect(archiveStock(9)).resolves.toMatchObject({ status: 'archived' })
    await expect(restoreStock(9)).resolves.toMatchObject({ status: 'active' })
    expect(requests.patch).toHaveBeenNthCalledWith(1, '/stocks/9/archive')
    expect(requests.patch).toHaveBeenNthCalledWith(2, '/stocks/9/restore')
  })

  it('网络错误继续交给页面展示，不伪造成功数据', async () => {
    const failure = new Error('无法连接后端服务')
    requests.get.mockRejectedValueOnce(failure)

    await expect(searchStocks('US', 'MSFT')).rejects.toBe(failure)
  })
})
