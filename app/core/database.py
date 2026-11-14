from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings


def create_database_engine() -> AsyncEngine:
    """创建异步 MySQL 引擎，并让每条新连接使用 UTC 会话时区。"""
    # asyncmy 会在物理连接建立时异步执行 init_command。
    # MySQL 的 TIMESTAMP 会按连接的会话时区转换；统一为 UTC 后，
    # created_at、fetched_at、computed_at 等时间可使用同一口径。
    # trade_date 是 DATE 类型，仍表示交易所当地的交易日期。
    return create_async_engine(
        get_settings().database_url,
        connect_args={"init_command": "SET time_zone = '+00:00'"},
        pool_pre_ping=True,
        pool_recycle=3600,
    )


engine = create_database_engine()
session_factory = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    """按请求提供数据库会话，并统一提交或回滚事务。"""
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
