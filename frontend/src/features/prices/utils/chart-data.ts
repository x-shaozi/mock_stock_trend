import type { DailyPrice } from '../types'

export interface CandleChartData {
  dates: string[]
  candles: [number, number, number, number][] // ECharts: open, close, low, high
  volumes: number[]
  rows: DailyPrice[]
  currency: string
  source: string
  adjustment: string
}

function parsePrice(value: string): number {
  const number = Number(value)
  if (!/^[+-]?\d+(?:\.\d+)?$/.test(value) || !Number.isFinite(number) || number <= 0) {
    throw new Error('行情中存在无效价格，无法安全绘制 K 线')
  }
  return number
}

/** 仅用于绘图的数据适配；不改变 API 原始 Decimal 字符串。 */
export function toCandleChartData(items: DailyPrice[]): CandleChartData {
  const rows = [...items].sort((a, b) => a.trade_date.localeCompare(b.trade_date))
  const dates: string[] = []
  const candles: CandleChartData['candles'] = []
  const volumes: number[] = []
  let basis: string | undefined

  for (const row of rows) {
    const currentBasis = JSON.stringify([row.currency, row.source, row.adjustment])
    if (basis && currentBasis !== basis) {
      throw new Error('历史行情存在不同来源、币种或复权口径，暂不能合并绘图')
    }
    basis = currentBasis
    if (!/^\d{4}-\d{2}-\d{2}$/.test(row.trade_date) || dates.includes(row.trade_date)) {
      throw new Error('历史行情交易日期异常或重复，暂不能绘图')
    }
    const open = parsePrice(row.open_price)
    const high = parsePrice(row.high_price)
    const low = parsePrice(row.low_price)
    const close = parsePrice(row.close_price)
    if (high < Math.max(open, close, low) || low > Math.min(open, close, high)) {
      throw new Error(`交易日 ${row.trade_date} 的 OHLC 价格范围不正确`)
    }
    if (!Number.isSafeInteger(row.volume) || row.volume < 0) {
      throw new Error(`交易日 ${row.trade_date} 的成交量无效`)
    }
    dates.push(row.trade_date)
    candles.push([open, close, low, high])
    volumes.push(row.volume)
  }
  return {
    dates,
    candles,
    volumes,
    rows,
    currency: rows[0]?.currency || '',
    source: rows[0]?.source || '',
    adjustment: rows[0]?.adjustment || '',
  }
}

export function formatDecimalPrice(value: string, currency: string): string {
  const number = Number(value)
  if (!Number.isFinite(number)) return value
  return `${new Intl.NumberFormat('zh-CN', { maximumFractionDigits: 6 }).format(number)} ${currency}`.trim()
}
