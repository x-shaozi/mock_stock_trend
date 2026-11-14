"""把不同网站的日线响应转换为项目统一使用的行情记录。"""

import json
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

import httpx

from app.models.stock import Stock


class MarketDataError(Exception):
    """行情网站不可用，或返回的数据无法安全地作为完整日线使用。"""


@dataclass(frozen=True)
class DailyBar:
    """一条已统一字段、价格精度和成交量单位的完整日线。"""

    trade_date: date
    open_price: Decimal
    high_price: Decimal
    low_price: Decimal
    close_price: Decimal
    volume: int  # 单位始终是股，而不是腾讯部分股票使用的“手”。
    currency: str
    source: str
    adjustment: str


class MarketDataClient:
    """只负责异步请求与解析行情；不会直接操作数据库。"""

    def __init__(
        self, http_client: httpx.AsyncClient, twelve_data_api_key: str
    ) -> None:
        self._http_client = http_client
        self._twelve_data_api_key = twelve_data_api_key

    async def fetch_daily_bars(self, stock: Stock, days: int) -> list[DailyBar]:
        """读取最近的调整后完整日线，并按交易日从早到晚返回。"""
        if stock.market == "CN":
            bars = await self._fetch_cn(stock.symbol)
        elif stock.market == "US":
            bars = await self._fetch_us(stock.symbol, days)
        else:
            raise MarketDataError("不支持的股票市场")

        # 日线网站可能在交易尚未结束时就返回“今天”的价格。
        # UTC 日期是一个保守的截止点：会偶尔晚一天收录，但不会把未收盘
        # 的价格误当作最终收盘价。这里不依赖 Windows 缺省没有的时区库。
        # timezone.utc 兼容项目声明的 Python 3.10；datetime.UTC 从 3.11 才有。
        today_utc = datetime.now(timezone.utc).date()  # noqa: UP017
        completed = [bar for bar in bars if bar.trade_date < today_utc]
        if not completed:
            raise MarketDataError("行情源没有返回已完成的日线")

        # 同一日期只允许一种结果。上游返回冲突记录时整次采集失败，
        # 以免随机选一条写入数据库。
        by_date: dict[date, DailyBar] = {}
        for bar in completed:
            old = by_date.get(bar.trade_date)
            if old is not None and old != bar:
                raise MarketDataError("行情源返回了相互冲突的同日记录")
            by_date[bar.trade_date] = bar
        return sorted(by_date.values(), key=lambda bar: bar.trade_date)[-days:]

    async def _request(self, url: str, params: dict[str, str | int]) -> httpx.Response:
        """异步请求行情网站，并把常见失败转换为能看懂的安全提示。"""
        try:
            response = await self._http_client.get(url, params=params)
            response.raise_for_status()
        except httpx.TimeoutException:
            raise MarketDataError("行情网站请求超时，请稍后重试") from None
        except httpx.HTTPStatusError as exc:
            # 只取数字状态码。异常文本和请求 URL 可能带有 API Key，
            # 不能直接放到接口响应、日志或新异常的 cause 里。
            raise MarketDataError(
                self._status_message(exc.response.status_code)
            ) from None
        except httpx.RequestError:
            raise MarketDataError("无法连接行情网站，请检查网络后重试") from None
        return response

    @staticmethod
    def _status_message(status_code: int) -> str:
        """把上游 HTTP 状态码翻译为可操作的提示，不返回上游原文。"""
        if status_code == 401:
            return "行情网站拒绝密钥，请核对数据源密钥"
        if status_code == 403:
            return "行情网站访问权限不足"
        if status_code == 404:
            return "行情网站未提供该代码的日线，请核对股票代码和数据权限"
        if status_code == 429:
            return "行情网站请求过于频繁，请稍后重试"
        if status_code >= 500:
            return f"行情网站暂时不可用（HTTP {status_code}）"
        return f"行情网站请求失败（HTTP {status_code}）"

    async def _fetch_cn(self, symbol: str) -> list[DailyBar]:
        """请求腾讯前复权日线，并按腾讯数组的实际字段顺序解析。"""
        prefix = f"{symbol[-2:].lower()}{symbol[:6]}"
        response = await self._request(
            "https://proxy.finance.qq.com/ifzqgtimg/appstock/app/newfqkline/get",
            {"_var": "kline_day", "param": f"{prefix},day,,,640,qfq"},
        )
        # 腾讯可能在 JSON 前加上 `变量名=`，不能直接调用 response.json()。
        body = response.text
        marker = body.find("={")
        if marker >= 0:
            body = body[marker + 1 :]
        try:
            payload = json.loads(body)
            # 请求 qfq 时，腾讯把日线放在 qfqday，而非未复权的 day。
            rows = payload["data"][prefix]["qfqday"]
            if not isinstance(rows, list) or not rows:
                raise ValueError("日线为空")
            return [self._parse_cn_row(row, prefix) for row in rows]
        except (KeyError, TypeError, ValueError, IndexError) as exc:
            raise MarketDataError("A 股行情响应缺少有效日线") from exc

    async def _fetch_us(self, symbol: str, days: int) -> list[DailyBar]:
        """请求 Twelve Data 调整后日线；个人密钥只能从服务配置传入。"""
        if not self._twelve_data_api_key:
            raise MarketDataError("美股行情密钥未配置，请设置 TWELVE_DATA_API_KEY")
        response = await self._request(
            "https://api.twelvedata.com/time_series",
            {
                "symbol": symbol,
                "interval": "1day",
                # 多要一条，以便丢掉可能尚未收盘的当日日线。
                "outputsize": days + 1,
                # v1 分析规则需要调整后价格；不能和旧的 none 日线混算。
                "adjust": "all",
                "apikey": self._twelve_data_api_key,
            },
        )
        try:
            payload = response.json()
            if not isinstance(payload, dict):
                raise TypeError("响应不是对象")
            if payload.get("status") == "error":
                # Twelve Data 通常用 HTTP 状态码报错，也可能在 JSON 中给出
                # code。仍只使用数字码生成提示，不把可能含密钥的原文返回。
                code = payload.get("code")
                if isinstance(code, int):
                    raise MarketDataError(self._status_message(code))
                raise MarketDataError("美股行情网站返回错误")
            meta = payload["meta"]
            if not isinstance(meta, dict):
                raise TypeError("股票元数据不是对象")
            meta_symbol = meta["symbol"]
            if (
                not isinstance(meta_symbol, str)
                or meta_symbol.upper() != symbol
                or meta["currency"] != "USD"
            ):
                raise ValueError("股票身份或币种不符")
            rows = payload["values"]
            if not isinstance(rows, list) or not rows:
                raise ValueError("日线为空")
            return [self._parse_us_row(row) for row in rows]
        except (KeyError, TypeError, ValueError, IndexError) as exc:
            raise MarketDataError("美股行情响应缺少有效日线") from exc

    @classmethod
    def _parse_cn_row(cls, row: list[str], prefix: str) -> DailyBar:
        """腾讯字段依次是日期、开、收、高、低、量；量按证券类型换为股。"""
        if not isinstance(row, list) or len(row) < 6:
            raise ValueError("A 股日线字段不足")
        multiplier = 1 if prefix.startswith(("sh688", "sh689")) else 100
        return cls._make_bar(
            trade_date=row[0],
            open_price=row[1],
            close_price=row[2],
            high_price=row[3],
            low_price=row[4],
            volume=row[5],
            volume_multiplier=multiplier,
            currency="CNY",
            source="tencent",
            adjustment="qfq",
        )

    @classmethod
    def _parse_us_row(cls, row: dict[str, str]) -> DailyBar:
        """Twelve Data 使用具名字段，价格仍按十进制字符串转换。"""
        return cls._make_bar(
            trade_date=row["datetime"],
            open_price=row["open"],
            high_price=row["high"],
            low_price=row["low"],
            close_price=row["close"],
            volume=row["volume"],
            volume_multiplier=1,
            currency="USD",
            source="twelvedata",
            adjustment="all",
        )

    @staticmethod
    def _make_bar(
        *,
        trade_date: str,
        open_price: str,
        high_price: str,
        low_price: str,
        close_price: str,
        volume: str,
        volume_multiplier: int,
        currency: str,
        source: str,
        adjustment: str,
    ) -> DailyBar:
        """统一检查价格、数量与日期；坏记录不允许进入数据库。"""
        try:
            prices = [
                Decimal(value).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
                for value in (open_price, high_price, low_price, close_price)
            ]
            raw_volume = Decimal(volume) * volume_multiplier
            if not raw_volume.is_finite() or raw_volume != int(raw_volume):
                raise ValueError("成交量必须是整数股")
            shares = int(raw_volume)
            day = date.fromisoformat(trade_date)
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise ValueError("日线含有无效日期、价格或成交量") from exc
        opening, high, low, closing = prices
        if (
            any(
                not price.is_finite() or price <= 0 or price >= 10**12
                for price in prices
            )
            or low > min(opening, closing)
            or high < max(opening, closing)
            or high < low
            or not 0 <= shares <= 2**63 - 1
        ):
            raise ValueError("日线价格或成交量超出合理范围")
        return DailyBar(
            trade_date=day,
            open_price=opening,
            high_price=high,
            low_price=low,
            close_price=closing,
            volume=shares,
            currency=currency,
            source=source,
            adjustment=adjustment,
        )
