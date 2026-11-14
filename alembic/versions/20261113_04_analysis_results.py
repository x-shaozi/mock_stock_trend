"""在分析轮次表之后创建逐日分析结果表。"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# Alembic 用 revision 标识当前版本，用 down_revision 找到它紧邻的上一版。
# 此编号保持在 alembic_version.version_num 的 32 字符长度以内。
revision: str = "20261113_04_analysis_results"
down_revision: str | None = "20261113_03_create_analysis_runs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """创建一轮分析中每个交易日对应一行的 analysis_results 表。"""
    # --sql 会把这些操作打印为 MySQL SQL；在线升级才会真正修改数据库。
    # 每列的类型与可空规则须和已经验收的 AnalysisResult 模型一致。
    op.create_table(
        "analysis_results",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        # 结果属于 analysis_runs 中的一轮；trade_date 是该行对应的交易日。
        sa.Column("analysis_run_id", sa.Integer(), nullable=False),
        sa.Column("trade_date", sa.Date(), nullable=False),
        # 保存计算时实际使用的收盘价。行情日后修正时应重新计算本轮结果。
        sa.Column("close_price", sa.Numeric(precision=18, scale=6), nullable=False),
        # 各指标有不同的预热期，尚未算出时允许保存 NULL。
        sa.Column("ma5", sa.Numeric(precision=18, scale=6), nullable=True),
        sa.Column("ma20", sa.Numeric(precision=18, scale=6), nullable=True),
        sa.Column("rsi14", sa.Numeric(precision=8, scale=4), nullable=True),
        sa.Column("macd", sa.Numeric(precision=18, scale=6), nullable=True),
        # 前 34 条日线不能形成完整的 v1 评分，三个结果字段允许为空。
        sa.Column("trend_score", sa.Integer(), nullable=True),
        sa.Column("trend_label", sa.String(length=50), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        # 数据库外键阻止结果指向不存在的分析轮次。
        sa.ForeignKeyConstraint(["analysis_run_id"], ["analysis_runs.id"]),
        # 一轮中同一交易日只保存一条；不同轮次可以包含同一天。
        sa.UniqueConstraint(
            "analysis_run_id",
            "trade_date",
            name="uq_analysis_results_run_date",
        ),
        comment="股票分析结果表",
    )


def downgrade() -> None:
    """回退这一版，只删除 analysis_results 表；真实执行会删除其中的数据。"""
    # 回退本版本不删除 analysis_runs，也不改动股票与日线表。
    op.drop_table("analysis_results")
