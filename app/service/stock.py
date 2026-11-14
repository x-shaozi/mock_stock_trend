"""处理股票列表、归档与恢复的业务流程。"""

from app.models.stock import Stock
from app.repository.stock import StockRepository


class StockNotFound(Exception):
    """按编号查找时没有这只股票。"""


class StockService:
    """处理股票业务流程，不管理数据库会话。"""

    def __init__(self, repository: StockRepository) -> None:
        self._repository = repository

    async def list_stocks(
        self, *, page: int, page_size: int, status: str
    ) -> tuple[list[Stock], int]:
        """计算页码，并让总数和当前页使用同一种股票状态。"""
        offset = (page - 1) * page_size
        total = await self._repository.count(status=status)
        stocks = await self._repository.list_page(
            offset=offset, limit=page_size, status=status
        )
        return stocks, total

    async def archive_stock(self, stock_id: int) -> Stock:
        """把股票标记为已归档；不存在时交给路由返回 404。"""
        stock = await self._repository.archive_by_id(stock_id)
        if stock is None:
            raise StockNotFound
        return stock

    async def restore_stock(self, stock_id: int) -> Stock:
        """把股票恢复为正常；不存在时交给路由返回 404。"""
        stock = await self._repository.restore_by_id(stock_id)
        if stock is None:
            raise StockNotFound
        return stock
