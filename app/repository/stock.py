"""股票基础信息的数据库操作。"""

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from app.models.stock import Stock


class StockRepository:
    """封装股票表操作；只有仓储持有数据库会话。"""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, stock_id: int) -> Stock | None:
        """采集前先确认股票存在，避免为不存在的编号请求外部行情。"""
        result = await self._session.execute(select(Stock).where(Stock.id == stock_id))
        return result.scalar_one_or_none()

    async def get_by_market_symbol(self, *, market: str, symbol: str) -> Stock | None:
        """按唯一的市场和代码查找，包括已归档的记录。"""
        result = await self._session.execute(
            select(Stock).where(Stock.market == market, Stock.symbol == symbol)
        )
        return result.scalar_one_or_none()

    async def get_by_id_for_update(self, stock_id: int) -> Stock | None:
        """在写日线前锁住股票行，使同一股票的并发采集依次入库。"""
        result = await self._session.execute(
            # 本次会话此前已读取过该股票。重新从数据库填充字段，
            # 才能看到网络等待期间其他请求是否把它归档。
            select(Stock)
            .where(Stock.id == stock_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return result.scalar_one_or_none()

    async def insert(self, stock: Stock) -> Stock:
        """插入股票，并在返回前让 MySQL 执行 INSERT。"""
        self._session.add(stock)
        # flush 会发送 INSERT，但不会提交事务。此时可取得自增 id，
        # 也能在返回 HTTP 201 之前发现联合唯一约束的冲突。
        await self._session.flush()
        return stock

    @staticmethod
    def _status_condition(status: str) -> ColumnElement[bool]:
        """把“正常／已归档”转成数据库能执行的筛选条件。"""
        # 归档时间为空就是正常；有归档时间就是已归档。
        # count 和 list_page 共用这里，避免列表内容与 total 口径不同。
        if status == "active":
            return Stock.archived_at.is_(None)
        if status == "archived":
            return Stock.archived_at.is_not(None)
        raise ValueError(f"不支持的股票状态：{status}")

    async def count(self, *, status: str) -> int:
        """只统计所选状态的股票，作为当前列表的 total。"""
        statement = (
            select(func.count())
            .select_from(Stock)
            .where(self._status_condition(status))
        )
        result = await self._session.execute(statement)
        return result.scalar_one()

    async def list_page(self, *, offset: int, limit: int, status: str) -> list[Stock]:
        """按状态取一页股票，同一状态中仍让较新的记录排在前面。"""
        # id 是自增主键；显式排序可让翻页结果有确定的顺序。
        statement = (
            select(Stock)
            .where(self._status_condition(status))
            .order_by(Stock.id.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self._session.execute(statement)
        return list(result.scalars().all())

    async def archive_by_id(self, stock_id: int) -> Stock | None:
        """首次归档时写入 UTC 时间，再读取该股票；不存在则返回 None。"""
        # 只更新还未归档的记录。重复请求不会重写原来的归档时间。
        # 若两个请求同时归档，数据库会串行处理同一行的更新条件。
        # UTC_TIMESTAMP() 由 MySQL 产生当前 UTC 时间；连接的会话时区也已设为 UTC。
        statement = (
            update(Stock)
            .where(Stock.id == stock_id, Stock.archived_at.is_(None))
            .values(archived_at=func.utc_timestamp())
        )
        await self._session.execute(statement)

        # 无论这次是否实际更新，都读取最终状态：
        # 找不到返回 None；已归档则返回原记录供路由生成同样的成功响应。
        result = await self._session.execute(select(Stock).where(Stock.id == stock_id))
        return result.scalar_one_or_none()

    async def restore_by_id(self, stock_id: int) -> Stock | None:
        """清除归档时间，让股票回到正常列表；不存在则返回 None。"""
        # 只有已归档记录需要更新。重复恢复不会改动股票的其他字段。
        statement = (
            update(Stock)
            .where(Stock.id == stock_id, Stock.archived_at.is_not(None))
            .values(archived_at=None)
        )
        await self._session.execute(statement)

        # 返回数据库中的最终状态，供业务层区分“股票不存在”和“恢复成功”。
        result = await self._session.execute(select(Stock).where(Stock.id == stock_id))
        return result.scalar_one_or_none()
