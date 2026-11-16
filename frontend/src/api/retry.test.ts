import { describe, expect, it, vi } from 'vitest'
import { ApiRequestError } from './errors'
import { withGetRetry } from './retry'

describe('只读请求有限重试', () => {
  it('网络错误后恢复时成功，最多尝试三次', async () => {
    const fn = vi
      .fn()
      .mockRejectedValueOnce(
        new ApiRequestError('离线', undefined, undefined, undefined, 'network'),
      )
      .mockResolvedValueOnce('ok')
    await expect(withGetRetry(fn, undefined, 2)).resolves.toBe('ok')
    expect(fn).toHaveBeenCalledTimes(2)
  })
  it('不重试 409 等业务错误', async () => {
    const fn = vi.fn().mockRejectedValue(new ApiRequestError('冲突', 409, 'STOCK_ARCHIVED'))
    await expect(withGetRetry(fn)).rejects.toThrow('冲突')
    expect(fn).toHaveBeenCalledTimes(1)
  })
  it('503 带业务错误码时不重试', async () => {
    const fn = vi
      .fn()
      .mockRejectedValue(new ApiRequestError('服务维护中', 503, 'SERVICE_MAINTENANCE'))
    await expect(withGetRetry(fn)).rejects.toThrow('服务维护中')
    expect(fn).toHaveBeenCalledTimes(1)
  })
  it('超过重试次数后抛出异常', async () => {
    const fn = vi
      .fn()
      .mockRejectedValue(new ApiRequestError('离线', undefined, undefined, undefined, 'network'))
    await expect(withGetRetry(fn, undefined, 1)).rejects.toThrow('离线')
    expect(fn).toHaveBeenCalledTimes(2)
  })
})
