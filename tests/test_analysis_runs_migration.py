"""离线检查 analysis_runs 迁移的版本顺序、建表 SQL 和回退 SQL。"""

from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

from alembic import command


def _migration_config() -> Config:
    """读取项目根目录的 Alembic 配置；离线模式不会连接真实数据库。"""
    project_root = Path(__file__).resolve().parents[1]
    return Config(str(project_root / "alembic.ini"))


def test_analysis_runs_follows_daily_prices() -> None:
    """确认分析轮次迁移接在日线迁移后面；后续版本不改变此顺序。"""
    script = ScriptDirectory.from_config(_migration_config())
    revision = script.get_revision("20261113_03_create_analysis_runs")

    assert revision.down_revision == "20261113_02_create_daily_prices"


def test_analysis_runs_migration_generates_expected_mysql_sql(capsys) -> None:
    """从日线版本离线升级，只应生成分析轮次表及版本号更新语句。"""
    # 起点设为日线版本，避免把已验收的股票和日线建表语句也算进来。
    command.upgrade(
        _migration_config(),
        "20261113_02_create_daily_prices:20261113_03_create_analysis_runs",
        sql=True,
    )
    sql = capsys.readouterr().out

    assert "CREATE TABLE analysis_runs" in sql
    assert "requested_days INTEGER NOT NULL" in sql
    assert "computed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP" in sql
    assert (
        "CONSTRAINT uq_analysis_runs_request "
        "UNIQUE (stock_id, requested_days, end_date, rule_version)"
    ) in sql
    assert "FOREIGN KEY(stock_id) REFERENCES stocks (id)" in sql
    assert "CREATE TABLE daily_prices" not in sql
    assert "20261113_03_create_analysis_runs" in sql


def test_analysis_runs_migration_generates_rollback_sql(capsys) -> None:
    """离线回退第三版，只应输出删除分析轮次表的语句。"""
    command.downgrade(
        _migration_config(),
        "20261113_03_create_analysis_runs:20261113_02_create_daily_prices",
        sql=True,
    )
    sql = capsys.readouterr().out

    assert "DROP TABLE analysis_runs" in sql
    assert "DROP TABLE daily_prices" not in sql
    assert "DROP TABLE stocks" not in sql
