import { describe, expect, it } from 'vitest'
import { ApiRequestError, describeRequestError } from './errors'

function err(message: string, status?: number, code?: string) {
  return new ApiRequestError(message, status, code)
}

describe('统一错误提示', () => {
  it('后端断线和网络超时不同文案', () => {
    expect(
      describeRequestError(new ApiRequestError('失败', undefined, undefined, undefined, 'network'))
        .title,
    ).toContain('无法连接')
    expect(
      describeRequestError(new ApiRequestError('失败', undefined, undefined, undefined, 'timeout'))
        .title,
    ).toBe('请求超时')
  })
  it('不把未知代理 502 误认为行情数据源故障', () => {
    expect(describeRequestError(err('Bad Gateway', 502)).title).toBe('服务暂不可用')
    expect(describeRequestError(err('供应商出错', 502, 'MARKET_DATA_UNAVAILABLE')).title).toContain(
      '外部行情',
    )
  })
  it('业务冲突与验证失败不自动重试', () => {
    expect(describeRequestError(err('股票已归档', 409, 'STOCK_ARCHIVED')).retryable).toBe(false)
    expect(describeRequestError(err('参数无效', 422)).retryable).toBe(false)
  })
  it('500 不直接断定 MySQL 故障', () => {
    expect(describeRequestError(err('服务器内部错误', 500)).title).toBe('股票分析服务暂时异常')
  })
})
