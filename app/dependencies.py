"""集中声明 FastAPI 依赖，并组装路由需要的业务服务。"""

from collections.abc import AsyncIterator
from typing import Annotated

import httpx
from fastapi import Depends
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_session
from app.core.redis import get_redis
from app.repository.analysis import AnalysisRepository
from app.repository.daily_price import DailyPriceRepository
from app.repository.stock import StockRepository
from app.service.analysis import AnalysisService
from app.service.market_data import MarketDataClient
from app.service.price_collection import PriceCollectionService
from app.service.price_history import PriceHistoryService
from app.service.stock import StockService
from app.service.stock_catalog import StockCatalogClient
from app.service.stock_registration import StockRegistrationService
from app.service.stock_search import StockSearchService

# 会话的创建和事务收尾仍由 get_session 实现。scope="function" 让提交或
# 回滚发生在响应发给客户端之前，避免提交失败时客户端已经收到成功状态。
SessionDep = Annotated[AsyncSession, Depends(get_session, scope="function")]

# Redis 客户端仍由 lifespan 创建；业务路由只从本模块取得依赖别名。
RedisDep = Annotated[Redis, Depends(get_redis)]


def get_stock_repository(session: SessionDep) -> StockRepository:
    """把当前请求的数据库会话交给股票仓储。"""
    return StockRepository(session)


StockRepositoryDep = Annotated[StockRepository, Depends(get_stock_repository)]


def get_stock_service(repository: StockRepositoryDep) -> StockService:
    """组装业务服务；路由无需了解数据库会话的存在。"""
    return StockService(repository)


StockServiceDep = Annotated[StockService, Depends(get_stock_service)]


async def get_stock_catalog_client() -> AsyncIterator[StockCatalogClient]:
    """为搜索请求建立异步 HTTP 客户端，请求结束后自动关闭。"""
    # 目录查询是网络 I/O；客户端和密钥只在依赖层组装，路由无需接触它们。
    async with httpx.AsyncClient(timeout=15) as client:
        yield StockCatalogClient(client, get_settings().twelve_data_api_key)


StockCatalogClientDep = Annotated[StockCatalogClient, Depends(get_stock_catalog_client)]


def get_stock_search_service(catalog: StockCatalogClientDep) -> StockSearchService:
    """把外部目录适配器交给搜索业务服务。"""
    return StockSearchService(catalog)


StockSearchServiceDep = Annotated[StockSearchService, Depends(get_stock_search_service)]


def get_stock_registration_service(
    repository: StockRepositoryDep, search_service: StockSearchServiceDep
) -> StockRegistrationService:
    """为新增接口组合本地仓储和外部候选搜索。"""
    return StockRegistrationService(repository, search_service)


StockRegistrationServiceDep = Annotated[
    StockRegistrationService, Depends(get_stock_registration_service)
]


def get_daily_price_repository(session: SessionDep) -> DailyPriceRepository:
    """把当前请求的异步数据库会话交给日线仓储。"""
    return DailyPriceRepository(session)


DailyPriceRepositoryDep = Annotated[
    DailyPriceRepository, Depends(get_daily_price_repository)
]


def get_price_history_service(
    stock_repository: StockRepositoryDep,
    daily_price_repository: DailyPriceRepositoryDep,
) -> PriceHistoryService:
    """为只读日线接口组装两个仓储，路由不直接接触会话。"""
    return PriceHistoryService(stock_repository, daily_price_repository)


PriceHistoryServiceDep = Annotated[
    PriceHistoryService, Depends(get_price_history_service)
]


async def get_market_data_client() -> AsyncIterator[MarketDataClient]:
    """每个采集请求共享一个异步 HTTP 客户端，并在请求结束时关闭。"""
    # 密钥由 Pydantic Settings 从环境变量或本地 .env 读取；
    # 这里不打印密钥，也不把它放进数据库或接口响应。
    async with httpx.AsyncClient(timeout=15) as client:
        yield MarketDataClient(client, get_settings().twelve_data_api_key)


MarketDataClientDep = Annotated[MarketDataClient, Depends(get_market_data_client)]


def get_price_collection_service(
    stock_repository: StockRepositoryDep,
    daily_price_repository: DailyPriceRepositoryDep,
    market_data_client: MarketDataClientDep,
) -> PriceCollectionService:
    """组装采集服务；路由只接触服务，不直接使用数据库或 HTTP 客户端。"""
    return PriceCollectionService(
        stock_repository, daily_price_repository, market_data_client
    )


PriceCollectionServiceDep = Annotated[
    PriceCollectionService, Depends(get_price_collection_service)
]


def get_analysis_repository(session: SessionDep) -> AnalysisRepository:
    """把当前请求的异步会话交给分析仓储。"""
    return AnalysisRepository(session)


AnalysisRepositoryDep = Annotated[AnalysisRepository, Depends(get_analysis_repository)]


def get_analysis_service(
    stock_repository: StockRepositoryDep,
    daily_price_repository: DailyPriceRepositoryDep,
    analysis_repository: AnalysisRepositoryDep,
) -> AnalysisService:
    """集中组装分析服务；路由无需知道数据库会话或模型细节。"""
    return AnalysisService(
        stock_repository, daily_price_repository, analysis_repository
    )


AnalysisServiceDep = Annotated[AnalysisService, Depends(get_analysis_service)]
