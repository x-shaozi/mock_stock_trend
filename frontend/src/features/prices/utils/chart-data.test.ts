import { describe, expect, it } from 'vitest'
import { toCandleChartData, formatDecimalPrice } from './chart-data'
import type { DailyPrice } from '../types'

const a: DailyPrice = {
  trade_date: '2026-11-13',
  open_price: '102.000000',
  high_price: '110.000000',
  low_price: '99.500000',
  close_price: '108.300000',
  volume: 120000,
  currency: 'USD',
  source: 'twelvedata',
  adjustment: 'all',
}
const b: DailyPrice = {
  ...a,
  trade_date: '2026-11-12',
  open_price: '98.000000',
  high_price: '104.000000',
  low_price: '97.000000',
  close_price: '101.000000',
  volume: 95000,
}

describe('日线转 ECharts 数据', () => {
  it('按交易日期升序排列，K 线数据顺序为开收低高', () => {
    const chart = toCandleChartData([a, b])
    expect(chart.dates).toEqual(['2026-11-12', '2026-11-13'])
    expect(chart.candles).toEqual([
      [98, 101, 97, 104],
      [102, 108.3, 99.5, 110],
    ])
    expect(chart.volumes).toEqual([95000, 120000])
    expect(chart.rows[0].close_price).toBe('101.000000')
  })
  it('空行情是合法状态', () => {
    expect(toCandleChartData([]).dates).toEqual([])
  })
  it('拒绝混合复权口径', () => {
    expect(() => toCandleChartData([a, { ...b, adjustment: 'none' }])).toThrow('不同来源')
  })
  it('拒绝重复日期、非法价格和异常成交量', () => {
    expect(() => toCandleChartData([a, a])).toThrow('重复')
    expect(() => toCandleChartData([{ ...a, low_price: '120' }])).toThrow('OHLC')
    expect(() => toCandleChartData([{ ...a, close_price: 'not a number' }])).toThrow('无效价格')
    expect(() => toCandleChartData([{ ...a, volume: -1 }])).toThrow('成交量')
  })
  it('保留原字符串精度，仅展示时格式化', () => {
    expect(formatDecimalPrice(a.close_price, 'USD')).toBe('108.3 USD')
  })
})
