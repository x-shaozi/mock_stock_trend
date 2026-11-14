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

export class ApiRequestError extends Error {
  constructor(
    message: string,
    readonly httpStatus?: number,
    readonly errorCode?: string,
    readonly issues?: ValidationIssue[],
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
