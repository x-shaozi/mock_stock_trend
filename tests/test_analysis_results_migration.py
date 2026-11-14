"""离线检查逐日分析结果迁移的版本顺序、建表 SQL 和回退 SQL。"""

from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

from alembic import command


def _migration_config() -> Config:
    """读取项目根目录的 Alembic 配置；离线执行不连接 MySQL。"""
    project_root = Path(__file__).resolve().parents[1]
    return Config(str(project_root / "alembic.ini"))


def test_analysis_results_follows_analysis_runs() -> None:
    """结果迁移紧接轮次迁移；后续迁移可以继续接在结果表之后。"""
    script = ScriptDirectory.from_config(_migration_config())
    revision = script.get_revision("20261113_04_analysis_results")

    assert revision.down_revision == "20261113_03_create_analysis_runs"


def test_analysis_results_migration_generates_expected_mysql_sql(capsys) -> None:
    """从轮次版本离线升级，只生成结果表与 Alembic 版本更新。"""
    # 明确起点可避免把已验收的前三张表混入本测试的输出。
    command.upgrade(
        _migration_config(), "20261113_03_create_analysis_runs:head", sql=True
    )
    sql = capsys.readouterr().out

    assert "CREATE TABLE analysis_results" in sql
    assert "close_price NUMERIC(18, 6) NOT NULL" in sql
    assert "ma5 NUMERIC(18, 6)" in sql
    assert "rsi14 NUMERIC(8, 4)" in sql
    assert "trend_score INTEGER" in sql
    assert "FOREIGN KEY(analysis_run_id) REFERENCES analysis_runs (id)" in sql
    assert (
        "CONSTRAINT uq_analysis_results_run_date UNIQUE (analysis_run_id, trade_date)"
    ) in sql
    assert "CREATE TABLE analysis_runs" not in sql
    assert "20261113_04_analysis_results" in sql


def test_analysis_results_migration_generates_rollback_sql(capsys) -> None:
    """离线回退第四版，只生成删除结果表及版本号回退的 SQL。"""
    command.downgrade(
        _migration_config(), "head:20261113_03_create_analysis_runs", sql=True
    )
    sql = capsys.readouterr().out

    assert "DROP TABLE analysis_results" in sql
    assert "DROP TABLE analysis_runs" not in sql
    assert "DROP TABLE daily_prices" not in sql
    assert "DROP TABLE stocks" not in sql
