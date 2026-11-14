"""定义一只股票在一个已完成交易日的行情表结构。"""

from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    TIMESTAMP,
    BigInteger,
    Date,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.stock import Stock


class DailyPrice(Base):
    """保存一只股票在一个已完成交易日的开高低收、成交量及来源。"""

    __tablename__ = "daily_prices"
    __table_args__ = (
        # 同一只股票、同一个交易日只保留一条选定来源的日线。
        # 后续重新采集该交易日时，应更新原有行，而不是插入第二行。
        UniqueConstraint("stock_id", "trade_date", name="uk_stock_date"),
        {"comment": "股票日价格表"},
    )

    # 每条日线自己的编号，由数据库自动生成。
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # 外键指向 stocks.id，说明这条行情属于哪只股票。
    # 与 Stock 的物理外键关联由数据库约束保障。
    stock_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("stocks.id"), nullable=False
    )
    # 使用交易所当地的交易日期；不是采集程序运行的日期。
    trade_date: Mapped[date] = mapped_column(Date, nullable=False)

    # 四个价格来自同一条已完成日线，且必须采用同一种调整后价格口径。
    # Decimal 与 Numeric(18, 6) 用于保存来源提供的小数价格。
    open_price: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    high_price: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    low_price: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    close_price: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)

    # 采集层需先把成交量统一为股数口径，再写入这个整数列。
    volume: Mapped[int] = mapped_column(BigInteger, nullable=False)
    # 币种使用三个字母的代码，例如 CNY 或 USD。
    currency: Mapped[str] = mapped_column(String(3), nullable=False)

    # 记录供应方和其价格调整参数，便于以后追溯同一行数据的来历。
    # 例如腾讯证券使用 source=tencent、adjustment=qfq；
    # Twelve Data 使用 source=twelvedata、adjustment=all。
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    adjustment: Mapped[str] = mapped_column(String(16), nullable=False)

    # 新增时由数据库填写；以后刷新旧行时，入库代码必须主动更新此字段。
    # TIMESTAMP 会受数据库连接时区影响，首次业务写入前须统一为 UTC。
    fetched_at: Mapped[datetime] = mapped_column(
        TIMESTAMP,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )

    # 每条日线所属的股票；由 Repository 按需显式加载。
    stock: Mapped["Stock"] = relationship(
        back_populates="daily_prices",
        lazy="raise",
    )
