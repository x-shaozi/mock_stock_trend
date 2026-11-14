"""检查日线模型与股票模型可以共存，并生成约定的 MySQL 表结构。"""

from datetime import date
from decimal import Decimal

from sqlalchemy import Numeric, UniqueConstraint
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import configure_mappers
from sqlalchemy.schema import CreateTable

from app.models.daily_price import DailyPrice
from app.models.stock import Stock


def test_daily_price_model_can_be_configured_with_stock() -> None:
    """模型中的外键应能指向已有股票表；本测试不连接数据库。"""
    configure_mappers()

    price = DailyPrice(
        stock_id=1,
        trade_date=date(2026, 11, 12),
        open_price=Decimal("53.100000"),
        high_price=Decimal("54.310000"),
        low_price=Decimal("52.060000"),
        close_price=Decimal("52.240000"),
        volume=15_725_737,
        currency="CNY",
        source="tencent",
        adjustment="qfq",
    )

    assert Stock.__table__.name == "stocks"
    assert price.stock_id == 1
    assert price.trade_date == date(2026, 11, 12)
    assert price.close_price == Decimal("52.240000")
    assert price.fetched_at is None  # 只有真正插入数据库后，数据库才会填默认时间。


def test_daily_price_mysql_table_contract() -> None:
    """检查外键、交易日唯一性、价格精度和必填来源元数据。"""
    table = DailyPrice.__table__
    columns = table.columns
    unique_constraints = [
        constraint
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    ]

    assert table.name == "daily_prices"
    assert table.comment == "股票日价格表"
    assert [column.name for column in table.primary_key.columns] == ["id"]
    assert {key.target_fullname for key in columns["stock_id"].foreign_keys} == {
        "stocks.id"
    }
    assert len(unique_constraints) == 1
    assert unique_constraints[0].name == "uk_stock_date"
    assert [column.name for column in unique_constraints[0].columns] == [
        "stock_id",
        "trade_date",
    ]
    for name in ("open_price", "high_price", "low_price", "close_price"):
        assert isinstance(columns[name].type, Numeric)
        assert (columns[name].type.precision, columns[name].type.scale) == (18, 6)
    for name in (
        "stock_id",
        "trade_date",
        "volume",
        "currency",
        "source",
        "adjustment",
        "fetched_at",
    ):
        assert not columns[name].nullable
    assert columns["fetched_at"].server_default is not None

    ddl = str(CreateTable(table).compile(dialect=mysql.dialect()))
    assert "FOREIGN KEY(stock_id) REFERENCES stocks (id)" in ddl
    assert "UNIQUE (stock_id, trade_date)" in ddl
    assert "close_price NUMERIC(18, 6) NOT NULL" in ddl
