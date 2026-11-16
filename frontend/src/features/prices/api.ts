import { http } from '../../api/http'
import { withGetRetry } from '../../api/retry'
import type { PriceCollectionResult, PriceHistory } from './types'

/** 读取已保存日线；不触发第三方数据采集。 */
export function getPriceHistory(
  stockId: number,
  days: number,
  signal?: AbortSignal,
): Promise<PriceHistory> {
  return withGetRetry(async () => {
    const response = await http.get<PriceHistory>(`/stocks/${stockId}/prices`, {
      params: { days },
      signal,
    })
    return response.data
  }, signal)
}

/** 写操作不自动重试：超时不等于服务端未完成采集。 */
export async function collectPrices(stockId: number, days: number): Promise<PriceCollectionResult> {
  const response = await http.post<PriceCollectionResult>(
    `/stocks/${stockId}/prices/collect`,
    undefined,
    {
      params: { days },
      timeout: 45_000,
    },
  )
  return response.data
}
