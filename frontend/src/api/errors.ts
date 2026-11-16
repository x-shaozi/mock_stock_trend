export interface ValidationIssue {
  field: string
  message: string
}

export interface ApiErrorPayload {
  code?: number
  message?: string
  error_code?: string | null
  errors?: ValidationIssue[] | null
}

export type RequestErrorKind = 'http' | 'network' | 'timeout' | 'aborted'

export class ApiRequestError extends Error {
  constructor(
    message: string,
    readonly httpStatus?: number,
    readonly errorCode?: string,
    readonly issues?: ValidationIssue[],
    readonly kind: RequestErrorKind = 'http',
  ) {
    super(message)
    this.name = 'ApiRequestError'
  }
}

export function extractApiErrorPayload(data: unknown): ApiErrorPayload | undefined {
  if (!data || typeof data !== 'object' || Array.isArray(data)) return undefined
  const item = data as Record<string, unknown>
  return {
    code: typeof item.code === 'number' ? item.code : undefined,
    message: typeof item.message === 'string' ? item.message : undefined,
    error_code: typeof item.error_code === 'string' ? item.error_code : undefined,
    errors: Array.isArray(item.errors)
      ? item.errors.filter(
          (issue): issue is ValidationIssue =>
            typeof issue === 'object' &&
            issue !== null &&
            typeof issue.field === 'string' &&
            typeof issue.message === 'string',
        )
      : undefined,
  }
}

export interface ErrorDisplay {
  title: string
  detail: string
  retryable: boolean
}

/** 前端只依据可确认的错误信息分类，不把任意 500/502 断言为 MySQL 故障。 */
export function describeRequestError(error: unknown): ErrorDisplay {
  if (!(error instanceof ApiRequestError)) {
    return {
      title: '数据处理失败',
      detail: error instanceof Error ? error.message : '发生未知异常，请重试。',
      retryable: true,
    }
  }
  if (error.kind === 'timeout') {
    return {
      title: '请求超时',
      detail: '服务响应时间过长。请检查网络，并重新查询。',
      retryable: true,
    }
  }
  if (error.kind === 'network') {
    return {
      title: '无法连接股票分析服务',
      detail: '请检查局域网连接，确认开发电脑和 FastAPI 后端已启动，然后重试。',
      retryable: true,
    }
  }
  if (
    error.errorCode === 'MARKET_DATA_UNAVAILABLE' ||
    error.errorCode === 'STOCK_CATALOG_UNAVAILABLE'
  ) {
    return { title: '外部行情服务暂不可用', detail: error.message, retryable: true }
  }
  if ((error.httpStatus === 502 && !error.errorCode) || error.httpStatus === 503) {
    return {
      title: '服务暂不可用',
      detail: '请求可能未到达后端服务，请检查前端代理及后端运行状态。',
      retryable: true,
    }
  }
  if (error.httpStatus && error.httpStatus >= 500) {
    return {
      title: '股票分析服务暂时异常',
      detail: '服务端处理请求失败，请稍后重试。',
      retryable: true,
    }
  }
  if (error.httpStatus === 422) {
    return {
      title: '请求参数不合法',
      detail:
        error.issues?.map((issue) => `${issue.field}：${issue.message}`).join('；') ||
        error.message,
      retryable: false,
    }
  }
  if (error.httpStatus === 404) {
    return { title: '资源不存在', detail: error.message, retryable: false }
  }
  if (error.httpStatus === 409) {
    return { title: '操作存在冲突', detail: error.message, retryable: false }
  }
  return { title: '请求失败', detail: error.message, retryable: true }
}
