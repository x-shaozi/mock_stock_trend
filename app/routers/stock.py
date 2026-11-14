"""股票管理的 HTTP 路由。"""

from datetime import timezone
from typing import Annotated

from fastapi import APIRouter, Path, Query

from app.core.exceptions import BusinessHTTPException
from app.dependencies import (
    StockRegistrationServiceDep,
    StockSearchServiceDep,
    StockServiceDep,
)
from app.schemas.api_response import APIResponse
from app.schemas.stock import (
    StockArchiveResponse,
    StockCandidateResponse,
    StockCreate,
    StockDetailResponse,
    StockListQuery,
    StockListResponse,
    StockResponse,
    StockRestoreResponse,
    StockSearchQuery,
    StockSearchResponse,
)
from app.service.stock import StockNotFound
from app.service.stock_catalog import StockCatalogError
from app.service.stock_registration import StockAlreadyExists, StockNotListed

router = APIRouter(prefix="/stocks", tags=["股票管理"])


@router.get(
    "/search",
    response_model=StockSearchResponse,
    summary="按代码或名称搜索可追踪股票",
    responses={502: {"model": APIResponse, "description": "股票搜索服务失败"}},
)
async def search_stocks(
    query: Annotated[StockSearchQuery, Query()], service: StockSearchServiceDep
) -> StockSearchResponse:
    """只返回外部目录中的候选项；用户选中后再调用新增接口。"""
    try:
        candidates = await service.search(query=query.query, market=query.market)
    except StockCatalogError as exc:
        raise BusinessHTTPException(
            status_code=502, error_code="STOCK_CATALOG_UNAVAILABLE", message=str(exc)
        ) from None
    return StockSearchResponse(
        items=[StockCandidateResponse.model_validate(item) for item in candidates]
    )


@router.get(
    "",
    response_model=StockListResponse,
    summary="查询股票列表",
)
async def list_stocks(
    query: Annotated[StockListQuery, Query()], service: StockServiceDep
) -> StockListResponse:
    """返回所选状态的一页股票，以及该状态下的总条数。"""
    stocks, total = await service.list_stocks(
        page=query.page,
        page_size=query.page_size,
        status=query.status,
        market=query.market,
        keyword=query.keyword,
    )
    return StockListResponse(
        items=[StockResponse.model_validate(stock) for stock in stocks],
        total=total,
        page=query.page,
        page_size=query.page_size,
    )


@router.get(
    "/{stock_id}",
    response_model=StockDetailResponse,
    summary="按编号查询股票详情",
    responses={404: {"model": APIResponse, "description": "股票不存在"}},
)
async def get_stock(
    stock_id: Annotated[int, Path(ge=1)], service: StockServiceDep
) -> StockDetailResponse:
    """供详情页独立查询股票；已归档记录仍能打开详情。"""
    try:
        stock = await service.get_stock(stock_id)
    except StockNotFound:
        raise BusinessHTTPException(
            status_code=404, error_code="STOCK_NOT_FOUND", message="股票不存在"
        ) from None
    return StockDetailResponse(
        id=stock.id,
        symbol=stock.symbol,
        name=stock.name,
        market=stock.market,
        status="archived" if stock.archived_at is not None else "active",
        created_at=stock.created_at.replace(tzinfo=timezone.utc),  # noqa: UP017
        archived_at=(
            stock.archived_at.replace(tzinfo=timezone.utc)  # noqa: UP017
            if stock.archived_at is not None
            else None
        ),
    )


@router.post(
    "",
    status_code=201,
    response_model=StockResponse,
    summary="将选中的股票加入追踪列表",
    responses={
        404: {"model": APIResponse, "description": "股票目录中找不到该代码"},
        409: {"model": APIResponse, "description": "股票已存在"},
        502: {"model": APIResponse, "description": "股票搜索服务失败"},
    },
)
async def add_stock(
    request: StockCreate, service: StockRegistrationServiceDep
) -> StockResponse:
    """按代码加入追踪列表，名称由业务层从外部目录核对后填写。"""
    try:
        stock = await service.register_stock(
            symbol=request.symbol, market=request.market
        )
    except StockAlreadyExists as exc:
        # 已归档股票仍占用市场与代码的唯一组合，不能重复新增。
        raise BusinessHTTPException(
            status_code=409,
            error_code="STOCK_ALREADY_EXISTS",
            message="该市场的股票代码已存在",
        ) from exc
    except StockNotListed:
        raise BusinessHTTPException(
            status_code=404,
            error_code="STOCK_NOT_LISTED",
            message="股票目录中找不到该市场的代码",
        ) from None
    except StockCatalogError as exc:
        raise BusinessHTTPException(
            status_code=502, error_code="STOCK_CATALOG_UNAVAILABLE", message=str(exc)
        ) from None
    return StockResponse.model_validate(stock)


@router.patch(
    "/{stock_id}/archive",
    response_model=StockArchiveResponse,
    summary="归档股票",
    responses={404: {"model": APIResponse, "description": "股票不存在"}},
)
async def archive_stock(
    stock_id: Annotated[int, Path(ge=1)], service: StockServiceDep
) -> StockArchiveResponse:
    """按股票编号归档；已有归档记录时直接返回成功。"""
    try:
        stock = await service.archive_stock(stock_id)
    except StockNotFound as exc:
        raise BusinessHTTPException(
            status_code=404, error_code="STOCK_NOT_FOUND", message="股票不存在"
        ) from exc
    return StockArchiveResponse(id=stock.id, symbol=stock.symbol, status="archived")


@router.patch(
    "/{stock_id}/restore",
    response_model=StockRestoreResponse,
    summary="恢复已归档股票",
    responses={404: {"model": APIResponse, "description": "股票不存在"}},
)
async def restore_stock(
    stock_id: Annotated[int, Path(ge=1)], service: StockServiceDep
) -> StockRestoreResponse:
    """按股票编号恢复；已经正常的股票再次请求也返回成功。"""
    try:
        stock = await service.restore_stock(stock_id)
    except StockNotFound as exc:
        raise BusinessHTTPException(
            status_code=404, error_code="STOCK_NOT_FOUND", message="股票不存在"
        ) from exc
    return StockRestoreResponse(id=stock.id, symbol=stock.symbol, status="active")
