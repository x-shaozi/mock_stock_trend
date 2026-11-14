"""发起趋势分析接口的请求和响应格式。"""

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class AnalysisRunRequest(BaseModel):
    """days 是参与计算的交易日条数，不只是页面显示的条数。"""

    days: int = Field(default=90, ge=35, le=260, description="最近多少条已存日线")


class AnalysisRunListQuery(BaseModel):
    """批次列表的分页条件来自 URL，规则与股票列表一致。"""

    page: int = Field(default=1, ge=1, description="页码，从 1 开始")
    page_size: int = Field(
        default=20, ge=1, le=100, description="每页条数，最多 100 条"
    )


class AnalysisRunListItem(BaseModel):
    """列表只显示辨认一轮分析所需的信息，不带每日指标。"""

    run_id: int
    requested_days: int
    start_date: date
    end_date: date
    source: str
    adjustment: str
    rule_version: str
    computed_at: datetime


class AnalysisRunListResponse(BaseModel):
    """股票身份、当前页批次及总条数。"""

    stock_id: int
    symbol: str
    market: str
    items: list[AnalysisRunListItem]
    total: int
    page: int
    page_size: int


class LatestAnalysis(BaseModel):
    """这一轮分析最后一个交易日的指标与评分。"""

    trade_date: date
    close_price: Decimal
    ma5: Decimal
    ma20: Decimal
    rsi14: Decimal
    macd: Decimal
    trend_score: int
    trend_label: str
    summary: str


class AnalysisRunResponse(BaseModel):
    """同时给出批次身份、输入范围和最新一天的结果。"""

    run_id: int
    stock_id: int
    symbol: str
    requested_days: int
    start_date: date
    end_date: date
    source: str
    adjustment: str
    rule_version: str
    saved: int
    latest: LatestAnalysis


class AnalysisResultItem(BaseModel):
    """一轮分析中的一天；历史不足时，尚未算出的指标保持为空。"""

    model_config = ConfigDict(from_attributes=True)

    trade_date: date
    close_price: Decimal
    ma5: Decimal | None
    ma20: Decimal | None
    rsi14: Decimal | None
    macd: Decimal | None
    trend_score: int | None
    trend_label: str | None
    summary: str | None


class AnalysisRunDetailResponse(BaseModel):
    """已保存分析批次及其全部逐日结果，不包含重新计算的内容。"""

    run_id: int
    stock_id: int
    symbol: str
    market: str
    requested_days: int
    start_date: date
    end_date: date
    source: str
    adjustment: str
    rule_version: str
    computed_at: datetime
    saved: int
    items: list[AnalysisResultItem]
