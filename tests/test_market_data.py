"""用假 HTTP 响应验证两种行情源的解析，不依赖外网或个人密钥。"""

import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import httpx
import pytest

from app.models.stock import Stock
from app.service.market_data import MarketDataClient, MarketDataError


@pytest.fixture
def anyio_backend() -> str:
    """本项目的异步测试只运行 asyncio 后端。"""
    return "asyncio"


def _cn_response(symbol: str, rows: list[list[str]]) -> httpx.Response:
    """模拟腾讯前复权日线在 JSON 前加变量名的真实响应形式。"""
    payload = {"code": 0, "data": {symbol: {"qfqday": rows}}}
    return httpx.Response(200, text=f"kline_day={json.dumps(payload)}")


@pytest.mark.anyio
async def test_cn_field_order_and_science_board_volume() -> None:
    """腾讯把收盘放在最高前；科创板成交量本身就是股。"""

    def respond(request: httpx.Request) -> httpx.Response:
        assert request.url.params["param"] == "sh688385,day,,,640,qfq"
        return _cn_response(
            "sh688385",
            [["2026-11-12", "53.100", "52.240", "54.310", "52.060", "15725737"]],
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http_client:
        bars = await MarketDataClient(http_client, "").fetch_daily_bars(
            Stock(symbol="688385.SH", market="CN"), 1
        )

    assert len(bars) == 1
    assert bars[0].open_price == Decimal("53.100000")
    assert bars[0].close_price == Decimal("52.240000")
    assert bars[0].high_price == Decimal("54.310000")
    assert bars[0].low_price == Decimal("52.060000")
    assert bars[0].volume == 15_725_737
    assert (bars[0].currency, bars[0].source, bars[0].adjustment) == (
        "CNY",
        "tencent",
        "qfq",
    )


@pytest.mark.anyio
async def test_cn_shenzhen_volume_is_converted_from_lots_to_shares() -> None:
    """深市返回的是手；一手按一百股换算后才能入库。"""

    def respond(request: httpx.Request) -> httpx.Response:
        assert request.url.params["param"] == "sz000001,day,,,640,qfq"
        return _cn_response(
            "sz000001", [["2026-11-12", "10", "11", "12", "9", "1082721"]]
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http_client:
        bars = await MarketDataClient(http_client, "").fetch_daily_bars(
            Stock(symbol="000001.SZ", market="CN"), 1
        )

    assert bars[0].volume == 108_272_100


@pytest.mark.anyio
async def test_us_adjusted_request_skips_today_and_sorts_completed_bars() -> None:
    """只保存已完成交易日；美股响应倒序时转换为日期升序。"""
    # 测试也保持 Python 3.10 兼容，因此仍使用 timezone.utc。
    today = datetime.now(timezone.utc).date()  # noqa: UP017
    yesterday = today - timedelta(days=1)
    earlier = today - timedelta(days=2)

    def row(day: str) -> dict[str, str]:
        return {
            "datetime": day,
            "open": "100.1",
            "high": "101.2",
            "low": "99.5",
            "close": "100.8",
            "volume": "1000",
        }

    def respond(request: httpx.Request) -> httpx.Response:
        assert request.url.params["symbol"] == "AAPL"
        assert request.url.params["interval"] == "1day"
        assert request.url.params["outputsize"] == "3"
        assert request.url.params["adjust"] == "all"
        assert request.url.params["apikey"] == "test-key"
        return httpx.Response(
            200,
            json={
                "meta": {"symbol": "AAPL", "currency": "USD"},
                "values": [
                    row(today.isoformat()),
                    row(yesterday.isoformat()),
                    row(earlier.isoformat()),
                ],
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http_client:
        bars = await MarketDataClient(http_client, "test-key").fetch_daily_bars(
            Stock(symbol="AAPL", market="US"), 2
        )

    assert [bar.trade_date for bar in bars] == [earlier, yesterday]
    assert all(bar.source == "twelvedata" and bar.adjustment == "all" for bar in bars)


@pytest.mark.anyio
async def test_missing_us_key_fails_before_sending_http_request() -> None:
    """没有个人密钥时不能偷偷使用仅支持少量代码的演示密钥。"""
    called = False

    def respond(request: httpx.Request) -> httpx.Response:
        nonlocal called
        called = True
        return httpx.Response(200, json={})

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http_client:
        with pytest.raises(MarketDataError, match="TWELVE_DATA_API_KEY"):
            await MarketDataClient(http_client, "").fetch_daily_bars(
                Stock(symbol="AAPL", market="US"), 1
            )
    assert called is False


@pytest.mark.anyio
async def test_bad_upstream_data_fails_without_returning_partial_bars() -> None:
    """上游把最高价写得比收盘价低时，拒绝整次采集。"""

    def respond(request: httpx.Request) -> httpx.Response:
        return _cn_response("sh688385", [["2026-11-12", "53", "54", "52", "50", "100"]])

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http_client:
        with pytest.raises(MarketDataError, match="有效日线"):
            await MarketDataClient(http_client, "").fetch_daily_bars(
                Stock(symbol="688385.SH", market="CN"), 1
            )


@pytest.mark.anyio
async def test_upstream_http_failure_has_no_secret_in_error() -> None:
    """即使请求 URL 中有密钥，也不把网址和密钥返回给调用方。"""

    def respond(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"status": "error"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http_client:
        with pytest.raises(MarketDataError) as error:
            await MarketDataClient(http_client, "secret-for-test").fetch_daily_bars(
                Stock(symbol="AAPL", market="US"), 1
            )
    assert "secret-for-test" not in str(error.value)


@pytest.mark.anyio
async def test_us_unexpected_json_shape_returns_source_error() -> None:
    """上游即使返回 HTTP 200，也可能不是预期的行情对象。"""

    def respond(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=["unexpected"])

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http_client:
        with pytest.raises(MarketDataError, match="美股行情响应缺少有效日线"):
            await MarketDataClient(http_client, "test-key").fetch_daily_bars(
                Stock(symbol="AAPL", market="US"), 1
            )


@pytest.mark.anyio
async def test_upstream_timeout_has_specific_safe_message() -> None:
    """下次超时时，用户能看出是等待超时，而不是猜测密钥错误。"""

    def respond(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("模拟超时", request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http_client:
        with pytest.raises(MarketDataError, match="行情网站请求超时"):
            await MarketDataClient(http_client, "test-key").fetch_daily_bars(
                Stock(symbol="AAPL", market="US"), 1
            )


@pytest.mark.anyio
async def test_upstream_rate_limit_has_specific_safe_message() -> None:
    """网站限制调用次数时，用户应知道需要稍后再试。"""

    def respond(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"code": 429, "status": "error"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http_client:
        with pytest.raises(MarketDataError, match="请求过于频繁"):
            await MarketDataClient(http_client, "test-key").fetch_daily_bars(
                Stock(symbol="AAPL", market="US"), 1
            )


@pytest.mark.anyio
async def test_us_error_body_code_is_translated_without_echoing_body() -> None:
    """即使上游用 HTTP 200 包装限流，也不能把英文原文直接返回。"""

    def respond(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"code": 429, "status": "error", "message": "key=test-key"},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http_client:
        with pytest.raises(MarketDataError, match="请求过于频繁") as error:
            await MarketDataClient(http_client, "test-key").fetch_daily_bars(
                Stock(symbol="AAPL", market="US"), 1
            )
    assert "test-key" not in str(error.value)


@pytest.mark.anyio
async def test_provider_404_mentions_code_and_access_rights() -> None:
    """部分代码的 404 表示套餐无权访问，不能武断说股票不存在。"""

    def respond(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"code": 404, "status": "error"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http_client:
        with pytest.raises(MarketDataError, match="股票代码和数据权限"):
            await MarketDataClient(http_client, "test-key").fetch_daily_bars(
                Stock(symbol="APPL", market="US"), 1
            )
