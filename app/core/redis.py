from fastapi import Request
from redis.asyncio import Redis


def get_redis(request: Request) -> Redis:
    """取得应用生命周期管理的 Redis 客户端。"""
    return request.app.state.redis
