import type { Market } from './types'

export type RawQueryValue = string | readonly (string | null)[] | null | undefined
export type RawQuery = Record<string, RawQueryValue>

export interface StockListQuery {
  market: Market | ''
  keyword: string
  page: number
  pageSize: number
}

export const PAGE_SIZES = [10, 20, 50, 100] as const

// Vue Router 允许同名查询参数出现多次；本页面只使用第一个值。
function first(value: RawQueryValue): string | undefined {
  if (Array.isArray(value)) return value[0] ?? undefined
  return typeof value === 'string' ? value : undefined
}

function positiveInt(value: string | undefined, fallback: number): number {
  // 地址栏里的值都可能被用户手动改动，因此先验证再交给后端。
  if (!value || !/^\d+$/.test(value)) return fallback
  const number = Number(value)
  return Number.isSafeInteger(number) && number >= 1 ? number : fallback
}

export function parseStockListQuery(query: RawQuery): StockListQuery {
  // 从 URL 恢复页面状态。非法市场、页码或每页条数退回安全默认值。
  const market = first(query.market)
  const keyword = (first(query.keyword) ?? '').trim().slice(0, 50)
  const pageSize = positiveInt(first(query.page_size), 20)
  return {
    market: market === 'CN' || market === 'US' ? market : '',
    keyword,
    page: positiveInt(first(query.page), 1),
    pageSize: PAGE_SIZES.some((size) => size === pageSize) ? pageSize : 20,
  }
}

export function buildStockListQuery(query: StockListQuery): Record<string, string | undefined> {
  // 筛选或翻页时写回 URL，使刷新和分享链接能恢复同一组条件。
  return {
    market: query.market || undefined,
    keyword: query.keyword.trim() || undefined,
    page: String(query.page),
    page_size: String(query.pageSize),
  }
}
