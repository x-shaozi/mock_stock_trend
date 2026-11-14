"""定义访问 API 根路径时返回的首页信息。"""

from fastapi import APIRouter, Request

from app.schemas.home import HomeResponse

router = APIRouter(tags=["项目入口"])


@router.get(
    "/",
    response_model=HomeResponse,
    summary="查看 API 入口",
    response_description="成功响应",
)
async def home(request: Request) -> HomeResponse:
    """返回应用名称和入口地址；此请求不需要查询 MySQL 或 Redis。"""
    # 应用名称直接取 FastAPI 的 title，避免这里再维护一份可能过时的名称。
    return HomeResponse(name=request.app.title, docs="/docs", health="/health")
