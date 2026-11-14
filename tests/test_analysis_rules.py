from math import inf, nan

import pytest

from app.service.analysis_rules import (
    Indicators,
    calculate_indicators,
    evaluate_trend,
)


def test_ma5_uses_the_latest_five_closes() -> None:
    points = calculate_indicators([100, 102, 101, 105, 108])

    assert points[-1].ma5 == pytest.approx(103.2)
    assert points[-1].ma20 is None
    assert points[-1].rsi14 is None
    assert points[-1].macd is None


@pytest.mark.parametrize(
    ("closes", "expected"),
    [
        (list(range(1, 16)), 100.0),
        (list(range(15, 0, -1)), 0.0),
        ([100.0] * 15, 50.0),
        ([100.0, 101.0] * 7 + [100.0], 50.0),
    ],
)
def test_simple_rsi_handles_rising_falling_flat_and_mixed_prices(
    closes: list[float], expected: float
) -> None:
    points = calculate_indicators(closes)

    assert points[13].rsi14 is None
    assert points[14].rsi14 == pytest.approx(expected)


def test_macd_matches_independent_decimal_reference() -> None:
    points = calculate_indicators(list(range(1, 36)))

    assert points[33].macd is None
    assert points[34].macd == pytest.approx(0.3840588563773852)
    assert points[34].ma5 == pytest.approx(33.0)
    assert points[34].ma20 == pytest.approx(25.5)


def test_trend_needs_all_indicators_before_scoring() -> None:
    points = calculate_indicators(list(range(1, 36)))

    assert evaluate_trend(34, points[33]) is None
    assessment = evaluate_trend(35, points[34])
    assert assessment is not None
    assert (assessment.score, assessment.label, assessment.rule_version) == (
        84,
        "强势上涨",
        "v1",
    )


def test_course_scoring_example() -> None:
    indicators = Indicators(ma5=103, ma20=100, rsi14=60, macd=0.5)

    assessment = evaluate_trend(105, indicators)

    assert assessment is not None
    assert (assessment.score, assessment.label) == (96, "强势上涨")


def test_flat_prices_keep_neutral_score() -> None:
    points = calculate_indicators([100.0] * 35)

    assessment = evaluate_trend(100.0, points[-1])

    assert points[-1].rsi14 == 50
    assert points[-1].macd == 0
    assert assessment is not None
    assert (assessment.score, assessment.label) == (56, "震荡观察")


def test_falling_prices_get_weak_label() -> None:
    points = calculate_indicators(list(range(100, 65, -1)))

    assessment = evaluate_trend(66, points[-1])

    assert assessment is not None
    assert (assessment.score, assessment.label) == (18, "偏弱下行")


@pytest.mark.parametrize("close", [0, -1, nan, inf])
def test_invalid_close_is_rejected(close: float) -> None:
    with pytest.raises(ValueError, match="收盘价"):
        calculate_indicators([close])


def test_empty_history_has_no_indicators() -> None:
    assert calculate_indicators([]) == []
