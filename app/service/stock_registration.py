"""把用户选择的股票候选核对后加入本地追踪列表。"""

from sqlalchemy.exc import IntegrityError

from app.models.stock import Stock
from app.repository.stock import StockRepository
from app.service.stock_catalog import StockCatalogError
from app.service.stock_search import StockSearchService


class StockAlreadyExists(Exception):
    """这个市场和代码已经在本地，包括已归档的股票。"""


class StockNotListed(Exception):
    """外部目录没有返回与用户提交的市场、代码完全一致的股票。"""


class StockRegistrationService:
    """先核对股票身份，再调用仓储保存；自身不持有数据库会话。"""

    def __init__(
        self, repository: StockRepository, search_service: StockSearchService
    ) -> None:
        self._repository = repository
        self._search_service = search_service

    async def register_stock(self, *, symbol: str, market: str) -> Stock:
        """以外部目录中的标准名称建档，防止名称和代码填错。"""
        # 先查本地：已存在时直接告知用户，不浪费外部搜索额度。
        # 已归档股票也占用 (market, symbol)，需要走恢复接口。
        existing = await self._repository.get_by_market_symbol(
            market=market, symbol=symbol
        )
        if existing is not None:
            raise StockAlreadyExists

        # 搜索可以返回相似代码或同名证券，不能随便取第一条。
        # 必须确认用户所选的市场和完整代码均相同，才允许写库。
        candidates = await self._search_service.search(query=symbol, market=market)
        matched = next(
            (
                item
                for item in candidates
                if item.market == market and item.symbol == symbol
            ),
            None,
        )
        if matched is None:
            raise StockNotListed
        if len(matched.name) > 100:
            # stocks.name 的模型长度为 100。来源名称超长时明确报告来源问题，
            # 不截断名称，也不让数据库错误变成难理解的 500。
            raise StockCatalogError("股票搜索服务返回了过长的股票名称")

        stock = Stock(symbol=symbol, name=matched.name, market=market)
        try:
            return await self._repository.insert(stock)
        except IntegrityError as exc:
            # 两个请求可能同时通过上面的查询。数据库唯一约束是最后防线；
            # MySQL 1062 表示重复键，其他完整性错误不能误报成重复股票。
            if exc.orig.args and exc.orig.args[0] == 1062:
                raise StockAlreadyExists from exc
            raise
