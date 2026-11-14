"""查询一只股票已经保存的日线历史。"""

from app.models.daily_price import DailyPrice
from app.models.stock import Stock
from app.repository.daily_price import DailyPriceRepository
from app.repository.stock import StockRepository


class HistoryStockNotFound(Exception):
    """请求的股票编号在 stocks 表中不存在。"""


class PriceHistoryService:
    """组合股票身份与日线查询，不自行持有数据库会话。"""

    def __init__(
        self,
        stock_repository: StockRepository,
        daily_price_repository: DailyPriceRepository,
    ) -> None:
        self._stock_repository = stock_repository
        self._daily_price_repository = daily_price_repository

    async def get_history(
        self, stock_id: int, days: int
    ) -> tuple[Stock, list[DailyPrice]]:
        """股票不存在时明确报错；有股票但未采集时返回空日线。"""
        stock = await self._stock_repository.get_by_id(stock_id)
        if stock is None:
            raise HistoryStockNotFound

        # 已归档只是从正常股票列表中隐藏，历史行情仍属于这只股票。
        # 这里不调用在线数据源；想刷新行情需使用单独的采集接口。
        prices = await self._daily_price_repository.list_recent(stock_id, days)
        return stock, prices
