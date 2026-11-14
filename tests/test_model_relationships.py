"""检查四张表的 ORM 导航属性与数据库外键方向一致。"""

import pytest
from sqlalchemy.orm import configure_mappers

from app.models import AnalysisResult, AnalysisRun, DailyPrice, Stock


@pytest.mark.parametrize(
    ("parent", "collection", "child", "reference"),
    [
        (Stock, "daily_prices", DailyPrice, "stock"),
        (Stock, "analysis_runs", AnalysisRun, "stock"),
        (AnalysisRun, "results", AnalysisResult, "analysis_run"),
    ],
)
def test_relationship_pairs_are_bidirectional_and_do_not_lazy_load(
    parent: type, collection: str, child: type, reference: str
) -> None:
    """逐对验证目标类、反向属性和异步项目约定的禁止隐式查询。"""
    configure_mappers()
    parent_side = parent.__mapper__.relationships[collection]
    child_side = child.__mapper__.relationships[reference]

    assert parent_side.mapper.class_ is child
    assert child_side.mapper.class_ is parent
    assert parent_side.back_populates == reference
    assert child_side.back_populates == collection
    assert parent_side.uselist is True
    assert child_side.uselist is False
    assert parent_side.lazy == child_side.lazy == "raise"


def test_relationships_follow_only_the_three_existing_foreign_keys() -> None:
    """分析结果通过批次找股票，不额外制造一条直接的 ORM 关系。"""
    assert set(Stock.__mapper__.relationships.keys()) == {
        "daily_prices",
        "analysis_runs",
    }
    assert set(AnalysisRun.__mapper__.relationships.keys()) == {"stock", "results"}
    assert set(DailyPrice.__mapper__.relationships.keys()) == {"stock"}
    assert set(AnalysisResult.__mapper__.relationships.keys()) == {"analysis_run"}
    assert str(AnalysisRun.__mapper__.relationships["results"].order_by[0]) == (
        "analysis_results.trade_date"
    )
