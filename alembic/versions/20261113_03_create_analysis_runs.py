"""在日线行情表之后创建分析轮次表。"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision 是本次迁移的编号；down_revision 指向已建立 daily_prices 的上一版。
# Alembic 会根据这两个编号决定升级或回退时执行版本文件的顺序。
revision: str = "20261113_03_create_analysis_runs"
down_revision: str | None = "20261113_02_create_daily_prices"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """建立保存每次分析输入范围及规则版本的 analysis_runs 表。"""
    # 使用 --sql 时只会打印建表 SQL；在线升级时才会交给 MySQL 执行。
    # 列的名称、类型、非空要求和默认值与 AnalysisRun 模型保持一致。
    op.create_table(
        "analysis_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        # 一轮分析属于已有的一只股票；外键在本次建表的末尾声明。
        sa.Column("stock_id", sa.Integer(), nullable=False),
        # 用户请求 90 天就使用最近 90 条日线；实际首尾交易日单独保存。
        sa.Column("requested_days", sa.Integer(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        # 来源与调整参数记录本轮使用的价格口径，规则版本区分算法变化。
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("adjustment", sa.String(length=16), nullable=False),
        sa.Column("rule_version", sa.String(length=16), nullable=False),
        # 首次插入时由 MySQL 给出时间；以后重算须由业务代码更新此列。
        sa.Column(
            "computed_at",
            sa.TIMESTAMP(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["stock_id"], ["stocks.id"]),
        # 同一股票、结束日期和规则版本下，90 天与 100 天各自占一轮。
        # 同样条件再次分析时，后续入库代码应更新已有轮次，而非重复插入。
        sa.UniqueConstraint(
            "stock_id",
            "requested_days",
            "end_date",
            "rule_version",
            name="uq_analysis_runs_request",
        ),
        comment="股票分析批次表",
    )


def downgrade() -> None:
    """回退这一版，只删除 analysis_runs 表；真实执行会删除其中的数据。"""
    # 本轮仅建立这一张表，因此回退不触及 stocks 或 daily_prices。
    op.drop_table("analysis_runs")
