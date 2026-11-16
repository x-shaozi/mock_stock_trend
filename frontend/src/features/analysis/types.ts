/**
 * 分析接口的字段直接来自 OpenAPI 生成文件。
 * 后端调整响应结构时，重新生成类型即可让前端的类型检查指出受影响的位置。
 */
import type { components } from '../../api/generated/schema'

export type AnalysisRunRequest = components['schemas']['AnalysisRunRequest']
export type AnalysisRunResponse = components['schemas']['AnalysisRunResponse']
export type AnalysisRunListItem = components['schemas']['AnalysisRunListItem']
export type AnalysisRunListResponse = components['schemas']['AnalysisRunListResponse']
export type AnalysisRunDetailResponse = components['schemas']['AnalysisRunDetailResponse']
export type AnalysisResultItem = components['schemas']['AnalysisResultItem']

/** 响应体没有“新建还是重算”字段，所以同时保留 HTTP 状态码表达的结果。 */
export interface RunSubmitOutcome {
  data: AnalysisRunResponse
  created: boolean
}
