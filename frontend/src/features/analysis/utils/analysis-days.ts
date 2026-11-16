/**
 * 分析接口只接受 35～260 条完整日线。输入框清空时可能临时产生空值，
 * 因此按钮状态和提交前检查都使用同一条规则，避免把无效值发给后端。
 */
export function isValidAnalysisDays(value: number | null | undefined): value is number {
  return typeof value === 'number' && Number.isSafeInteger(value) && value >= 35 && value <= 260
}
