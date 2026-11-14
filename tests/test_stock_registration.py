"""验证选中股票后的业务规则，不依赖真实 MySQL 或行情网站。"""

from unittest.mock import AsyncMock

import pytest
from sqlalchemy.exc import IntegrityError

from app.repository.stock import StockRepository
from app.service.stock_catalog import StockCandidate, StockCatalogError
from app.service.stock_registration import (
    StockAlreadyExists,
    StockNotListed,
    StockRegistrationService,
)
from app.service.stock_search import StockSearchService


@pytest.fixture
def anyio_backend() -> str:
    """业务层异步测试使用 asyncio。"""
    return "asyncio"


@pytest.mark.anyio
async def test_registration_uses_exact_candidate_and_catalog_name() -> None:
    """相似代码不能代替用户选中的代码，名称必须来自精确匹配项。"""
    repository = AsyncMock(spec=StockRepository)
    repository.get_by_market_symbol.return_value = None
    repository.insert.side_effect = lambda stock: stock
    search = AsyncMock(spec=StockSearchService)
    search.search.return_value = [
        StockCandidate("APPLF", "Another Company", "US", "OTC"),
        StockCandidate("AAPL", "Apple Inc.", "US", "NASDAQ"),
    ]

    stock = await StockRegistrationService(repository, search).register_stock(
        symbol="AAPL", market="US"
    )

    assert (stock.symbol, stock.name, stock.market) == ("AAPL", "Apple Inc.", "US")
    search.search.assert_awaited_once_with(query="AAPL", market="US")
    repository.insert.assert_awaited_once()


@pytest.mark.anyio
async def test_registration_rejects_only_similar_candidates() -> None:
    """输入 APPL 时即使找到 APPLF，也不能把它当成同一只股票。"""
    repository = AsyncMock(spec=StockRepository)
    repository.get_by_market_symbol.return_value = None
    search = AsyncMock(spec=StockSearchService)
    search.search.return_value = [StockCandidate("APPLF", "AlphaPolis", "US", "OTC")]

    with pytest.raises(StockNotListed):
        await StockRegistrationService(repository, search).register_stock(
            symbol="APPL", market="US"
        )

    repository.insert.assert_not_awaited()


@pytest.mark.anyio
async def test_existing_stock_skips_external_search() -> None:
    """本地已追踪的股票直接报告冲突，不消耗数据源调用次数。"""
    repository = AsyncMock(spec=StockRepository)
    repository.get_by_market_symbol.return_value = object()
    search = AsyncMock(spec=StockSearchService)

    with pytest.raises(StockAlreadyExists):
        await StockRegistrationService(repository, search).register_stock(
            symbol="AAPL", market="US"
        )

    search.search.assert_not_awaited()
    repository.insert.assert_not_awaited()


@pytest.mark.anyio
async def test_unique_constraint_catches_concurrent_duplicate() -> None:
    """两次请求同时通过预查询时，数据库重复键仍须转换成 409 业务错误。"""
    repository = AsyncMock(spec=StockRepository)
    repository.get_by_market_symbol.return_value = None
    repository.insert.side_effect = IntegrityError(
        "INSERT INTO stocks ...", {}, Exception(1062, "duplicate")
    )
    search = AsyncMock(spec=StockSearchService)
    search.search.return_value = [StockCandidate("AAPL", "Apple", "US", "NASDAQ")]

    with pytest.raises(StockAlreadyExists):
        await StockRegistrationService(repository, search).register_stock(
            symbol="AAPL", market="US"
        )


@pytest.mark.anyio
async def test_catalog_failure_does_not_write_stock() -> None:
    """外部目录出错时保留 502 原因，不应创建半截股票。"""
    repository = AsyncMock(spec=StockRepository)
    repository.get_by_market_symbol.return_value = None
    search = AsyncMock(spec=StockSearchService)
    search.search.side_effect = StockCatalogError("股票搜索服务请求超时")

    with pytest.raises(StockCatalogError, match="超时"):
        await StockRegistrationService(repository, search).register_stock(
            symbol="AAPL", market="US"
        )

    repository.insert.assert_not_awaited()
