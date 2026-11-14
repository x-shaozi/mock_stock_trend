"""验证搜索接口的参数、响应和统一错误格式。"""

from collections.abc import Iterator
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_stock_search_service
from app.main import app
from app.service.stock_catalog import StockCatalogError
from app.service.stock_search import StockSearchService


@pytest.fixture
def search_service() -> Iterator[AsyncMock]:
    """替换外部搜索服务，测试 HTTP 规则时不访问真实网站。"""
    service = AsyncMock(spec=StockSearchService)
    app.dependency_overrides[get_stock_search_service] = lambda: service
    try:
        yield service
    finally:
        app.dependency_overrides.pop(get_stock_search_service, None)


def test_search_returns_candidates_without_database_id(
    search_service: AsyncMock,
) -> None:
    """候选项没有 stocks.id；选中后还需另行调用新增接口。"""
    search_service.search.return_value = [
        SimpleNamespace(
            symbol="688385.SH", name="复旦微电", market="CN", exchange="SSE"
        )
    ]

    with TestClient(app) as client:
        response = client.get("/stocks/search?market=cn&query=688385.SH")

    assert response.status_code == 200
    assert response.json() == {
        "items": [
            {
                "symbol": "688385.SH",
                "name": "复旦微电",
                "market": "CN",
                "exchange": "SSE",
            }
        ]
    }
    search_service.search.assert_awaited_once_with(query="688385.SH", market="CN")


def test_search_without_match_returns_empty_list(search_service: AsyncMock) -> None:
    """有效搜索却没有匹配项应是 200 和空列表。"""
    search_service.search.return_value = []

    with TestClient(app) as client:
        response = client.get("/stocks/search?market=US&query=nosuchsymbol")

    assert response.status_code == 200
    assert response.json() == {"items": []}


@pytest.mark.parametrize(
    "query",
    ["market=EU&query=MSFT", "market=US&query=%20%20", "query=MSFT", "market=US"],
)
def test_search_rejects_invalid_input(search_service: AsyncMock, query: str) -> None:
    """市场或搜索词缺失、非法时，在访问数据源前返回 422。"""
    with TestClient(app) as client:
        response = client.get(f"/stocks/search?{query}")

    assert response.status_code == 422
    assert response.json()["code"] == 422
    search_service.search.assert_not_awaited()


def test_search_source_failure_returns_502(search_service: AsyncMock) -> None:
    """外部服务失败要保留统一错误结构，不返回假候选。"""
    search_service.search.side_effect = StockCatalogError(
        "股票搜索服务请求超时，请稍后重试"
    )

    with TestClient(app) as client:
        response = client.get("/stocks/search?market=US&query=MSFT")

    assert response.status_code == 502
    assert response.json() == {
        "code": 502,
        "message": "股票搜索服务请求超时，请稍后重试",
        "error_code": "STOCK_CATALOG_UNAVAILABLE",
    }
