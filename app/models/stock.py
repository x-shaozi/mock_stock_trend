"""将股票基础信息映射为 stocks 数据库表。"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import TIMESTAMP, Integer, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.analysis_run import AnalysisRun
    from app.models.daily_price import DailyPrice


class Stock(Base):
    """一只股票的基础信息。"""

    __tablename__ = "stocks"
    __table_args__ = (
        # 同一市场中，一个股票代码只能保存一次。
        UniqueConstraint("market", "symbol", name="uq_stocks_market_symbol"),
        {"comment": "股票表"},
    )

    # 主键由数据库自动生成，用于关联这只股票的其他记录。
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # A 股使用包含交易所后缀的代码，如 688385.SH；美股如 AAPL。
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)

    # 必须明确传入 CN 或 US；此处不设置默认市场。
    market: Mapped[str] = mapped_column(String(2), nullable=False)

    # 插入数据库时由数据库填写，创建时间不能为空。
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )

    # NULL 表示仍在正常使用；归档时记录 UTC 时间，便于日后知道何时归档。
    # 旧股票记录在迁移后此列为 NULL，因此仍属于正常状态。
    archived_at: Mapped[datetime | None] = mapped_column(TIMESTAMP, nullable=True)

    # 一只股票对应多条已存储的日线；查询时应显式加载或按条件读取。
    daily_prices: Mapped[list["DailyPrice"]] = relationship(
        back_populates="stock",
        lazy="raise",
    )

    # 一只股票可以有多轮趋势分析。
    analysis_runs: Mapped[list["AnalysisRun"]] = relationship(
        back_populates="stock",
        lazy="raise",
    )
