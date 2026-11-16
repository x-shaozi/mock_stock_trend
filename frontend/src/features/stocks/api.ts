import { http } from '../../api/http'
import { withGetRetry } from '../../api/retry'
import type {
  Market,
  StockArchiveResponse,
  StockCandidate,
  StockCreate,
  StockDetail,
  StockListResponse,
  StockResponse,
  StockRestoreResponse,
  StockStatus,
} from './types'

// 本文件只负责把股票业务操作翻译成 HTTP 请求。
// 页面不直接配置 Axios；超时、基础地址和统一错误转换都交给 src/api/http.ts。
export interface StockListParams {
  status: StockStatus
  market?: Market
  keyword?: string
  page: number
  page_size: number
}

export async function listStocks(
  params: StockListParams,
  signal?: AbortSignal,
): Promise<StockListResponse> {
  // signal 由列表页创建。用户快速切换筛选条件时，可取消过期请求。
  const response = await http.get<StockListResponse>('/stocks', { params, signal })
  return response.data
}

export async function searchStocks(market: Market, query: string): Promise<StockCandidate[]> {
  const response = await http.get<{ items: StockCandidate[] }>('/stocks/search', {
    params: { market, query },
  })
  return response.data.items
}

export async function addStock(
  payload: Pick<StockCreate, 'market' | 'symbol'>,
): Promise<StockResponse> {
  // 名称由后端重新查询股票目录，本请求只提交市场和代码。
  const response = await http.post<StockResponse>('/stocks', payload)
  return response.data
}

export async function archiveStock(stockId: number): Promise<StockArchiveResponse> {
  const response = await http.patch<StockArchiveResponse>(`/stocks/${stockId}/archive`)
  return response.data
}

export async function restoreStock(stockId: number): Promise<StockRestoreResponse> {
  const response = await http.patch<StockRestoreResponse>(`/stocks/${stockId}/restore`)
  return response.data
}

/** P1 新增的详情接口；归档股票也可以查询。 */
export function getStock(stockId: number, signal?: AbortSignal): Promise<StockDetail> {
  return withGetRetry(async () => {
    const response = await http.get<StockDetail>(`/stocks/${stockId}`, { signal })
    return response.data
  }, signal)
}
