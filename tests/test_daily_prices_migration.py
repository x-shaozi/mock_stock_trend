"""离线检查日线表是股票表之后的下一份迁移。"""

from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

from alembic import command


def _migration_config() -> Config:
    """从项目根目录加载 Alembic 配置，不使用真实数据库连接。"""
    project_root = Path(__file__).resolve().parents[1]
    return Config(str(project_root / "alembic.ini"))


def test_daily_prices_follows_stocks() -> None:
    """确认日线迁移紧接股票迁移；后续版本不会改变这段顺序。"""
    script = ScriptDirectory.from_config(_migration_config())
    revision = script.get_revision("20261113_02_create_daily_prices")

    assert revision.down_revision == "20261113_01_create_stocks"


def test_daily_prices_migration_generates_expected_mysql_sql(capsys) -> None:
    """只打印第二版的 SQL，检查日线字段及数据库约束。"""
    # 起点设为股票迁移，输出中应只包含尚待执行的日线迁移。
    command.upgrade(
        _migration_config(),
        "20261113_01_create_stocks:20261113_02_create_daily_prices",
        sql=True,
    )
    sql = capsys.readouterr().out

    assert "CREATE TABLE daily_prices" in sql
    assert "close_price NUMERIC(18, 6) NOT NULL" in sql
    assert "fetched_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP" in sql
    assert "CONSTRAINT uk_stock_date UNIQUE (stock_id, trade_date)" in sql
    assert "FOREIGN KEY(stock_id) REFERENCES stocks (id)" in sql
    assert "CREATE TABLE stocks" not in sql


def test_daily_prices_migration_generates_rollback_sql(capsys) -> None:
    """离线回退第二版，只应得到删除日线表的 SQL。"""
    command.downgrade(
        _migration_config(),
        "20261113_02_create_daily_prices:20261113_01_create_stocks",
        sql=True,
    )
    sql = capsys.readouterr().out

    assert "DROP TABLE daily_prices" in sql
    assert "DROP TABLE stocks" not in sql
