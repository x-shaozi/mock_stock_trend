"""Alembic 命令的入口：登记模型，并选择离线打印或在线执行迁移。"""

import asyncio
from logging.config import fileConfig

from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from alembic import context
from app.core.config import get_settings

# 导入具体模型会把四张表登记到 Base.metadata，供 Alembic 比较结构。
# F401 例外标记说明这些类虽未在本文件直接调用，仍必须保留导入。
from app.models.analysis_result import AnalysisResult  # noqa: F401
from app.models.analysis_run import AnalysisRun  # noqa: F401
from app.models.base import Base
from app.models.daily_price import DailyPrice  # noqa: F401
from app.models.stock import Stock  # noqa: F401

# context.config 代表 alembic.ini；若配置了日志段，才交给 Python 日志系统读取。
config = context.config
if config.config_file_name and config.file_config.has_section("loggers"):
    fileConfig(config.config_file_name)

# Base.metadata 是已登记模型的表结构清单，供后续迁移生成与结构比较使用。
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """响应 --sql：按 MySQL 语法生成 SQL 文本，不读取密钥或连接数据库。"""
    # 这里只需要知道目标数据库是 MySQL；离线生成 SQL 不需要数据库地址。
    # literal_binds=True 会把参数值直接写进输出的 SQL，便于人工核对。
    context.configure(
        dialect_name="mysql",
        target_metadata=target_metadata,
        literal_binds=True,
    )
    # 让 Alembic 按版本顺序调用 upgrade()；离线模式不会在 MySQL 中开启事务。
    with context.begin_transaction():
        context.run_migrations()


def apply_migrations(connection: Connection) -> None:
    """把 Alembic 迁移操作绑定到传入的数据库连接。"""
    # 这段函数供下方 run_sync 调用；迁移文件里的 op.create_table 会使用这条连接。
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """从环境配置取地址，通过 asyncmy 异步连接真实 MySQL 并执行迁移。"""
    # NullPool 表示这次命令结束后不保留数据库连接；迁移不是常驻的 API 服务。
    engine = create_async_engine(get_settings().database_url, poolclass=NullPool)
    try:
        # async with 保证连接用完后归还；这里才会尝试连接 MySQL。
        async with engine.connect() as connection:
            # Alembic 的操作接口是同步形式；run_sync 将它适配到异步连接上。
            # 数据库 I/O 仍由异步引擎和 asyncmy 驱动完成。
            await connection.run_sync(apply_migrations)
    finally:
        # 即使连接或迁移失败，也释放引擎持有的资源。
        await engine.dispose()


# 带 --sql 的命令进入离线分支；不带 --sql 的真实升级命令进入在线分支。
# asyncio.run 只负责为本次命令启动事件循环，不会在 FastAPI 请求中运行。
if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
