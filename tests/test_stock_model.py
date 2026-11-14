"""验证股票模型与关联模型能共同映射，并生成预期的 MySQL 表结构。"""

from sqlalchemy import UniqueConstraint
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import configure_mappers
from sqlalchemy.schema import CreateTable

from app.models import Stock


def test_stock_model_configures_with_registered_related_models() -> None:
    """模型包已登记四张表，股票对象仍可正常创建。"""
    configure_mappers()

    stock = Stock(symbol="688385.SH", name="复旦微电", market="CN")

    assert stock.symbol == "688385.SH"
    assert stock.name == "复旦微电"
    assert stock.market == "CN"


def test_stock_mysql_table_contract() -> None:
    """检查关键数据库约束；不连接或创建真实数据库。"""
    table = Stock.__table__
    columns = table.columns
    unique_constraints = [
        constraint
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    ]

    assert table.name == "stocks"
    assert table.comment == "股票表"
    assert [column.name for column in table.primary_key.columns] == ["id"]
    assert len(unique_constraints) == 1
    assert unique_constraints[0].name == "uq_stocks_market_symbol"
    assert [column.name for column in unique_constraints[0].columns] == [
        "market",
        "symbol",
    ]
    assert all(not columns[name].nullable for name in ("symbol", "name", "market"))
    assert columns["market"].server_default is None
    assert not columns["created_at"].nullable
    assert columns["created_at"].server_default is not None
    # 归档列没有自动时间：新股票和旧股票都先保持正常状态。
    assert columns["archived_at"].nullable
    assert columns["archived_at"].server_default is None

    ddl = str(CreateTable(table).compile(dialect=mysql.dialect()))
    assert "UNIQUE (market, symbol)" in ddl
    assert "created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP" in ddl
    assert "archived_at TIMESTAMP" in ddl
