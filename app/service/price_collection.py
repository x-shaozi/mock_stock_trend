"""组织一次股票日线采集：查股票、访问行情源、保存有效数据。"""

from dataclasses import dataclass

from app.repository.daily_price import DailyPriceRepository, SaveCounts
from app.repository.stock import StockRepository
from app.service.market_data import MarketDataClient


class CollectionStockNotFound(Exception):
    """请求的股票编号不在 stocks 表中。"""


class ArchivedStock(Exception):
    """已归档股票不应继续采集行情。"""


@dataclass(frozen=True)
class CollectionResult:
    """业务层提供给 HTTP 路由的采集结果。"""

    stock_id: int
    symbol: str
    counts: SaveCounts


class PriceCollectionService:
    """只组织业务流程，不直接持有数据库会话。"""

    def __init__(
        self,
        stock_repository: StockRepository,
        daily_price_repository: DailyPriceRepository,
        market_data_client: MarketDataClient,
    ) -> None:
        self._stocks = stock_repository
        self._prices = daily_price_repository
        self._market_data = market_data_client

    async def collect(self, stock_id: int, days: int) -> CollectionResult:
        """先取网络数据，再锁股票入库，避免网络等待时占用数据库行锁。"""
        stock = await self._stocks.get_by_id(stock_id)
        if stock is None:
            raise CollectionStockNotFound
        if stock.archived_at is not None:
            raise ArchivedStock

        bars = await self._market_data.fetch_daily_bars(stock, days)

        # 网络请求期间，股票可能被另一个请求归档，所以写入前在锁内
        # 再检查一次。锁也让同一股票的并发采集顺序比较与写入日线。
        locked_stock = await self._stocks.get_by_id_for_update(stock_id)
        if locked_stock is None:
            raise CollectionStockNotFound
        if locked_stock.archived_at is not None:
            raise ArchivedStock
        counts = await self._prices.save_bars(stock_id, bars)
        return CollectionResult(stock_id=stock_id, symbol=stock.symbol, counts=counts)
