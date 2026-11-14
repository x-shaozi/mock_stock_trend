"""按股票和交易日读取、保存日线，数据库会话只存在于仓储层。"""

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.daily_price import DailyPrice
from app.service.market_data import DailyBar


class PriceBasisConflict(Exception):
    """同一天已有不同来源或复权口径的数据，不能混合覆盖。"""


@dataclass(frozen=True)
class SaveCounts:
    """分别记录新增、修正和未变化的日线数量。"""

    inserted: int
    updated: int
    unchanged: int


class DailyPriceRepository:
    """负责日线的数据库读写；事务提交仍由 get_session 统一处理。"""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_recent(self, stock_id: int, days: int) -> list[DailyPrice]:
        """只从数据库读取最近几条日线，再按交易日期由早到晚返回。"""
        # 数据库先按日期倒序取最近 days 条，LIMIT 才不会把旧记录留下、
        # 把真正最新的记录漏掉。反转结果仅改变响应顺序，方便前端画时间轴。
        result = await self._session.execute(
            select(DailyPrice)
            .where(DailyPrice.stock_id == stock_id)
            .order_by(DailyPrice.trade_date.desc())
            .limit(days)
        )
        return list(reversed(result.scalars().all()))

    async def save_bars(self, stock_id: int, bars: list[DailyBar]) -> SaveCounts:
        """同日首次采集插入，内容改变时更新，完全一致时保持原记录。"""
        # 服务层已经锁住对应的股票行；同一股票的两个采集请求
        # 会在这里顺序执行，避免同时判断“这一天还没有记录”。
        result = await self._session.execute(
            select(DailyPrice).where(
                DailyPrice.stock_id == stock_id,
                DailyPrice.trade_date.in_(bar.trade_date for bar in bars),
            )
        )
        existing = {price.trade_date: price for price in result.scalars()}
        inserted = updated = unchanged = 0

        for bar in bars:
            price = existing.get(bar.trade_date)
            if price is None:
                self._session.add(
                    DailyPrice(
                        stock_id=stock_id,
                        trade_date=bar.trade_date,
                        open_price=bar.open_price,
                        high_price=bar.high_price,
                        low_price=bar.low_price,
                        close_price=bar.close_price,
                        volume=bar.volume,
                        currency=bar.currency,
                        source=bar.source,
                        adjustment=bar.adjustment,
                    )
                )
                inserted += 1
                continue

            # 同一交易日只能保留一种价格口径。来源或复权方式不同，
            # 应先由人决定如何处理旧数据，不能悄悄替换并混合计算指标。
            if (price.source, price.adjustment, price.currency) != (
                bar.source,
                bar.adjustment,
                bar.currency,
            ):
                raise PriceBasisConflict

            old_values = (
                price.open_price,
                price.high_price,
                price.low_price,
                price.close_price,
                price.volume,
            )
            new_values = (
                bar.open_price,
                bar.high_price,
                bar.low_price,
                bar.close_price,
                bar.volume,
            )
            if old_values == new_values:
                unchanged += 1
                continue
            (
                price.open_price,
                price.high_price,
                price.low_price,
                price.close_price,
                price.volume,
            ) = new_values
            # 修正旧日线时留下新的获取时间，便于排查数据何时发生变化。
            price.fetched_at = func.utc_timestamp()
            updated += 1

        # 在生成成功响应之前执行 SQL，尽早发现数据库约束和类型错误。
        await self._session.flush()
        return SaveCounts(inserted=inserted, updated=updated, unchanged=unchanged)
