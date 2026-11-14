"""组织一次趋势分析：核对行情，运行已确认的 v1 规则并保存结果。"""

from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import ROUND_HALF_UP, Decimal

from app.models.analysis_run import AnalysisRun
from app.models.stock import Stock
from app.repository.analysis import AnalysisDay, AnalysisRepository
from app.repository.daily_price import DailyPriceRepository
from app.repository.stock import StockRepository
from app.service.analysis_rules import (
    MIN_SCORE_BARS,
    RULE_VERSION,
    calculate_indicators,
    evaluate_trend,
)


class AnalysisStockNotFound(Exception):
    """股票编号在 stocks 表中不存在。"""


class AnalysisStockArchived(Exception):
    """归档股票不接受新的分析。"""


class AnalysisDataInsufficient(Exception):
    """数据库中的日线数量不够本次请求的计算范围。"""

    def __init__(self, requested: int, available: int) -> None:
        self.requested = requested
        self.available = available


class AnalysisPriceBasisConflict(Exception):
    """日线来源、币种或调整方式不符合这一轮分析的统一口径。"""


class AnalysisRunNotFound(Exception):
    """所请求的股票与分析批次组合不存在。"""


@dataclass(frozen=True, slots=True)
class AnalysisRunOutcome:
    """交给路由的结果；HTTP 状态码仍由路由决定。"""

    run_id: int
    stock_id: int
    symbol: str
    requested_days: int
    start_date: date
    end_date: date
    source: str
    adjustment: str
    rule_version: str
    created: bool
    latest: AnalysisDay


def _decimal(value: float | None, places: int) -> Decimal | None:
    """将计算结果按数据库字段精度固定下来，响应与入库使用同一数值。"""
    if value is None:
        return None
    unit = Decimal(1).scaleb(-places)
    return Decimal(str(value)).quantize(unit, rounding=ROUND_HALF_UP)


class AnalysisService:
    """只组织业务规则，不直接持有数据库会话。"""

    def __init__(
        self,
        stocks: StockRepository,
        prices: DailyPriceRepository,
        analyses: AnalysisRepository,
    ) -> None:
        self._stocks = stocks
        self._prices = prices
        self._analyses = analyses

    async def list_runs(
        self, *, stock_id: int, page: int, page_size: int
    ) -> tuple[Stock, list[AnalysisRun], int]:
        """确认股票存在后，返回这一页批次和全部批次的数量。"""
        stock = await self._stocks.get_by_id(stock_id)
        if stock is None:
            raise AnalysisStockNotFound
        # 归档只阻止新的分析，不影响查看以前保存的批次。
        total = await self._analyses.count_runs(stock_id)
        runs = await self._analyses.list_run_page(
            stock_id=stock_id, offset=(page - 1) * page_size, limit=page_size
        )
        return stock, runs, total

    async def get_run(self, stock_id: int, run_id: int) -> AnalysisRun:
        """读取已保存的分析快照；不采集行情，也不重新计算指标。"""
        run = await self._analyses.get_run_for_stock(stock_id=stock_id, run_id=run_id)
        if run is None:
            raise AnalysisRunNotFound
        # 已归档的股票仍能查看以前保存的分析，所以这里不检查 archived_at。
        return run

    async def run(self, stock_id: int, requested_days: int) -> AnalysisRunOutcome:
        """用库中最近的指定条数计算，不在分析时访问行情网站。"""
        # 采集接口也会锁同一行股票。先拿锁再读日线，避免分析途中采集
        # 修改这些输入；锁随 get_session 管理的事务结束而释放。
        stock = await self._stocks.get_by_id_for_update(stock_id)
        if stock is None:
            raise AnalysisStockNotFound
        if stock.archived_at is not None:
            raise AnalysisStockArchived

        prices = await self._prices.list_recent(stock_id, requested_days)
        if len(prices) < requested_days:
            raise AnalysisDataInsufficient(requested_days, len(prices))

        expected = {"CN": ("qfq", "CNY"), "US": ("all", "USD")}.get(stock.market)
        basis = {(price.source, price.adjustment, price.currency) for price in prices}
        # 已存日线也可能来自旧版采集或手工修正。只用完整、同口径、
        # 已收盘的记录；否则停止分析，绝不把两种价格揉在一起评分。
        today_utc = datetime.now(timezone.utc).date()  # noqa: UP017
        if (
            expected is None
            or len(basis) != 1
            or any(price.trade_date >= today_utc for price in prices)
        ):
            raise AnalysisPriceBasisConflict
        source, adjustment, currency = basis.pop()
        if (adjustment, currency) != expected:
            raise AnalysisPriceBasisConflict

        closes = [float(price.close_price) for price in prices]
        indicators = calculate_indicators(closes)
        days: list[AnalysisDay] = []
        for price, close, indicator in zip(prices, closes, indicators):
            assessment = evaluate_trend(close, indicator)
            ma5 = _decimal(indicator.ma5, 6)
            ma20 = _decimal(indicator.ma20, 6)
            rsi14 = _decimal(indicator.rsi14, 4)
            macd = _decimal(indicator.macd, 6)
            summary = None
            if assessment is not None:
                # 指标只描述已发生的价格变化，不给出买卖建议或未来预测。
                summary = (
                    f"截至{price.trade_date}，趋势评分{assessment.score}分，"
                    f"标签为{assessment.label}；MA5={ma5}，MA20={ma20}，"
                    f"RSI14={rsi14}，MACD={macd}。"
                )
            days.append(
                AnalysisDay(
                    trade_date=price.trade_date,
                    close_price=price.close_price,
                    ma5=ma5,
                    ma20=ma20,
                    rsi14=rsi14,
                    macd=macd,
                    trend_score=assessment.score if assessment else None,
                    trend_label=assessment.label if assessment else None,
                    summary=summary,
                )
            )

        # 请求下限是 35，因此最后一天一定有完整的指标与评分。
        assert len(days) >= MIN_SCORE_BARS and days[-1].trend_score is not None
        run, created = await self._analyses.save_run(
            stock_id=stock_id,
            requested_days=requested_days,
            source=source,
            adjustment=adjustment,
            rule_version=RULE_VERSION,
            days=days,
        )
        return AnalysisRunOutcome(
            run_id=run.id,
            stock_id=stock_id,
            symbol=stock.symbol,
            requested_days=requested_days,
            start_date=days[0].trade_date,
            end_date=days[-1].trade_date,
            source=source,
            adjustment=adjustment,
            rule_version=RULE_VERSION,
            created=created,
            latest=days[-1],
        )
