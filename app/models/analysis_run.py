"""定义一次股票趋势分析使用了哪些日线及哪一版计算规则。"""

from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    TIMESTAMP,
    Date,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.analysis_result import AnalysisResult
    from app.models.stock import Stock


class AnalysisRun(Base):
    """用户发起的一轮分析；以后每天的分析结果会关联到这一轮。"""

    __tablename__ = "analysis_runs"
    __table_args__ = (
        # 例如同一只股票在同一交易日结束的 90 天和 100 天分析：
        # requested_days 不同，因此数据库允许分别保存这两轮。
        # 同样条件再次分析时，后续业务代码应更新已有轮次及其结果。
        UniqueConstraint(
            "stock_id",
            "requested_days",
            "end_date",
            "rule_version",
            name="uq_analysis_runs_request",
        ),
        {"comment": "股票分析批次表"},
    )

    # 主键由数据库自动生成。后续 AnalysisResult 将通过这个编号找到所属轮次。
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # 外键指向 stocks.id，保证分析的股票在 stocks 表中存在。
    # 同时在 ORM 中通过 stock / Stock.analysis_runs 建立双向关系。
    stock_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("stocks.id"), nullable=False
    )

    # 用户输入的分析天数就是参与计算的日线条数，而不只是图表显示条数。
    requested_days: Mapped[int] = mapped_column(Integer, nullable=False)

    # 分别保存本轮实际取到的第一条和最后一条日线的交易日期。
    # 例如库中有 100 条而用户请求 90 条，start_date 对应最近 90 条中的第一条。
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)

    # 来源及价格调整方式来自本轮使用的日线；入库服务以后须检查这些日线的口径一致。
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    adjustment: Mapped[str] = mapped_column(String(16), nullable=False)

    # 例如 v1；规则变化后可区分旧结果与新结果，不会仅凭日期混用。
    rule_version: Mapped[str] = mapped_column(String(16), nullable=False)

    # 第一次入库时 MySQL 填写当前时间；同条件重算时业务代码须主动更新时间。
    # TIMESTAMP 受数据库连接时区影响，首次写入业务数据前还需统一为 UTC。
    computed_at: Mapped[datetime] = mapped_column(
        TIMESTAMP,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )

    # 本轮分析对应的一只股票。
    stock: Mapped["Stock"] = relationship(
        back_populates="analysis_runs",
        lazy="raise",
    )

    # 本轮分析产生的逐日结果，加载时按照交易日期升序排列。
    results: Mapped[list["AnalysisResult"]] = relationship(
        back_populates="analysis_run",
        lazy="raise",
        order_by="AnalysisResult.trade_date",
    )
