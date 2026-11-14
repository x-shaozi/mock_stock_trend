"""不连接 MySQL，验证股票新增、列表、归档和恢复接口的 HTTP 契约。"""

from collections.abc import Iterator
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_stock_registration_service, get_stock_service
from app.main import app
from app.service.stock import StockNotFound, StockService
from app.service.stock_catalog import StockCatalogError
from app.service.stock_registration import (
    StockAlreadyExists,
    StockNotListed,
    StockRegistrationService,
)


@pytest.fixture
def stock_service() -> Iterator[AsyncMock]:
    """用可检查调用记录的假服务替换真实依赖，避免连接 MySQL。"""
    service = AsyncMock(spec=StockService)
    app.dependency_overrides[get_stock_service] = lambda: service
    try:
        yield service
    finally:
        app.dependency_overrides.pop(get_stock_service, None)


@pytest.fixture
def registration_service() -> Iterator[AsyncMock]:
    """新增接口的路由测试只检查 HTTP 行为，不调用真实目录或数据库。"""
    service = AsyncMock(spec=StockRegistrationService)
    app.dependency_overrides[get_stock_registration_service] = lambda: service
    try:
        yield service
    finally:
        app.dependency_overrides.pop(get_stock_registration_service, None)


def test_create_stock_returns_201_and_normalized_fields(
    registration_service: AsyncMock,
) -> None:
    """路由只交给业务层市场和代码，响应使用业务层核对的名称。"""
    registration_service.register_stock.return_value = SimpleNamespace(
        id=7, symbol="688385.SH", name="复旦微电", market="CN"
    )

    with TestClient(app) as client:
        response = client.post(
            "/stocks",
            json={"symbol": " 688385.ss ", "name": "用户误填的名称", "market": "cn"},
        )

    assert response.status_code == 201
    assert response.json() == {
        "id": 7,
        "symbol": "688385.SH",
        "name": "复旦微电",
        "market": "CN",
    }
    registration_service.register_stock.assert_awaited_once_with(
        symbol="688385.SH", market="CN"
    )


def test_duplicate_stock_returns_unified_409(registration_service: AsyncMock) -> None:
    """业务层报告重复时，路由转换为项目统一的错误响应。"""
    registration_service.register_stock.side_effect = StockAlreadyExists

    with TestClient(app) as client:
        response = client.post(
            "/stocks", json={"symbol": "AAPL", "name": "Apple", "market": "US"}
        )

    assert response.status_code == 409
    assert response.json() == {
        "code": 409,
        "message": "该市场的股票代码已存在",
        "error_code": "STOCK_ALREADY_EXISTS",
    }


def test_invalid_stock_does_not_reach_service(
    registration_service: AsyncMock,
) -> None:
    """无效市场由请求模型挡住，不发送数据库写入。"""

    with TestClient(app) as client:
        response = client.post(
            "/stocks", json={"symbol": "AAPL", "name": "Apple", "market": "EU"}
        )

    assert response.status_code == 422
    assert response.json()["code"] == 422
    assert response.json()["errors"]
    registration_service.register_stock.assert_not_awaited()


def test_missing_catalog_symbol_returns_404(registration_service: AsyncMock) -> None:
    """目录中找不到完全匹配的代码时，不创建本地股票。"""
    registration_service.register_stock.side_effect = StockNotListed

    with TestClient(app) as client:
        response = client.post("/stocks", json={"symbol": "APPL", "market": "US"})

    assert response.status_code == 404
    assert response.json() == {
        "code": 404,
        "message": "股票目录中找不到该市场的代码",
        "error_code": "STOCK_NOT_LISTED",
    }


def test_catalog_failure_returns_502(registration_service: AsyncMock) -> None:
    """目录网站出错时返回可识别的来源错误。"""
    registration_service.register_stock.side_effect = StockCatalogError(
        "股票搜索服务请求超时，请稍后重试"
    )

    with TestClient(app) as client:
        response = client.post("/stocks", json={"symbol": "AAPL", "market": "US"})

    assert response.status_code == 502
    assert response.json() == {
        "code": 502,
        "message": "股票搜索服务请求超时，请稍后重试",
        "error_code": "STOCK_CATALOG_UNAVAILABLE",
    }


