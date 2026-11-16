import { ApiRequestError } from './errors'

/** 仅适用于可安全重复的 GET 请求；POST/PATCH 绝不调用此方法。 */
export async function withGetRetry<T>(
  request: () => Promise<T>,
  signal?: AbortSignal,
  maxRetries = 2,
): Promise<T> {
  for (let attempt = 0; ; attempt += 1) {
    if (signal?.aborted)
      throw new ApiRequestError('请求已取消', undefined, undefined, undefined, 'aborted')
    try {
      return await request()
    } catch (error: unknown) {
      const retryable =
        error instanceof ApiRequestError &&
        (error.kind === 'network' ||
          error.kind === 'timeout' ||
          ((error.httpStatus === 502 || error.httpStatus === 503) && !error.errorCode))
      if (!retryable || attempt >= maxRetries || signal?.aborted) throw error
      await waitForRetry(300 * 2 ** attempt, signal)
    }
  }
}

function waitForRetry(ms: number, signal?: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal?.aborted) {
      reject(new ApiRequestError('请求已取消', undefined, undefined, undefined, 'aborted'))
      return
    }
    const timer = setTimeout(() => {
      signal?.removeEventListener('abort', onAbort)
      resolve()
    }, ms)
    function onAbort(): void {
      clearTimeout(timer)
      signal?.removeEventListener('abort', onAbort)
      reject(new ApiRequestError('请求已取消', undefined, undefined, undefined, 'aborted'))
    }
    signal?.addEventListener('abort', onAbort, { once: true })
  })
}
