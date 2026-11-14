"""不访问数据库的股票详情业务单元测试。"""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.repository.stock import StockRepository
from app.service.stock import StockNotFound, StockService


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_get_stock_includes_archived_record() -> None:
    repository = AsyncMock(spec=StockRepository)
    stock = SimpleNamespace(id=9, archived_at="2026-11-15")
    repository.get_by_id.return_value = stock
    service = StockService(repository)

    assert await service.get_stock(9) is stock
    repository.get_by_id.assert_awaited_once_with(9)


@pytest.mark.anyio
async def test_get_stock_missing_raises_business_exception() -> None:
    repository = AsyncMock(spec=StockRepository)
    repository.get_by_id.return_value = None
    service = StockService(repository)

    with pytest.raises(StockNotFound):
        await service.get_stock(999)