def test_list_stocks_returns_page_and_total(stock_service: AsyncMock) -> None:
    """列表响应同时包含股票、总条数与实际使用的分页参数。"""
    stock_service.list_stocks.return_value = (
        [SimpleNamespace(id=4, symbol="MSFT", name="Microsoft", market="US")],
        3,
    )

    with TestClient(app) as client:
        response = client.get("/stocks?page=2&page_size=1")

    assert response.status_code == 200
    assert response.json() == {
        "items": [{"id": 4, "symbol": "MSFT", "name": "Microsoft", "market": "US"}],
        "total": 3,
        "page": 2,
        "page_size": 1,
    }
    stock_service.list_stocks.assert_awaited_once_with(
        page=2, page_size=1, status="active", market=None, keyword=None
    )


def test_list_stocks_uses_default_page(stock_service: AsyncMock) -> None:
    """不传查询参数时默认请求第一页，每页二十条。"""
    stock_service.list_stocks.return_value = ([], 0)

    with TestClient(app) as client:
        response = client.get("/stocks")

    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0, "page": 1, "page_size": 20}
    stock_service.list_stocks.assert_awaited_once_with(
        page=1, page_size=20, status="active", market=None, keyword=None
    )


def test_list_stocks_can_request_archived_items(stock_service: AsyncMock) -> None:
    """选已归档时，路由把状态交给业务层，并保持原有响应格式。"""
    stock_service.list_stocks.return_value = ([], 0)

    with TestClient(app) as client:
        response = client.get("/stocks?status=archived&page_size=1")

    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0, "page": 1, "page_size": 1}
    stock_service.list_stocks.assert_awaited_once_with(
        page=1, page_size=1, status="archived", market=None, keyword=None
    )


def test_list_stocks_rejects_unknown_status(stock_service: AsyncMock) -> None:
    """不认识的查看方式直接返回 422，不访问业务层或数据库。"""
    with TestClient(app) as client:
        response = client.get("/stocks?status=deleted")

    assert response.status_code == 422
    assert response.json()["code"] == 422
    assert response.json()["errors"][0]["field"] == "query.status"
    stock_service.list_stocks.assert_not_awaited()


@pytest.mark.parametrize("query", ["page=0", "page_size=0", "page_size=101"])
def test_list_stocks_rejects_invalid_pagination(
    stock_service: AsyncMock, query: str
) -> None:
    """无效分页由 Pydantic 拦截，不能进入业务层查询数据库。"""
    with TestClient(app) as client:
        response = client.get(f"/stocks?{query}")

    assert response.status_code == 422
    assert response.json()["code"] == 422
    assert response.json()["errors"]
    stock_service.list_stocks.assert_not_awaited()


def test_archive_stock_returns_200_and_identity(stock_service: AsyncMock) -> None:
    """路由只传编号给业务层，成功后告诉用户归档的是哪只股票。"""
    stock_service.archive_stock.return_value = SimpleNamespace(id=4, symbol="MSFT")

    with TestClient(app) as client:
        response = client.patch("/stocks/4/archive")

    assert response.status_code == 200
    assert response.json() == {"id": 4, "symbol": "MSFT", "status": "archived"}
    stock_service.archive_stock.assert_awaited_once_with(4)


def test_archive_missing_stock_returns_unified_404(stock_service: AsyncMock) -> None:
    """业务层找不到股票时，路由使用项目统一的 404 格式。"""
    stock_service.archive_stock.side_effect = StockNotFound

    with TestClient(app) as client:
        response = client.patch("/stocks/999999/archive")

    assert response.status_code == 404
    assert response.json() == {
        "code": 404,
        "message": "股票不存在",
        "error_code": "STOCK_NOT_FOUND",
    }


def test_archive_stock_rejects_invalid_id(stock_service: AsyncMock) -> None:
    """股票编号必须大于零，错误编号不会进入业务层。"""
    with TestClient(app) as client:
        response = client.patch("/stocks/0/archive")

    assert response.status_code == 422
    assert response.json()["errors"][0]["field"] == "path.stock_id"
    stock_service.archive_stock.assert_not_awaited()


def test_restore_stock_returns_200_and_identity(stock_service: AsyncMock) -> None:
    """恢复成功后返回股票编号、代码和正常状态。"""
    stock_service.restore_stock.return_value = SimpleNamespace(id=4, symbol="MSFT")

    with TestClient(app) as client:
        response = client.patch("/stocks/4/restore")

    assert response.status_code == 200
    assert response.json() == {"id": 4, "symbol": "MSFT", "status": "active"}
    stock_service.restore_stock.assert_awaited_once_with(4)


