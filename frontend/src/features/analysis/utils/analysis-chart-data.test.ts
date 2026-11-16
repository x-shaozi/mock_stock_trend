import { describe, expect, it } from 'vitest'
import type { AnalysisResultItem, AnalysisRunDetailResponse } from '../types'
import { formatAnalysisValue, pageAnalysisRows, toAnalysisChartData } from './analysis-chart-data'

function fixture(count = 35): AnalysisRunDetailResponse {
  const items: AnalysisResultItem[] = Array.from({ length: count }, (_, index) => {
    const date = new Date(Date.UTC(2026, 0, index + 1)).toISOString().slice(0, 10)
    return {
      trade_date: date,
      close_price: (100 + index).toFixed(6),
      ma5: index >= 4 ? (99 + index).toFixed(6) : null,
      ma20: index >= 19 ? (95 + index).toFixed(6) : null,
      rsi14: index >= 14 ? '50.0000' : null,
      macd: index >= 34 ? '0.125000' : null,
      trend_score: index >= 34 ? 72 : null,
      trend_label: index >= 34 ? '震荡偏强' : null,
      summary: index >= 34 ? '后端保存的规则说明' : null,
    }
  })
  return {
    run_id: 1,
    stock_id: 2,
    symbol: 'AAPL',
    market: 'US',
    requested_days: count,
    saved: count,
    start_date: items[0]!.trade_date,
    end_date: items[items.length - 1]!.trade_date,
    source: 'twelvedata',
    adjustment: 'all',
    rule_version: 'v1',
    computed_at: '2026-11-15T01:00:00Z',
    items,
  }
}

describe('S3 分析快照图表数据整理', () => {
  it('前 34 条保留空 MACD 和评分，较早形成的 MA5、RSI 正常展示', () => {
    const result = toAnalysisChartData(fixture())
    expect(result.macd.slice(0, 34).every((value) => value === null)).toBe(true)
    expect(result.score.slice(0, 34).every((value) => value === null)).toBe(true)
    expect(result.macd[34]).toBe(0.125)
    expect(result.score[34]).toBe(72)
    expect(result.ma5[4]).toBe(103)
    expect(result.rsi14[14]).toBe(50)
  })

  it('按交易日排序供绘图，但明细仍保留后端的价格字符串', () => {
    const input = fixture()
    input.items.reverse()
    const result = toAnalysisChartData(input)
    expect(result.dates[0]).toBe(input.start_date)
    expect(result.rows[0]?.close_price).toBe('100.000000')
    expect(result.close[34]).toBe(134)
  })

  it('拒绝重复日期、记录数量不一致、越界 RSI 和评分', () => {
    const duplicated = fixture()
    duplicated.items[1]!.trade_date = duplicated.items[0]!.trade_date
    expect(() => toAnalysisChartData(duplicated)).toThrow('重复')

    const missing = fixture()
    missing.items.pop()
    expect(() => toAnalysisChartData(missing)).toThrow('数量不一致')

    const badRsi = fixture()
    badRsi.items[34]!.rsi14 = '110.0'
    expect(() => toAnalysisChartData(badRsi)).toThrow('RSI14')

    const badScore = fixture()
    badScore.items[34]!.trend_score = 101
    expect(() => toAnalysisChartData(badScore)).toThrow('评分')
  })

  it('不把尚未生成的指标画成 0，也不接受预热期提前评分', () => {
    expect(formatAnalysisValue(null)).toBe('—')
    expect(formatAnalysisValue('0.000000')).toBe('0')
    const bad = fixture()
    bad.items[12]!.trend_score = 80
    expect(() => toAnalysisChartData(bad)).toThrow('预热')
  })

  it('逐日表格先显示最近 20 条，下一页显示更早记录且不改变图表顺序', () => {
    const result = toAnalysisChartData(fixture())
    const firstPage = pageAnalysisRows(result.rows, 1, 20)
    const secondPage = pageAnalysisRows(result.rows, 2, 20)
    expect(firstPage).toHaveLength(20)
    expect(secondPage).toHaveLength(15)
    expect(firstPage[0]?.trade_date).toBe(result.dates.at(-1))
    expect(secondPage.at(-1)?.trade_date).toBe(result.dates[0])
    expect(new Set([...firstPage, ...secondPage].map((row) => row.trade_date)).size).toBe(35)
    expect(result.rows[0]?.trade_date).toBe(result.dates[0])
    expect(pageAnalysisRows(result.rows, 3, 20)).toEqual([])
  })
})
