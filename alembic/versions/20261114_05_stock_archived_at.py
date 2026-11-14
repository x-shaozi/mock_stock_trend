"""为股票表增加可空的归档时间，不改动现有股票记录。"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision 是本次迁移的编号；down_revision 指向紧邻的上一版。
# Alembic 按这条版本链决定升级和回退的顺序。
revision: str = "20261114_05_stock_archived_at"
down_revision: str | None = "20261113_04_analysis_results"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """为 stocks 加上 archived_at；已有记录的该值为空，表示仍正常使用。"""
    # 这里只描述表结构变更。带 --sql 运行时仅打印 SQL；在线升级才修改 MySQL。
    # 允许 NULL，因而无需为现有股票指定虚构的归档时间。
    op.add_column("stocks", sa.Column("archived_at", sa.TIMESTAMP(), nullable=True))


def downgrade() -> None:
    """回退本次迁移，移除归档时间列及其中已保存的时间。"""
    # 回退会丢失 archived_at 中的数据；不会删除 stocks 表或股票记录。
    op.drop_column("stocks", "archived_at")
