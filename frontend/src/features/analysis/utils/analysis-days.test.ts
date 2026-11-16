import { describe, expect, it } from 'vitest'
import { isValidAnalysisDays } from './analysis-days'

describe('分析条数输入校验', () => {
  it('只允许 35～260 的整数；空白、非整数和越界值不能提交', () => {
    for (const value of [null, undefined, Number.NaN, 1.5, 34, 261]) {
      expect(isValidAnalysisDays(value)).toBe(false)
    }
    expect(isValidAnalysisDays(35)).toBe(true)
    expect(isValidAnalysisDays(260)).toBe(true)
  })
})
