from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from redis.asyncio import Redis

from app.core.config import get_settings
from app.core.database import engine
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging
from app.routers import analysis, daily_price, health, home, stock
from app.schemas.api_response import APIResponse


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """创建并释放共享 Redis 客户端与数据库连接池。"""
    app.state.redis = Redis.from_url(get_settings().redis_url, decode_responses=True)
    try:
        yield
    finally:
        await app.state.redis.aclose()
        await engine.dispose()


configure_logging()
app = FastAPI(
    title="模拟股票趋势 API",
    lifespan=lifespan,
    responses={
        422: {"model": APIResponse, "description": "请求参数不合法"},
        500: {"model": APIResponse, "description": "服务器内部错误"},
    },
)
register_exception_handlers(app)
app.include_router(home.router)
app.include_router(health.router)
app.include_router(stock.router)
app.include_router(daily_price.router)
app.include_router(analysis.router)


if __name__ == "__main__":
    uvicorn.run("app.main:app", host="127.0.0.1", port=18000, reload=True)
