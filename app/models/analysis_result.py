"""定义一次股票分析中，每个交易日对应的指标和评分。"""

from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Date,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.analysis_run import AnalysisRun


class AnalysisResult(Base):
    """一轮分析中，一个交易日对应的一条计算结果。"""

    __tablename__ = "analysis_results"
    __table_args__ = (
        # 同一轮分析里的同一交易日只能保存一次。
        # 90 天和 100 天的分析属于不同的 AnalysisRun，因此可以各自保存当天结果。
        UniqueConstraint(
            "analysis_run_id",
            "trade_date",
            name="uq_analysis_results_run_date",
        ),
        {"comment": "股票分析结果表"},
    )

    # 每条结果自己的编号，由数据库自动生成。
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # 外键指向 analysis_runs.id。查询所属股票时，可沿着本轮的 stock_id 找到。
    # 同时在 ORM 中通过 analysis_run / AnalysisRun.results 建立双向关系。
    analysis_run_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("analysis_runs.id"), nullable=False
    )

    # 这条结果对应交易所当地的交易日期，而不是运行分析程序的日期。
    trade_date: Mapped[date] = mapped_column(Date, nullable=False)

    # 保存本轮计算实际使用的调整后收盘价，供以后核对指标和评分。
    # 它与 daily_prices.close_price 来自同一输入；行情修正后须重新计算本轮。
    close_price: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)

    # 历史不足时，指标暂时没有值：MA5 从第 5 条日线开始，MA20 从第 20 条，
    # RSI14 从第 15 条，MACD 从第 35 条。None 在数据库中对应 NULL。
    ma5: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    ma20: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    rsi14: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    macd: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)

    # 四项指标齐全后才评分；前 34 条日线的这三个字段均保持为空。
    # 后续业务层负责在保存时让评分、标签和摘要的有无保持一致。
    trend_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    trend_label: Mapped[str | None] = mapped_column(String(50), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    # 每条结果属于一轮分析。
    analysis_run: Mapped["AnalysisRun"] = relationship(
        back_populates="results",
        lazy="raise",
    )