def test_restore_missing_stock_returns_unified_404(stock_service: AsyncMock) -> None:
    """找不到股票时保持项目统一的 404 响应。"""
    stock_service.restore_stock.side_effect = StockNotFound

    with TestClient(app) as client:
        response = client.patch("/stocks/999999/restore")

    assert response.status_code == 404
    assert response.json() == {
        "code": 404,
        "message": "股票不存在",
        "error_code": "STOCK_NOT_FOUND",
    }


def test_restore_stock_rejects_invalid_id(stock_service: AsyncMock) -> None:
    """编号不合法时不调用业务层。"""
    with TestClient(app) as client:
        response = client.patch("/stocks/0/restore")

    assert response.status_code == 422
    assert response.json()["errors"][0]["field"] == "path.stock_id"
    stock_service.restore_stock.assert_not_awaited()


def test_get_stock_detail_includes_status_and_utc_timestamps(
    stock_service: AsyncMock,
) -> None:
    """页面刷新能直接按 id 读取状态，UTC 时间使用 Z 后缀。"""
    from datetime import datetime

    stock_service.get_stock.return_value = SimpleNamespace(
        id=7,
        symbol="AAPL",
        name="Apple Inc.",
        market="US",
        created_at=datetime(2026, 11, 14, 8, 30),
        archived_at=None,
    )
    with TestClient(app) as client:
        response = client.get("/stocks/7")

    assert response.status_code == 200
    assert response.json() == {
        "id": 7,
        "symbol": "AAPL",
        "name": "Apple Inc.",
        "market": "US",
        "status": "active",
        "created_at": "2026-11-14T08:30:00Z",
        "archived_at": None,
    }
    stock_service.get_stock.assert_awaited_once_with(7)


def test_get_archived_stock_is_still_visible(stock_service: AsyncMock) -> None:
    """归档股票保留独立详情与归档时间。"""
    from datetime import datetime

    stock_service.get_stock.return_value = SimpleNamespace(
        id=7,
        symbol="AAPL",
        name="Apple Inc.",
        market="US",
        created_at=datetime(2026, 11, 14, 8, 30),
        archived_at=datetime(2026, 11, 15, 6, 0),
    )
    with TestClient(app) as client:
        response = client.get("/stocks/7")

    assert response.status_code == 200
    assert response.json()["status"] == "archived"
    assert response.json()["archived_at"] == "2026-11-15T06:00:00Z"


def test_get_stock_missing_and_bad_id(stock_service: AsyncMock) -> None:
    """不存在报业务 404，非法 path 先被框架校验为 422。"""
    stock_service.get_stock.side_effect = StockNotFound
    with TestClient(app) as client:
        missing = client.get("/stocks/999999")
        invalid = client.get("/stocks/0")

    assert missing.status_code == 404
    assert missing.json() == {
        "code": 404,
        "message": "股票不存在",
        "error_code": "STOCK_NOT_FOUND",
    }
    assert invalid.status_code == 422
    assert invalid.json()["errors"][0]["field"] == "path.stock_id"
    stock_service.get_stock.assert_awaited_once_with(999999)


def test_list_stocks_passes_optional_filters(stock_service: AsyncMock) -> None:
    """输入市场和关键词后，Router 只转发经过 Pydantic 规范化的数据。"""
    stock_service.list_stocks.return_value = ([], 0)
    with TestClient(app) as client:
        response = client.get("/stocks?market=us&keyword=%20aapl%20&page=2&page_size=5")

    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0, "page": 2, "page_size": 5}
    stock_service.list_stocks.assert_awaited_once_with(
        page=2, page_size=5, status="active", market="US", keyword="aapl"
    )


def test_list_stocks_blank_keyword_is_ignored(stock_service: AsyncMock) -> None:
    """只有空格的搜索输入等同不填写关键词。"""
    stock_service.list_stocks.return_value = ([], 0)
    with TestClient(app) as client:
        response = client.get("/stocks?keyword=%20%20")

    assert response.status_code == 200
    stock_service.list_stocks.assert_awaited_once_with(
        page=1, page_size=20, status="active", market=None, keyword=None
    )


@pytest.mark.parametrize("query", ["market=EU", "keyword=" + "x" * 51])
def test_list_stocks_rejects_bad_filters(stock_service: AsyncMock, query: str) -> None:
    """无效市场与超长关键词在执行 SQL 前返回 422。"""
    with TestClient(app) as client:
        response = client.get(f"/stocks?{query}")
    assert response.status_code == 422
    assert response.json()["code"] == 422
    stock_service.list_stocks.assert_not_awaited()
