"""不连接数据库或外网，验证采集接口的状态码与响应格式。"""

from collections.abc import Iterator
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_price_collection_service
from app.main import app
from app.repository.daily_price import PriceBasisConflict, SaveCounts
from app.service.market_data import MarketDataError
from app.service.price_collection import (
    ArchivedStock,
    CollectionResult,
    CollectionStockNotFound,
    PriceCollectionService,
)


@pytest.fixture
def collection_service() -> Iterator[AsyncMock]:
    """替换整个服务，确保接口契约测试不会接触真实资源。"""
    service = AsyncMock(spec=PriceCollectionService)
    app.dependency_overrides[get_price_collection_service] = lambda: service
    try:
        yield service
    finally:
        app.dependency_overrides.pop(get_price_collection_service, None)


def test_collect_returns_counts_and_default_days(collection_service: AsyncMock) -> None:
    """默认采集九十条，并返回写入、修正和未变化条数。"""
    collection_service.collect.return_value = CollectionResult(
        stock_id=4, symbol="AAPL", counts=SaveCounts(89, 1, 0)
    )
    with TestClient(app) as client:
        response = client.post("/stocks/4/prices/collect")

    assert response.status_code == 200
    assert response.json() == {
        "stock_id": 4,
        "symbol": "AAPL",
        "inserted": 89,
        "updated": 1,
        "unchanged": 0,
    }
    collection_service.collect.assert_awaited_once_with(4, 90)


@pytest.mark.parametrize(
    "path",
    [
        "/stocks/0/prices/collect",
        "/stocks/4/prices/collect?days=0",
        "/stocks/4/prices/collect?days=261",
    ],
)
def test_invalid_parameters_return_422_without_calling_service(
    collection_service: AsyncMock, path: str
) -> None:
    """非法编号和天数先由 Pydantic 拦住，不发网络或数据库请求。"""
    with TestClient(app) as client:
        response = client.post(path)
    assert response.status_code == 422
    assert response.json()["code"] == 422
    collection_service.collect.assert_not_awaited()


@pytest.mark.parametrize(
    ("error", "status", "message"),
    [
        (CollectionStockNotFound(), 404, "股票不存在"),
        (ArchivedStock(), 409, "已归档股票不可采集行情"),
        (PriceBasisConflict(), 409, "已有不同行情口径，不能覆盖"),
        (
            MarketDataError("行情网站请求失败，请稍后重试"),
            502,
            "行情网站请求失败，请稍后重试",
        ),
    ],
)
def test_collect_business_errors_use_common_response(
    collection_service: AsyncMock, error: Exception, status: int, message: str
) -> None:
    """业务异常统一转换为 code 与 message，不泄漏异常堆栈。"""
    collection_service.collect.side_effect = error
    with TestClient(app) as client:
        response = client.post("/stocks/4/prices/collect?days=2")
    assert response.status_code == status
    assert response.json() == {"code": status, "message": message}
