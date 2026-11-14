"""离线检查分析轮次模型的映射、外键和 MySQL 建表约束。"""

from datetime import date

from sqlalchemy import UniqueConstraint
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import configure_mappers
from sqlalchemy.schema import CreateTable

from app.models.analysis_run import AnalysisRun
from app.models.stock import Stock


def test_analysis_run_can_be_configured_with_stock() -> None:
    """模型能与股票模型一起登记；这里只创建 Python 对象，不连接 MySQL。"""
    configure_mappers()

    # 两轮分析可以针对同一股票和同一结束日期，但使用不同的日线条数。
    run_90 = AnalysisRun(
        stock_id=1,
        requested_days=90,
        start_date=date(2026, 7, 1),
        end_date=date(2026, 11, 12),
        source="tencent",
        adjustment="qfq",
        rule_version="v1",
    )
    run_100 = AnalysisRun(
        stock_id=1,
        requested_days=100,
        start_date=date(2026, 6, 17),
        end_date=date(2026, 11, 12),
        source="tencent",
        adjustment="qfq",
        rule_version="v1",
    )

    assert Stock.__table__.name == "stocks"
    assert run_90.stock_id == run_100.stock_id == 1
    assert run_90.requested_days == 90
    assert run_100.requested_days == 100
    assert run_90.end_date == run_100.end_date
    # 数据库默认值只有真正执行 INSERT 时才会产生；Python 对象此时没有计算时间。
    assert run_90.computed_at is None


def test_analysis_run_mysql_table_contract() -> None:
    """检查来源字段必填、股票外键及包含分析天数的唯一约束。"""
    table = AnalysisRun.__table__
    columns = table.columns
    unique_constraints = [
        constraint
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    ]

    assert table.name == "analysis_runs"
    assert table.comment == "股票分析批次表"
    assert [column.name for column in table.primary_key.columns] == ["id"]
    assert {key.target_fullname for key in columns["stock_id"].foreign_keys} == {
        "stocks.id"
    }
    assert len(unique_constraints) == 1
    assert unique_constraints[0].name == "uq_analysis_runs_request"
    assert [column.name for column in unique_constraints[0].columns] == [
        "stock_id",
        "requested_days",
        "end_date",
        "rule_version",
    ]
    for name in (
        "stock_id",
        "requested_days",
        "start_date",
        "end_date",
        "source",
        "adjustment",
        "rule_version",
        "computed_at",
    ):
        assert not columns[name].nullable
    assert columns["computed_at"].server_default is not None

    # CreateTable 只把模型翻译成 SQL 字符串，不会在数据库创建表。
    ddl = str(CreateTable(table).compile(dialect=mysql.dialect()))
    assert "FOREIGN KEY(stock_id) REFERENCES stocks (id)" in ddl
    assert (
        "CONSTRAINT uq_analysis_runs_request "
        "UNIQUE (stock_id, requested_days, end_date, rule_version)"
    ) in ddl
    assert "computed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP" in ddl
