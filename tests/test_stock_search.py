"""用模拟网站响应测试搜索规则；不依赖外网、密钥或 MySQL。"""

import json

import httpx
import pytest

from app.service.stock_catalog import StockCatalogClient, StockCatalogError
from app.service.stock_search import StockSearchService


@pytest.fixture
def anyio_backend() -> str:
    """异步用例统一使用项目运行时的 asyncio。"""
    return "asyncio"


@pytest.mark.anyio
async def test_cn_name_search_keeps_only_shenzhen_and_shanghai_stocks() -> None:
    """腾讯响应含指数、基金和股票时，用户只能选 A 股股票。"""
    body = (
        "sh~000001~上证指数~szzs~ZS^"
        "sz~000001~平安银行~payh~GP-A^"
        "jj~000001~华夏基金~hxjj~KJ"
    )

    def respond(request: httpx.Request) -> httpx.Response:
        assert request.url.params["q"] == "000001"
        return httpx.Response(200, text=f"v_hint={json.dumps(body)}")

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        service = StockSearchService(StockCatalogClient(client, ""))
        results = await service.search(query="000001.SZ", market="CN")

    assert [(item.symbol, item.name, item.exchange) for item in results] == [
        ("000001.SZ", "平安银行", "SZSE")
    ]


@pytest.mark.anyio
async def test_cn_search_handles_real_unicode_escape_and_no_match() -> None:
    """腾讯返回 Unicode 转义的中文名称，也可能返回 N 表示无结果。"""
    responses = iter(
        [
            httpx.Response(
                200,
                text='v_hint="sh~688385~\\u590d\\u65e6\\u5fae\\u7535~fdwd~GP-A-KCB"',
            ),
            httpx.Response(200, text='v_hint="N";'),
        ]
    )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: next(responses))
    ) as client:
        catalog = StockCatalogClient(client, "")
        first = await catalog.search_cn("688385")
        second = await catalog.search_cn("不存在")

    assert [(item.symbol, item.name, item.exchange) for item in first] == [
        ("688385.SH", "复旦微电", "SSE")
    ]
    assert second == []


@pytest.mark.anyio
async def test_us_name_search_filters_other_markets_and_duplicate_exchange() -> None:
    """英文名称搜索可能先返回外国证券；美国同一代码也会重复。"""
    rows = [
        {
            "symbol": "4MSFT",
            "instrument_name": "MICROSOFT",
            "exchange": "MTA",
            "country": "Italy",
            "instrument_type": "Common Stock",
        },
        {
            "symbol": "MSFT",
            "instrument_name": "Microsoft Corporation",
            "exchange": "NASDAQ",
            "country": "United States",
            "instrument_type": "Common Stock",
        },
        {
            "symbol": "MSFT",
            "instrument_name": "Microsoft Corporation",
            "exchange": "IEX",
            "country": "United States",
            "instrument_type": "Common Stock",
        },
        {
            "symbol": "MSFT3",
            "instrument_name": "Microsoft Tracker",
            "exchange": "NASDAQ",
            "country": "United States",
            "instrument_type": "ETF",
        },
    ]

    def respond(request: httpx.Request) -> httpx.Response:
        assert request.url.params["symbol"] == "Microsoft"
        assert request.url.params["outputsize"] == "120"
        assert request.url.params["apikey"] == "test-key"
        return httpx.Response(200, json={"status": "ok", "data": rows})

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        service = StockSearchService(StockCatalogClient(client, "test-key"))
        results = await service.search(query="Microsoft", market="US")

    assert [(item.symbol, item.market, item.exchange) for item in results] == [
        ("MSFT", "US", "NASDAQ")
    ]


@pytest.mark.anyio
async def test_missing_us_key_fails_without_request() -> None:
    """没有密钥时明确报错，不发出无法授权的网络请求。"""
    called = False

    def respond(request: httpx.Request) -> httpx.Response:
        nonlocal called
        called = True
        return httpx.Response(200, json={})

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        with pytest.raises(StockCatalogError, match="TWELVE_DATA_API_KEY"):
            await StockCatalogClient(client, "").search_us("MSFT")

    assert called is False


@pytest.mark.anyio
async def test_upstream_error_does_not_include_api_key() -> None:
    """上游限流时，错误消息中不能出现请求地址或密钥。"""
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(429))
    ) as client:
        with pytest.raises(StockCatalogError) as error:
            await StockCatalogClient(client, "secret-for-test").search_us("MSFT")

    assert "过于频繁" in str(error.value)
    assert "secret-for-test" not in str(error.value)


@pytest.mark.anyio
async def test_broken_cn_response_raises_source_error() -> None:
    """来源格式变动时明确失败，不能把空结果误报成没有股票。"""
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, text="oops"))
    ) as client:
        with pytest.raises(StockCatalogError, match="无法识别"):
            await StockCatalogClient(client, "").search_cn("688385")
