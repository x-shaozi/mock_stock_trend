import { describe, expect, it } from 'vitest'
import { extractApiErrorPayload } from './errors'

describe('后端错误契约', () => {
  it('识别 P1 业务错误码', () => {
    expect(
      extractApiErrorPayload({ code: 409, message: '股票已归档', error_code: 'STOCK_ARCHIVED' }),
    ).toEqual({
      code: 409,
      message: '股票已归档',
      error_code: 'STOCK_ARCHIVED',
      errors: undefined,
    })
  })

  it('未知响应不能当作业务错误', () => {
    expect(extractApiErrorPayload('bad gateway')).toBeUndefined()
  })

  it('过滤无效的验证错误条目', () => {
    expect(
      extractApiErrorPayload({ errors: [{ field: 'query.days', message: '不合法' }, 5] })?.errors,
    ).toEqual([{ field: 'query.days', message: '不合法' }])
  })
})
