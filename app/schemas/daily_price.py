"""日线采集和历史查询接口的参数与成功响应。"""

from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class PriceCollectionQuery(BaseModel):
    """days 指最近需要保存的完整交易日数量，而不是自然日数量。"""

    days: int = Field(default=90, ge=1, le=260, description="最近多少条完整日线")


class PriceCollectionResponse(BaseModel):
    """分别告诉调用方多少天被新增、修正或保持原样。"""

    stock_id: int
    symbol: str
    inserted: int
    updated: int
    unchanged: int


class PriceHistoryQuery(BaseModel):
    """查询最近多少个已有交易日，而不是最近多少个自然日。"""

    days: int = Field(default=90, ge=1, le=260, description="最近多少条已存日线")


class DailyPriceItem(BaseModel):
    """一条已入库日线；价格在 JSON 中以字符串保留十进制精度。"""

    # from_attributes 让 Pydantic 直接读取 SQLAlchemy DailyPrice 的属性。
    model_config = ConfigDict(from_attributes=True)

    trade_date: date
    open_price: Decimal
    high_price: Decimal
    low_price: Decimal
    close_price: Decimal
    volume: int
    currency: str
    source: str
    adjustment: str


class PriceHistoryResponse(BaseModel):
    """股票身份和最近的已存日线；未采集时 items 是空数组。"""

    stock_id: int
    symbol: str
    market: Literal["CN", "US"]
    items: list[DailyPriceItem]
