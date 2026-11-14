"""创建、重算或读取一轮已保存的趋势分析。"""

from datetime import timezone
from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Query, Response

from app.dependencies import AnalysisServiceDep
from app.schemas.analysis import (
    AnalysisResultItem,
    AnalysisRunDetailResponse,
    AnalysisRunListItem,
    AnalysisRunListQuery,
    AnalysisRunListResponse,
    AnalysisRunRequest,
    AnalysisRunResponse,
    LatestAnalysis,
)
from app.schemas.api_response import APIResponse
from app.service.analysis import (
    AnalysisDataInsufficient,
    AnalysisPriceBasisConflict,
    AnalysisRunNotFound,
    AnalysisStockArchived,
    AnalysisStockNotFound,
)

router = APIRouter(prefix="/stocks", tags=["趋势分析"])


@router.get(
    "/{stock_id}/analysis-runs",
    response_model=AnalysisRunListResponse,
    summary="查看股票已保存的分析批次",
    responses={404: {"model": APIResponse, "description": "股票不存在"}},
)
async def list_analysis_runs(
    stock_id: Annotated[int, Path(ge=1)],
    query: Annotated[AnalysisRunListQuery, Query()],
    service: AnalysisServiceDep,
) -> AnalysisRunListResponse:
    """分页列出已保存批次；选择 run_id 后可调用逐日结果接口。"""
    try:
        stock, runs, total = await service.list_runs(
            stock_id=stock_id, page=query.page, page_size=query.page_size
        )
    except AnalysisStockNotFound:
        raise HTTPException(status_code=404, detail="股票不存在") from None

    return AnalysisRunListResponse(
        stock_id=stock.id,
        symbol=stock.symbol,
        market=stock.market,
        items=[
            AnalysisRunListItem(
                run_id=run.id,
                requested_days=run.requested_days,
                start_date=run.start_date,
                end_date=run.end_date,
                source=run.source,
                adjustment=run.adjustment,
                rule_version=run.rule_version,
                # MySQL TIMESTAMP 按 UTC 读取；给 JSON 显式标上 UTC 时区。
                computed_at=run.computed_at.replace(tzinfo=timezone.utc),  # noqa: UP017
            )
            for run in runs
        ],
        total=total,
        page=query.page,
        page_size=query.page_size,
    )


@router.get(
    "/{stock_id}/analysis-runs/{run_id}",
    response_model=AnalysisRunDetailResponse,
    summary="查看一轮已保存的逐日分析结果",
    responses={404: {"model": APIResponse, "description": "分析批次不存在"}},
)
async def get_analysis_run(
    stock_id: Annotated[int, Path(ge=1)],
    run_id: Annotated[int, Path(ge=1)],
    service: AnalysisServiceDep,
) -> AnalysisRunDetailResponse:
    """按股票和批次编号读取快照；不联网、不重算，也不修改数据库。"""
    try:
        run = await service.get_run(stock_id, run_id)
    except AnalysisRunNotFound:
        raise HTTPException(status_code=404, detail="分析批次不存在") from None

    # MySQL 会话已统一为 UTC，但 TIMESTAMP 读取后没有时区标记；补上 UTC，
    # 避免客户端把 computed_at 误认为自己电脑的当地时间。
    computed_at = run.computed_at.replace(tzinfo=timezone.utc)  # noqa: UP017
    return AnalysisRunDetailResponse(
        run_id=run.id,
        stock_id=run.stock_id,
        symbol=run.stock.symbol,
        market=run.stock.market,
        requested_days=run.requested_days,
        start_date=run.start_date,
        end_date=run.end_date,
        source=run.source,
        adjustment=run.adjustment,
        rule_version=run.rule_version,
        computed_at=computed_at,
        saved=len(run.results),
        items=[AnalysisResultItem.model_validate(item) for item in run.results],
    )


@router.post(
    "/{stock_id}/analysis-runs",
    status_code=201,
    response_model=AnalysisRunResponse,
    summary="根据已存日线发起趋势分析",
    responses={
        200: {"model": AnalysisRunResponse, "description": "同条件重算已有批次"},
        404: {"model": APIResponse, "description": "股票不存在"},
        409: {
            "model": APIResponse,
            "description": "股票已归档、日线不足或价格口径不一致",
        },
    },
)
async def create_analysis_run(
    stock_id: Annotated[int, Path(ge=1)],
    body: AnalysisRunRequest,
    service: AnalysisServiceDep,
    response: Response,
) -> AnalysisRunResponse:
    """只负责 HTTP 状态和响应；数据库查询、计算与保存由业务层协调。"""
    try:
        outcome = await service.run(stock_id, body.days)
    except AnalysisStockNotFound:
        raise HTTPException(status_code=404, detail="股票不存在") from None
    except AnalysisStockArchived:
        raise HTTPException(
            status_code=409, detail="已归档股票不可发起新分析"
        ) from None
    except AnalysisDataInsufficient as exc:
        raise HTTPException(
            status_code=409,
            detail=f"已存日线不足：需要{exc.requested}条，当前{exc.available}条",
        ) from exc
    except AnalysisPriceBasisConflict:
        raise HTTPException(
            status_code=409,
            detail="已存日线的来源、调整方式或币种不一致，请先核对行情",
        ) from None

    # 首次保存产生新资源，重复请求则重算同一批次并保留原编号。
    response.status_code = 201 if outcome.created else 200
    latest = outcome.latest
    return AnalysisRunResponse(
        run_id=outcome.run_id,
        stock_id=outcome.stock_id,
        symbol=outcome.symbol,
        requested_days=outcome.requested_days,
        start_date=outcome.start_date,
        end_date=outcome.end_date,
        source=outcome.source,
        adjustment=outcome.adjustment,
        rule_version=outcome.rule_version,
        saved=outcome.requested_days,
        latest=LatestAnalysis(
            trade_date=latest.trade_date,
            close_price=latest.close_price,
            ma5=latest.ma5,
            ma20=latest.ma20,
            rsi14=latest.rsi14,
            macd=latest.macd,
            trend_score=latest.trend_score,
            trend_label=latest.trend_label,
            summary=latest.summary,
        ),
    )
