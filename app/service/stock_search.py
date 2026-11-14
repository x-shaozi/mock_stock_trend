"""把用户搜索词交给正确的市场目录，并整理给前端选择。"""

from app.service.stock_catalog import StockCandidate, StockCatalogClient


class StockSearchService:
    """搜索候选股票；此过程只读外部网站，不保存本地追踪记录。"""

    def __init__(self, catalog: StockCatalogClient) -> None:
        self._catalog = catalog

    async def search(self, *, query: str, market: str) -> list[StockCandidate]:
        """按市场搜索，按代码去重，并把精确代码匹配置于前面。"""
        if market == "CN":
            # 腾讯建议接口不认识 688385.SH 这样的后缀，需先提取六位代码。
            source_query = query.upper()
            if source_query.endswith((".SH", ".SZ", ".SS")):
                source_query = source_query[:-3]
            candidates = await self._catalog.search_cn(source_query)
        else:
            candidates = await self._catalog.search_us(query)

        # 美股同一代码可能同时出现在 NASDAQ 和 IEX；当前 stocks 表用
        # (market, symbol) 识别一只股票，所以搜索结果也只展示一次。
        unique: dict[str, StockCandidate] = {}
        for candidate in candidates:
            unique.setdefault(candidate.symbol, candidate)
        normalized_query = query.upper().replace(".SS", ".SH")
        return sorted(
            unique.values(),
            key=lambda candidate: candidate.symbol != normalized_query,
        )[:20]
