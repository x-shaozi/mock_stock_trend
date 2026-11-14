"""创建股票基础信息表。"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision 是本次迁移的唯一编号；Alembic 用它记录数据库已执行到哪一版。
revision: str = "20261113_01_create_stocks"
# 这是项目的第一份迁移，没有上一版，所以 down_revision 为 None。
down_revision: str | None = None
# 以下两项用于更复杂的分支迁移；当前没有分支或额外依赖。
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """向前迁移一版：创建保存股票基础信息的 stocks 表。"""
    # op.create_table 描述真正执行迁移时要建立的表；离线模式只把它编译成 SQL。
    op.create_table(
        "stocks",
        # id 是数据库自动递增的主键，之后的行情表可用它关联一只股票。
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("symbol", sa.String(length=20), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        # 市场必须显式填写，例如 CN 或 US，避免遗漏时被默认归入错误市场。
        sa.Column("market", sa.String(length=2), nullable=False),
        # 不传 created_at 时由 MySQL 填当前时间；连接时区需在真实使用前统一。
        sa.Column(
            "created_at",
            sa.TIMESTAMP(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        # 同一市场的同一代码只能出现一次；不同市场可使用相同代码。
        sa.UniqueConstraint("market", "symbol", name="uq_stocks_market_symbol"),
        comment="股票表",
    )


def downgrade() -> None:
    """向后回退一版：删除 stocks 表；真实执行会一并删除表内数据。"""
    op.drop_table("stocks")
