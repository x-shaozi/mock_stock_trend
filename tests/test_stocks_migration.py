"""离线检查股票表迁移，不需要启动或连接 MySQL。"""

from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

from alembic import command


def _migration_config() -> Config:
    """使用项目根目录的配置，避免测试受当前工作目录影响。"""
    # __file__ 是本测试文件；parents[1] 从 tests/ 返回项目根目录。
    project_root = Path(__file__).resolve().parents[1]
    return Config(str(project_root / "alembic.ini"))


def test_stocks_is_the_first_migration() -> None:
    """股票表是迁移链的起点；后续迁移接在它之后。"""
    script = ScriptDirectory.from_config(_migration_config())

    assert script.get_revision("20261113_01_create_stocks").down_revision is None


def test_stocks_migration_generates_mysql_sql_without_database(capsys) -> None:
    """让 Alembic 离线打印升级 SQL，再检查关键建表内容。"""
    # sql=True 对应命令行的 --sql：只生成文字，不连接或修改数据库。
    command.upgrade(_migration_config(), "20261113_01_create_stocks", sql=True)
    # capsys 是 pytest 提供的输出捕获工具；out 是 Alembic 打印的 SQL。
    sql = capsys.readouterr().out

    # 同时检查股票表本身，以及 Alembic 用于记录迁移版本的表。
    assert "CREATE TABLE stocks" in sql
    assert "market VARCHAR(2) NOT NULL" in sql
    assert "created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP" in sql
    assert "CONSTRAINT uq_stocks_market_symbol UNIQUE (market, symbol)" in sql
    assert "alembic_version" in sql


def test_stocks_migration_generates_rollback_sql(capsys) -> None:
    """只离线回退第一版，检查生成的 SQL 删除股票表。"""
    # 指定起始版本，避免将后续的日线表回退也算进这个测试。
    command.downgrade(_migration_config(), "20261113_01_create_stocks:base", sql=True)
    sql = capsys.readouterr().out

    assert "DROP TABLE stocks" in sql
    assert "DELETE FROM alembic_version" in sql
