"""不连接数据库，验证已存日线查询接口的 HTTP 契约。"""

from collections.abc import Iterator
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_price_history_service
from app.main import app
from app.service.price_history import HistoryStockNotFound, PriceHistoryService


@pytest.fixture
def history_service() -> Iterator[AsyncMock]:
    """以假业务服务替换真实依赖，只检查 HTTP 参数和响应。"""
    service = AsyncMock(spec=PriceHistoryService)
    app.dependency_overrides[get_price_history_service] = lambda: service
    try:
        yield service
    finally:
        app.dependency_overrides.pop(get_price_history_service, None)


def test_price_history_returns_decimal_strings_and_default_days(
    history_service: AsyncMock,
) -> None:
    """价格不能变成浮点数；没传 days 时使用最近 90 个交易日。"""
    history_service.get_history.return_value = (
        SimpleNamespace(id=4, symbol="MSFT", market="US"),
        [
            SimpleNamespace(
                trade_date=date(2026, 11, 13),
                open_price=Decimal("410.100000"),
                high_price=Decimal("412.200000"),
                low_price=Decimal("409.500000"),
                close_price=Decimal("411.300000"),
                volume=1_000_000,
                currency="USD",
                source="twelvedata",
                adjustment="none",
            )
        ],
    )

    with TestClient(app) as client:
        response = client.get("/stocks/4/prices")

    assert response.status_code == 200
    assert response.json() == {
        "stock_id": 4,
        "symbol": "MSFT",
        "market": "US",
        "items": [
            {
                "trade_date": "2026-11-13",
                "open_price": "410.100000",
                "high_price": "412.200000",
                "low_price": "409.500000",
                "close_price": "411.300000",
                "volume": 1_000_000,
                "currency": "USD",
                "source": "twelvedata",
                "adjustment": "none",
            }
        ],
    }
    history_service.get_history.assert_awaited_once_with(4, 90)


def test_price_history_without_saved_bars_is_200(history_service: AsyncMock) -> None:
    """有这只股票但尚未采集，明确返回空列表。"""
    history_service.get_history.return_value = (
        SimpleNamespace(id=8, symbol="AAPL", market="US"),
        [],
    )

    with TestClient(app) as client:
        response = client.get("/stocks/8/prices?days=5")

    assert response.status_code == 200
    assert response.json() == {
        "stock_id": 8,
        "symbol": "AAPL",
        "market": "US",
        "items": [],
    }
    history_service.get_history.assert_awaited_once_with(8, 5)


def test_unknown_stock_returns_404(history_service: AsyncMock) -> None:
    """编号不存在时返回统一错误，不把它误当作没有行情。"""
    history_service.get_history.side_effect = HistoryStockNotFound

    with TestClient(app) as client:
        response = client.get("/stocks/99999999/prices")

    assert response.status_code == 404
    assert response.json() == {"code": 404, "message": "股票不存在"}


@pytest.mark.parametrize(
    "path",
    ["/stocks/0/prices", "/stocks/4/prices?days=0", "/stocks/4/prices?days=261"],
)
def test_invalid_history_query_returns_422_before_service(
    history_service: AsyncMock, path: str
) -> None:
    """无效编号或天数应直接被 FastAPI 拦下。"""
    with TestClient(app) as client:
        response = client.get(path)

    assert response.status_code == 422
    assert response.json()["code"] == 422
    assert response.json()["errors"]
    history_service.get_history.assert_not_awaited()
