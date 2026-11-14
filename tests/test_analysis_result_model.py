"""离线检查分析结果模型能够与分析轮次共存，以及预期的 MySQL 表结构。"""

from datetime import date
from decimal import Decimal

from sqlalchemy import Numeric, UniqueConstraint
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import configure_mappers
from sqlalchemy.schema import CreateTable

from app.models.analysis_result import AnalysisResult
from app.models.analysis_run import AnalysisRun
from app.models.stock import Stock


def test_analysis_result_can_be_configured_with_analysis_run() -> None:
    """分析结果可以指向一轮分析；创建 Python 对象不会连接数据库。"""
    configure_mappers()

    # 两次分析可以包含同一交易日；通过不同的轮次编号区分它们。
    result_90 = AnalysisResult(
        analysis_run_id=7,
        trade_date=date(2026, 11, 12),
        close_price=Decimal("52.240000"),
    )
    result_100 = AnalysisResult(
        analysis_run_id=8,
        trade_date=date(2026, 11, 12),
        close_price=Decimal("52.240000"),
    )

    assert Stock.__table__.name == "stocks"
    assert AnalysisRun.__table__.name == "analysis_runs"
    assert result_90.analysis_run_id == 7
    assert result_100.analysis_run_id == 8
    assert result_90.trade_date == result_100.trade_date
    assert result_90.close_price == Decimal("52.240000")
    # 没有传入的指标和评分保持为空；以后有足够历史时才由业务层填写。
    assert result_90.ma5 is None
    assert result_90.trend_score is None


def test_analysis_result_mysql_table_contract() -> None:
    """检查轮次外键、轮次内的交易日唯一性及指标的空值和精度。"""
    table = AnalysisResult.__table__
    columns = table.columns
    unique_constraints = [
        constraint
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    ]

    assert table.name == "analysis_results"
    assert table.comment == "股票分析结果表"
    assert [column.name for column in table.primary_key.columns] == ["id"]
    assert {key.target_fullname for key in columns["analysis_run_id"].foreign_keys} == {
        "analysis_runs.id"
    }
    assert len(unique_constraints) == 1
    assert unique_constraints[0].name == "uq_analysis_results_run_date"
    assert [column.name for column in unique_constraints[0].columns] == [
        "analysis_run_id",
        "trade_date",
    ]
    for name in ("analysis_run_id", "trade_date", "close_price"):
        assert not columns[name].nullable
    for name in (
        "ma5",
        "ma20",
        "rsi14",
        "macd",
        "trend_score",
        "trend_label",
        "summary",
    ):
        assert columns[name].nullable
    for name in ("close_price", "ma5", "ma20", "macd"):
        assert isinstance(columns[name].type, Numeric)
        assert (columns[name].type.precision, columns[name].type.scale) == (18, 6)
    assert isinstance(columns["rsi14"].type, Numeric)
    assert (columns["rsi14"].type.precision, columns["rsi14"].type.scale) == (8, 4)

    # 只把模型翻译成 MySQL SQL 文本，检查字段和约束，不执行真实建表。
    ddl = str(CreateTable(table).compile(dialect=mysql.dialect()))
    assert "FOREIGN KEY(analysis_run_id) REFERENCES analysis_runs (id)" in ddl
    assert "UNIQUE (analysis_run_id, trade_date)" in ddl
    assert "close_price NUMERIC(18, 6) NOT NULL" in ddl
    assert "trend_score INTEGER" in ddl
