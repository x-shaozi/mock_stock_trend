"""根据已完成交易日的调整后收盘价计算教学版趋势指标。"""

from collections.abc import Sequence
from dataclasses import dataclass
from itertools import pairwise
from math import fsum, isfinite

RULE_VERSION = "v1"
MIN_SCORE_BARS = 35


@dataclass(frozen=True, slots=True)
class Indicators:
    """一条日线对应的指标；历史不足时相应值为空。"""

    ma5: float | None
    ma20: float | None
    rsi14: float | None
    macd: float | None


@dataclass(frozen=True, slots=True)
class TrendAssessment:
    """一条日线的规则评分与标签。"""

    score: int
    label: str
    rule_version: str


def calculate_indicators(closes: Sequence[float]) -> list[Indicators]:
    """按交易日升序计算 MA、简单平均 RSI 和 MACD 柱值。"""
    prices = [float(close) for close in closes]
    if any(not isfinite(price) or price <= 0 for price in prices):
        raise ValueError("收盘价必须是大于零的有限数字")
    if not prices:
        return []

    ma5 = _moving_average(prices, 5)
    ma20 = _moving_average(prices, 20)
    rsi14 = _simple_rsi(prices, 14)
    macd = _macd_histogram(prices)
    return [
        Indicators(ma5[index], ma20[index], rsi14[index], macd[index])
        for index in range(len(prices))
    ]


def evaluate_trend(close: float, indicators: Indicators) -> TrendAssessment | None:
    """历史足够时按 v1 规则评分；指标不齐时不生成结论。"""
    if not isfinite(close) or close <= 0:
        raise ValueError("收盘价必须是大于零的有限数字")
    ma5 = indicators.ma5
    ma20 = indicators.ma20
    rsi14 = indicators.rsi14
    macd = indicators.macd
    if ma5 is None or ma20 is None or rsi14 is None or macd is None:
        return None
    if not all(isfinite(value) for value in (ma5, ma20, rsi14, macd)):
        raise ValueError("指标必须是有限数字")
    if not 0 <= rsi14 <= 100:
        raise ValueError("RSI 必须介于 0 和 100 之间")

    score = 50
    if close > ma20:
        score += 18
    elif close < ma20:
        score -= 12

    if ma5 > ma20:
        score += 14
    elif ma5 < ma20:
        score -= 8

    if macd > 0:
        score += 8
    elif macd < 0:
        score -= 8

    if 35 <= rsi14 <= 70:
        score += 6
    elif rsi14 > 70:
        score -= 6
    else:
        score -= 4

    score = max(0, min(100, score))
    if score >= 75:
        label = "强势上涨"
    elif score >= 60:
        label = "震荡偏强"
    elif score >= 45:
        label = "震荡观察"
    else:
        label = "偏弱下行"
    return TrendAssessment(score, label, RULE_VERSION)


def _moving_average(prices: list[float], window: int) -> list[float | None]:
    values: list[float | None] = [None] * len(prices)
    for index in range(window - 1, len(prices)):
        values[index] = fsum(prices[index - window + 1 : index + 1]) / window
    return values


def _simple_rsi(prices: list[float], window: int) -> list[float | None]:
    values: list[float | None] = [None] * len(prices)
    changes = [current - previous for previous, current in pairwise(prices)]
    for index in range(window, len(prices)):
        recent = changes[index - window : index]
        average_gain = fsum(max(change, 0) for change in recent) / window
        average_loss = fsum(max(-change, 0) for change in recent) / window
        if average_gain == 0 and average_loss == 0:
            values[index] = 50.0
        elif average_loss == 0:
            values[index] = 100.0
        else:
            strength = average_gain / average_loss
            values[index] = 100 - 100 / (1 + strength)
    return values


def _macd_histogram(prices: list[float]) -> list[float | None]:
    ema12 = _ema(prices, 12)
    ema26 = _ema(prices, 26)
    dif = [short - long for short, long in zip(ema12, ema26)]
    dea = _ema(dif, 9)
    values: list[float | None] = [None] * len(prices)
    for index in range(MIN_SCORE_BARS - 1, len(prices)):
        values[index] = dif[index] - dea[index]
    return values


def _ema(values: list[float], span: int) -> list[float]:
    alpha = 2 / (span + 1)
    result = [values[0]]
    for value in values[1:]:
        result.append(result[-1] + alpha * (value - result[-1]))
    return result
