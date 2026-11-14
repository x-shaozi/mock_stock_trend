"""读取已存日线与在线采集日线的 HTTP 接口。"""

from typing import Annotated

from fastapi import APIRouter, Path, Query

from app.core.exceptions import BusinessHTTPException
from app.dependencies import PriceCollectionServiceDep, PriceHistoryServiceDep
from app.repository.daily_price import PriceBasisConflict
from app.schemas.api_response import APIResponse
from app.schemas.daily_price import (
    DailyPriceItem,
    PriceCollectionQuery,
    PriceCollectionResponse,
    PriceHistoryQuery,
    PriceHistoryResponse,
)
from app.service.market_data import MarketDataError
from app.service.price_collection import ArchivedStock, CollectionStockNotFound
from app.service.price_history import HistoryStockNotFound

router = APIRouter(prefix="/stocks", tags=["行情采集"])


@router.get(
    "/{stock_id}/prices",
    response_model=PriceHistoryResponse,
    summary="查询已保存的日线",
    responses={404: {"model": APIResponse, "description": "股票不存在"}},
)
async def list_daily_prices(
    stock_id: Annotated[int, Path(ge=1)],
    query: Annotated[PriceHistoryQuery, Query()],
    service: PriceHistoryServiceDep,
) -> PriceHistoryResponse:
    """按股票编号查询 MySQL，返回最近的已存日线，不访问行情网站。"""
    try:
        stock, prices = await service.get_history(stock_id, query.days)
    except HistoryStockNotFound:
        raise BusinessHTTPException(
            status_code=404, error_code="STOCK_NOT_FOUND", message="股票不存在"
        ) from None

    return PriceHistoryResponse(
        stock_id=stock.id,
        symbol=stock.symbol,
        market=stock.market,
        items=[DailyPriceItem.model_validate(price) for price in prices],
    )


@router.post(
    "/{stock_id}/prices/collect",
    response_model=PriceCollectionResponse,
    summary="在线采集日线并入库",
    responses={
        404: {"model": APIResponse, "description": "股票不存在"},
        409: {"model": APIResponse, "description": "股票已归档或行情口径冲突"},
        502: {"model": APIResponse, "description": "行情网站请求或响应失败"},
    },
)
async def collect_daily_prices(
    stock_id: Annotated[int, Path(ge=1)],
    query: Annotated[PriceCollectionQuery, Query()],
    service: PriceCollectionServiceDep,
) -> PriceCollectionResponse:
    """采集调整后日线入库，并把业务错误转成统一响应。"""
    try:
        result = await service.collect(stock_id, query.days)
    except CollectionStockNotFound as exc:
        raise BusinessHTTPException(
            status_code=404, error_code="STOCK_NOT_FOUND", message="股票不存在"
        ) from exc
    except ArchivedStock as exc:
        raise BusinessHTTPException(
            status_code=409,
            error_code="STOCK_ARCHIVED",
            message="已归档股票不可采集行情",
        ) from exc
    except PriceBasisConflict as exc:
        raise BusinessHTTPException(
            status_code=409,
            error_code="PRICE_BASIS_CONFLICT",
            message="已有不同行情口径，不能覆盖",
        ) from exc
    except MarketDataError as exc:
        raise BusinessHTTPException(
            status_code=502, error_code="MARKET_DATA_UNAVAILABLE", message=str(exc)
        ) from exc
    return PriceCollectionResponse(
        stock_id=result.stock_id,
        symbol=result.symbol,
        inserted=result.counts.inserted,
        updated=result.counts.updated,
        unchanged=result.counts.unchanged,
    )
