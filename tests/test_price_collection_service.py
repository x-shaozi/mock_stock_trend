"""直接测试采集业务流程，重点检查请求行情期间股票状态发生变化的情况。"""

from datetime import date, datetime
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from app.models.stock import Stock
from app.repository.daily_price import DailyPriceRepository, SaveCounts
from app.repository.stock import StockRepository
from app.service.market_data import DailyBar, MarketDataClient
from app.service.price_collection import (
    ArchivedStock,
    CollectionStockNotFound,
    PriceCollectionService,
)


@pytest.fixture
def anyio_backend() -> str:
    """业务方法是异步函数；与项目其他异步测试一样使用 asyncio。"""
    return "asyncio"


@pytest.fixture
def active_stock() -> Stock:
    """只在内存中创建股票对象，不向 MySQL 写入记录。"""
    return Stock(
        id=10,
        symbol="600941.SH",
        name="中国移动",
        market="CN",
        archived_at=None,
    )


@pytest.fixture
def daily_bar() -> DailyBar:
    """假行情源返回的一条完整日线；测试不会访问真实网站。"""
    return DailyBar(
        trade_date=date(2026, 11, 13),
        open_price=Decimal("98.000000"),
        high_price=Decimal("101.720000"),
        low_price=Decimal("97.790000"),
        close_price=Decimal("101.460000"),
        volume=18_347_500,
        currency="CNY",
        source="tencent",
        adjustment="qfq",
    )


def build_service(
    stock: Stock | None,
) -> tuple[PriceCollectionService, AsyncMock, AsyncMock, AsyncMock]:
    """用可检查调用次数的替身代替数据库仓储和外部行情客户端。"""
    stocks = AsyncMock(spec=StockRepository)
    prices = AsyncMock(spec=DailyPriceRepository)
    market_data = AsyncMock(spec=MarketDataClient)
    stocks.get_by_id.return_value = stock
    return (
        PriceCollectionService(stocks, prices, market_data),
        stocks,
        prices,
        market_data,
    )


@pytest.mark.anyio
async def test_collect_saves_bars_after_stock_is_checked_again(
    active_stock: Stock, daily_bar: DailyBar
) -> None:
    """股票一直正常时，第二次检查后才保存日线，并返回真实保存条数。"""
    service, stocks, prices, market_data = build_service(active_stock)
    market_data.fetch_daily_bars.return_value = [daily_bar]
    stocks.get_by_id_for_update.return_value = active_stock
    prices.save_bars.return_value = SaveCounts(inserted=1, updated=0, unchanged=0)

    result = await service.collect(stock_id=10, days=1)

    assert (result.stock_id, result.symbol, result.counts.inserted) == (
        10,
        "600941.SH",
        1,
    )
    market_data.fetch_daily_bars.assert_awaited_once_with(active_stock, 1)
    stocks.get_by_id_for_update.assert_awaited_once_with(10)
    prices.save_bars.assert_awaited_once_with(10, [daily_bar])


@pytest.mark.anyio
async def test_collect_does_not_save_when_stock_is_archived_during_fetch(
    active_stock: Stock, daily_bar: DailyBar
) -> None:
    """网络等待期间股票被归档时，取回日线也不能再写入数据库。"""
    service, stocks, prices, market_data = build_service(active_stock)

    async def finish_fetch(stock: Stock, days: int) -> list[DailyBar]:
        """模拟行情返回时，下一次加锁查询已能看见归档后的状态。"""
        assert (stock.id, days) == (10, 1)
        stocks.get_by_id_for_update.return_value = Stock(
            id=10,
            symbol="600941.SH",
            name="中国移动",
            market="CN",
            archived_at=datetime(2026, 11, 15),
        )
        return [daily_bar]

    market_data.fetch_daily_bars.side_effect = finish_fetch

    with pytest.raises(ArchivedStock):
        await service.collect(stock_id=10, days=1)

    market_data.fetch_daily_bars.assert_awaited_once_with(active_stock, 1)
    stocks.get_by_id_for_update.assert_awaited_once_with(10)
    prices.save_bars.assert_not_awaited()


@pytest.mark.anyio
async def test_collect_does_not_save_when_stock_disappears_during_fetch(
    active_stock: Stock, daily_bar: DailyBar
) -> None:
    """网络等待期间股票被删除时，不会产生没有所属股票的日线。"""
    service, stocks, prices, market_data = build_service(active_stock)

    async def finish_fetch(stock: Stock, days: int) -> list[DailyBar]:
        """模拟行情返回时，加锁查询已找不到原来的股票。"""
        assert (stock.id, days) == (10, 1)
        stocks.get_by_id_for_update.return_value = None
        return [daily_bar]

    market_data.fetch_daily_bars.side_effect = finish_fetch

    with pytest.raises(CollectionStockNotFound):
        await service.collect(stock_id=10, days=1)

    market_data.fetch_daily_bars.assert_awaited_once_with(active_stock, 1)
    stocks.get_by_id_for_update.assert_awaited_once_with(10)
    prices.save_bars.assert_not_awaited()


@pytest.mark.anyio
async def test_collect_missing_stock_does_not_request_market_data() -> None:
    """开始时就找不到股票，应立即停止，不浪费行情接口调用额度。"""
    service, stocks, prices, market_data = build_service(None)

    with pytest.raises(CollectionStockNotFound):
        await service.collect(stock_id=10, days=1)

    stocks.get_by_id.assert_awaited_once_with(10)
    market_data.fetch_daily_bars.assert_not_awaited()
    stocks.get_by_id_for_update.assert_not_awaited()
    prices.save_bars.assert_not_awaited()
