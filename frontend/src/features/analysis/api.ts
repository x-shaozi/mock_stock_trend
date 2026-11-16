import { http } from '../../api/http'
import { withGetRetry } from '../../api/retry'
import type {
  AnalysisRunDetailResponse,
  AnalysisRunListResponse,
  AnalysisRunRequest,
  AnalysisRunResponse,
  RunSubmitOutcome,
} from './types'

/**
 * 按后端分页读取已经保存的分析批次，不触发重新计算。
 * signal 由使用此函数的页面创建；离开页面或切换股票时可以取消旧 GET。
 */
export function listAnalysisRuns(
  stockId: number,
  page = 1,
  pageSize = 20,
  signal?: AbortSignal,
): Promise<AnalysisRunListResponse> {
  return withGetRetry(async () => {
    const response = await http.get<AnalysisRunListResponse>(`/stocks/${stockId}/analysis-runs`, {
      params: { page, page_size: pageSize },
      signal,
    })
    return response.data
  }, signal)
}

/** 读取指定 run_id 对应的逐日快照；这也是只读 GET。 */
export function getAnalysisRun(
  stockId: number,
  runId: number,
  signal?: AbortSignal,
): Promise<AnalysisRunDetailResponse> {
  return withGetRetry(async () => {
    const response = await http.get<AnalysisRunDetailResponse>(
      `/stocks/${stockId}/analysis-runs/${runId}`,
      { signal },
    )
    return response.data
  }, signal)
}

/**
 * POST 会在后端写入分析结果。超时只表示客户端没收到确认，不能据此再发一次。
 * days 放在 JSON 请求体里；201 代表新批次，200 代表同条件重算已有批次。
 */
export async function submitAnalysisRun(stockId: number, days: number): Promise<RunSubmitOutcome> {
  const payload: AnalysisRunRequest = { days }
  const response = await http.post<AnalysisRunResponse>(
    `/stocks/${stockId}/analysis-runs`,
    payload,
    { timeout: 45_000 },
  )
  return { data: response.data, created: response.status === 201 }
}
