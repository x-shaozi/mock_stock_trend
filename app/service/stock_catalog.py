"""异步查询外部股票目录，并把来源各异的结果转换为统一候选项。"""

import json
import re
from dataclasses import dataclass

import httpx


class StockCatalogError(Exception):
    """股票目录网站不可用，或返回了不能安全解析的内容。"""


@dataclass(frozen=True)
class StockCandidate:
    """尚未加入本地追踪列表的一只股票；这里没有数据库编号。"""

    symbol: str
    name: str
    market: str
    exchange: str


class StockCatalogClient:
    """只负责访问股票目录；不查询或写入本项目的 MySQL。"""

    def __init__(
        self, http_client: httpx.AsyncClient, twelve_data_api_key: str
    ) -> None:
        self._http_client = http_client
        self._twelve_data_api_key = twelve_data_api_key

    async def search_cn(self, query: str) -> list[StockCandidate]:
        """读取腾讯搜索建议，保留沪深两市的 A 股普通股票。"""
        response = await self._request(
            "https://smartbox.gtimg.cn/s3/",
            {"v": 2, "t": "all", "c": 20, "q": query},
        )
        # 该接口不是 JSON API，而是形如 v_hint="..."; 的脚本文本。
        # 先检查整体格式，再用 json.loads 解开其中的 Unicode 转义。
        match = re.fullmatch(r'v_hint=("(?:\\.|[^"\\])*");?', response.text.strip())
        if match is None:
            raise StockCatalogError("A 股搜索服务返回了无法识别的数据")
        try:
            body = json.loads(match.group(1))
        except (TypeError, ValueError) as exc:
            raise StockCatalogError("A 股搜索服务返回了无法识别的数据") from exc
        if not isinstance(body, str):
            raise StockCatalogError("A 股搜索服务返回了无法识别的数据")
        if body == "N":
            return []

        candidates: list[StockCandidate] = []
        for record in body.split("^"):
            fields = record.split("~")
            if len(fields) < 5:
                continue
            prefix, code, name, _pinyin, kind = fields[:5]
            # 搜索建议也会混入指数、基金和非 A 股；只有 GP-A 类别可选。
            # 沪深股票可能同为六位代码，因此必须同时保留交易所后缀。
            if (
                prefix not in ("sh", "sz")
                or re.fullmatch(r"\d{6}", code) is None
                or not name.strip()
                or not kind.startswith("GP-A")
            ):
                continue
            candidates.append(
                StockCandidate(
                    symbol=f"{code}.{prefix.upper()}",
                    name=name.strip(),
                    market="CN",
                    exchange="SSE" if prefix == "sh" else "SZSE",
                )
            )
        return candidates

    async def search_us(self, query: str) -> list[StockCandidate]:
        """读取 Twelve Data 的匹配结果，只保留美国普通股。"""
        if not self._twelve_data_api_key:
            raise StockCatalogError("美股搜索密钥未配置，请设置 TWELVE_DATA_API_KEY")
        response = await self._request(
            "https://api.twelvedata.com/symbol_search",
            # 搜索结果混合了各国股票、基金等。同一英文名称的前几条可能
            # 全是其他市场，因此先取上游允许的 120 条，再按市场筛选。
            {"symbol": query, "outputsize": 120, "apikey": self._twelve_data_api_key},
        )
        try:
            payload = response.json()
            if not isinstance(payload, dict):
                raise TypeError("搜索响应不是对象")
            if payload.get("status") == "error":
                raise StockCatalogError("美股搜索服务拒绝了请求，请稍后重试")
            rows = payload["data"]
            if not isinstance(rows, list):
                raise TypeError("搜索列表不是数组")
        except (TypeError, ValueError, KeyError) as exc:
            raise StockCatalogError("美股搜索服务返回了无法识别的数据") from exc

        candidates: list[StockCandidate] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            symbol = row.get("symbol")
            name = row.get("instrument_name")
            exchange = row.get("exchange")
            if (
                row.get("country") != "United States"
                or row.get("instrument_type") != "Common Stock"
                or not isinstance(symbol, str)
                or re.fullmatch(r"[A-Z][A-Z0-9.-]{0,19}", symbol) is None
                or not isinstance(name, str)
                or not name.strip()
                or not isinstance(exchange, str)
                or not exchange.strip()
            ):
                continue
            candidates.append(
                StockCandidate(
                    symbol=symbol,
                    name=name.strip(),
                    market="US",
                    exchange=exchange.strip(),
                )
            )
        return candidates

    async def _request(self, url: str, params: dict[str, str | int]) -> httpx.Response:
        """统一处理网络失败；异常中可能含密钥，因此不能原样返回。"""
        try:
            response = await self._http_client.get(url, params=params)
            response.raise_for_status()
            return response
        except httpx.TimeoutException:
            raise StockCatalogError("股票搜索服务请求超时，请稍后重试") from None
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 429:
                raise StockCatalogError(
                    "股票搜索服务请求过于频繁，请稍后重试"
                ) from None
            raise StockCatalogError("股票搜索服务暂时不可用，请稍后重试") from None
        except httpx.RequestError:
            raise StockCatalogError("无法连接股票搜索服务，请稍后重试") from None
