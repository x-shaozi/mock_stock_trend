import { describe, expect, it } from 'vitest'
import { buildStockListQuery, parseStockListQuery } from './query'

describe('股票列表 URL 查询状态', () => {
  it('默认只请求第一页、每页 20 条', () => {
    expect(parseStockListQuery({})).toEqual({
      market: '',
      keyword: '',
      page: 1,
      pageSize: 20,
    })
  })

  it('解析并清理筛选参数，避免无效参数破坏页面', () => {
    expect(
      parseStockListQuery({ market: 'US', keyword: '  APP  ', page: '2', page_size: '50' }),
    ).toEqual({
      market: 'US',
      keyword: 'APP',
      page: 2,
      pageSize: 50,
    })
    expect(parseStockListQuery({ market: 'ALL', page: '-1', page_size: '200' })).toEqual({
      market: '',
      keyword: '',
      page: 1,
      pageSize: 20,
    })
  })

  it('保留筛选与分页状态供 URL 刷新恢复', () => {
    const data = { market: 'CN' as const, keyword: '688', page: 3, pageSize: 10 }
    expect(parseStockListQuery(buildStockListQuery(data))).toEqual(data)
  })
})
