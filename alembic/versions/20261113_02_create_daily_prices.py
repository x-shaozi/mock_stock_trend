"""在股票表之后创建日线行情表。"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# 迁移编号标识这一版；上一版是已创建 stocks 表的迁移。
revision: str = "20261113_02_create_daily_prices"
down_revision: str | None = "20261113_01_create_stocks"
# 当前只有一条线性的迁移链，不使用分支或其他版本依赖。
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """创建一只股票在一个已完成交易日对应一行的日线表。"""
    # 离线模式会把下面的表结构打印成 SQL；在线模式才会交给 MySQL 执行。
    op.create_table(
        "daily_prices",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        # stock_id 指向已存在的 stocks.id；trade_date 是交易所当地的日期。
        sa.Column("stock_id", sa.Integer(), nullable=False),
        sa.Column("trade_date", sa.Date(), nullable=False),
        # 四个价格保存统一调整口径后的数值，最多保留 6 位小数。
        sa.Column("open_price", sa.Numeric(precision=18, scale=6), nullable=False),
        sa.Column("high_price", sa.Numeric(precision=18, scale=6), nullable=False),
        sa.Column("low_price", sa.Numeric(precision=18, scale=6), nullable=False),
        sa.Column("close_price", sa.Numeric(precision=18, scale=6), nullable=False),
        # 成交量由采集层转换为股数；来源字段使价格口径可追溯。
        sa.Column("volume", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("adjustment", sa.String(length=16), nullable=False),
        # 首次写入时由数据库填写；日后刷新旧行时由入库代码更新。
        sa.Column(
            "fetched_at",
            sa.TIMESTAMP(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        # 外键保证日线必须属于一只已存在的股票。
        sa.ForeignKeyConstraint(["stock_id"], ["stocks.id"]),
        # 重复采集同一交易日时更新旧行，不允许插入第二行。
        sa.UniqueConstraint("stock_id", "trade_date", name="uk_stock_date"),
        comment="股票日价格表",
    )


def downgrade() -> None:
    """回退这一版，只删除 daily_prices 表；真实执行会删除其中的数据。"""
    op.drop_table("daily_prices")
