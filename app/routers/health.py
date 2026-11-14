from fastapi import APIRouter

from app.schemas.health import HealthResponse

router = APIRouter(tags=["健康检查"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="检查服务状态",
    response_description="成功响应",
)
async def health() -> HealthResponse:
    """报告 HTTP 服务进程可用。"""
    return HealthResponse(status="ok")
