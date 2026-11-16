import type { AnalysisResultItem, AnalysisRunDetailResponse } from '../types'

/** 图表需要数字数组；rows 仍保留后端返回的 Decimal 字符串供明细表使用。 */
export interface AnalysisChartData {
  dates: string[]
  close: number[]
  ma5: Array<number | null>
  ma20: Array<number | null>
  rsi14: Array<number | null>
  macd: Array<number | null>
  score: Array<number | null>
  rows: AnalysisResultItem[]
}

function readDecimal(value: string, field: string, tradeDate: string): number {
  // API 中的价格和指标是十进制字符串。只有在绘图时才转成 JavaScript 数字。
  if (!/^[+-]?\d+(?:\.\d+)?$/.test(value)) {
    throw new Error(`${tradeDate} 的 ${field} 不是有效数字`)
  }
  const parsed = Number(value)
  if (!Number.isFinite(parsed)) throw new Error(`${tradeDate} 的 ${field} 超出数值范围`)
  return parsed
}

function optionalDecimal(value: string | null, field: string, date: string): number | null {
  // 指标尚未形成时，后端返回 null。图表必须留空，不能把它画成 0。
  return value === null ? null : readDecimal(value, field, date)
}

/**
 * 将后端已经保存的逐日结果整理成 ECharts 可用的数据。
 * 这里只做校验、日期排序和数值转换，不计算 MA、RSI、MACD 或趋势评分。
 */
export function toAnalysisChartData(detail: AnalysisRunDetailResponse): AnalysisChartData {
  const rows = [...detail.items].sort((a, b) => a.trade_date.localeCompare(b.trade_date))
  const dates: string[] = []
  const close: number[] = []
  const ma5: Array<number | null> = []
  const ma20: Array<number | null> = []
  const rsi14: Array<number | null> = []
  const macd: Array<number | null> = []
  const score: Array<number | null> = []

  if (rows.length !== detail.saved || rows.length !== detail.requested_days) {
    throw new Error('分析批次的逐日记录数与保存数量不一致，无法可靠绘图')
  }
  if (
    rows.length &&
    (rows[0]!.trade_date !== detail.start_date ||
      rows[rows.length - 1]!.trade_date !== detail.end_date)
  ) {
    throw new Error('分析批次的日期范围与逐日记录不一致')
  }

  for (const [index, row] of rows.entries()) {
    const date = row.trade_date
    if (!/^\d{4}-\d{2}-\d{2}$/.test(date) || dates.includes(date)) {
      throw new Error('分析批次包含无效或重复的交易日期')
    }
    const currentClose = readDecimal(row.close_price, '收盘价', date)
    if (currentClose <= 0) throw new Error(`${date} 的收盘价必须大于零`)
    const rsi = optionalDecimal(row.rsi14, 'RSI14', date)
    if (rsi !== null && (rsi < 0 || rsi > 100)) {
      throw new Error(`${date} 的 RSI14 超出 0～100 范围`)
    }
    const trend = row.trend_score
    if (trend !== null && (!Number.isInteger(trend) || trend < 0 || trend > 100)) {
      throw new Error(`${date} 的趋势评分超出 0～100 范围`)
    }
    // 已确认的 v1 规则：前 34 条没有 MACD、评分及评分标签；MA/RSI 可以更早出现。
    if (index < 34 && (row.macd !== null || trend !== null || row.trend_label !== null)) {
      throw new Error(`${date} 的指标预热区间存在提前生成的评分或 MACD`)
    }
    dates.push(date)
    close.push(currentClose)
    ma5.push(optionalDecimal(row.ma5, 'MA5', date))
    ma20.push(optionalDecimal(row.ma20, 'MA20', date))
    rsi14.push(rsi)
    macd.push(optionalDecimal(row.macd, 'MACD', date))
    score.push(trend)
  }

  return { dates, close, ma5, ma20, rsi14, macd, score, rows }
}

/** 仅格式化页面文字；空指标显示破折号，零值仍显示为 0。 */
export function formatAnalysisValue(value: string | number | null | undefined, digits = 4): string {
  if (value == null) return '—'
  const parsed = typeof value === 'number' ? value : Number(value)
  if (!Number.isFinite(parsed)) return '—'
  return new Intl.NumberFormat('zh-CN', { maximumFractionDigits: digits }).format(parsed)
}

/** computed_at 是 UTC 时间戳；浏览器按用户所在时区显示，不改动交易日期。 */
export function formatComputedAt(value: string): string {
  const parsed = new Date(value)
  return Number.isNaN(parsed.getTime())
    ? '时间格式异常'
    : new Intl.DateTimeFormat('zh-CN', { dateStyle: 'medium', timeStyle: 'medium' }).format(parsed)
}

/**
 * 后端快照按交易日保存；表格默认先显示最近的日期。
 * 数组本身不倒序，避免影响共用同一份数据的图表日期顺序。
 */
export function pageAnalysisRows(
  rows: AnalysisResultItem[],
  page: number,
  pageSize: number,
): AnalysisResultItem[] {
  if (!Number.isSafeInteger(page) || page < 1 || !Number.isSafeInteger(pageSize) || pageSize < 1) {
    return []
  }
  const end = rows.length - (page - 1) * pageSize
  if (end <= 0) return []
  return rows.slice(Math.max(0, end - pageSize), end).reverse()
}
