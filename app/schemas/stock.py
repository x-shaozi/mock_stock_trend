"""股票新增、搜索、列表、归档与恢复接口使用的请求和响应模型。"""

import re
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class StockCreate(BaseModel):
    """用户提交代码和市场；名称由服务端从股票目录重新核对。"""

    symbol: str = Field(min_length=1, max_length=20, description="股票代码")
    name: str | None = Field(
        default=None,
        max_length=100,
        deprecated=True,
        description="旧版可选字段；即使填写，保存时也以股票目录中的名称为准",
    )
    market: Literal["CN", "US"] = Field(description="股票市场")

    @field_validator("symbol", mode="before")
    @classmethod
    def normalize_symbol(cls, value: object) -> object:
        """去掉输入两端的空格，并统一代码字母的大小写。"""
        # 先规范化再做长度检查，让带有无意空格的合法代码可以通过。
        return value.strip().upper() if isinstance(value, str) else value

    @field_validator("market", mode="before")
    @classmethod
    def normalize_market(cls, value: object) -> object:
        """允许输入小写市场代码，内部统一使用 CN 或 US。"""
        return value.strip().upper() if isinstance(value, str) else value

    @model_validator(mode="after")
    def validate_symbol_for_market(self) -> Self:
        """按市场检查代码格式，避免无法判断交易所的 A 股代码。"""
        if self.market == "CN":
            # .SS 是上海市场的另一种常见后缀；库内统一保存为 .SH。
            if self.symbol.endswith(".SS"):
                self.symbol = f"{self.symbol[:-3]}.SH"
            if re.fullmatch(r"\d{6}\.(SH|SZ)", self.symbol) is None:
                raise ValueError("A 股代码应为六位数字加 .SH 或 .SZ 后缀")
        elif re.fullmatch(r"[A-Z][A-Z0-9.-]{0,19}", self.symbol) is None:
            raise ValueError("美股代码应以字母开头，只包含字母、数字、点或连字符")
        return self


class StockResponse(BaseModel):
    """新增与列表共用的股票编号和基础信息。"""

    # from_attributes 允许 Pydantic 从 SQLAlchemy Stock 对象读取同名属性。
    model_config = ConfigDict(from_attributes=True)

    id: int
    symbol: str
    name: str
    market: Literal["CN", "US"]


class StockArchiveResponse(BaseModel):
    """归档成功后告诉调用方：哪只股票已处于归档状态。"""

    id: int
    symbol: str
    status: Literal["archived"]


class StockRestoreResponse(BaseModel):
    """恢复成功后告诉调用方：哪只股票已回到正常状态。"""

    id: int
    symbol: str
    status: Literal["active"]


class StockListQuery(BaseModel):
    """股票列表的查看方式和分页参数；这些值来自 URL 查询参数。"""

    # 不填写状态时只看正常股票，避免日后归档股票仍出现在日常列表。
    status: Literal["active", "archived"] = Field(
        default="active", description="股票状态：active 正常，archived 已归档"
    )
    page: int = Field(default=1, ge=1, description="页码，从 1 开始")
    page_size: int = Field(
        default=20, ge=1, le=100, description="每页条数，最多 100 条"
    )


class StockListResponse(BaseModel):
    """同时返回当前页股票和总条数，供前端计算页数。"""

    items: list[StockResponse]
    total: int
    page: int
    page_size: int


class StockSearchQuery(BaseModel):
    """搜索条件来自 URL；必须说明市场，并输入代码或名称。"""

    market: Literal["CN", "US"] = Field(description="股票市场：CN 或 US")
    query: str = Field(min_length=1, max_length=50, description="股票代码或名称")

    @field_validator("market", mode="before")
    @classmethod
    def normalize_search_market(cls, value: object) -> object:
        """允许用户输入小写市场代码，内部统一成大写。"""
        return value.strip().upper() if isinstance(value, str) else value

    @field_validator("query", mode="before")
    @classmethod
    def normalize_search_query(cls, value: object) -> object:
        """先去掉两端空格，再由 Field 检查是否为空。"""
        return value.strip() if isinstance(value, str) else value


class StockCandidateResponse(BaseModel):
    """外部目录中的候选项，还没有本地 stocks.id。"""

    model_config = ConfigDict(from_attributes=True)

    symbol: str
    name: str
    market: Literal["CN", "US"]
    exchange: str


class StockSearchResponse(BaseModel):
    """候选项列表；没有匹配时 items 是空数组。"""

    items: list[StockCandidateResponse]
