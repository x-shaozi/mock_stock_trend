// 类型来自已验收的 FastAPI OpenAPI；执行 pnpm gen:api 后生成声明文件。
import type { components } from '../../api/generated/schema'

export type StockResponse = components['schemas']['StockResponse']
export type Stock = StockResponse
export type StockDetail = components['schemas']['StockDetailResponse']
export type StockListResponse = components['schemas']['StockListResponse']
export type StockCandidate = components['schemas']['StockCandidateResponse']
export type StockSearchResponse = components['schemas']['StockSearchResponse']
export type StockCreate = components['schemas']['StockCreate']
export type StockArchiveResponse = components['schemas']['StockArchiveResponse']
export type StockRestoreResponse = components['schemas']['StockRestoreResponse']
export type Market = 'CN' | 'US'
export type StockStatus = 'active' | 'archived'
