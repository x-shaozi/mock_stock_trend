"""离线检查股票归档字段迁移；测试不会连接或修改真实 MySQL。"""

from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

from alembic import command


def _migration_config() -> Config:
    """从项目根目录读取 Alembic 配置，避免依赖命令执行时所在目录。"""
    project_root = Path(__file__).resolve().parents[1]
    return Config(str(project_root / "alembic.ini"))


def test_stock_archive_follows_analysis_results_as_latest_revision() -> None:
    """归档迁移应接在第四版之后，且迁移链只有一个最新版本。"""
    script = ScriptDirectory.from_config(_migration_config())
    revision = script.get_revision("20261114_05_stock_archived_at")

    assert revision.down_revision == "20261113_04_analysis_results"
    assert script.get_heads() == ["20261114_05_stock_archived_at"]


def test_stock_archive_migration_generates_expected_mysql_sql(capsys) -> None:
    """离线升级只增加可空归档列，不重建股票表或其他业务表。"""
    # 起点是已验收的第四版；sql=True 只打印 SQL，不连接 MySQL。
    command.upgrade(_migration_config(), "20261113_04_analysis_results:head", sql=True)
    sql = capsys.readouterr().out

    assert "ALTER TABLE stocks ADD COLUMN archived_at TIMESTAMP NULL" in sql
    assert "CREATE TABLE stocks" not in sql
    assert "DROP TABLE stocks" not in sql
    assert "20261114_05_stock_archived_at" in sql


def test_stock_archive_migration_generates_rollback_sql(capsys) -> None:
    """离线回退只删除归档列，不删除股票或其他业务表。"""
    command.downgrade(
        _migration_config(), "head:20261113_04_analysis_results", sql=True
    )
    sql = capsys.readouterr().out

    assert "ALTER TABLE stocks DROP COLUMN archived_at" in sql
    assert "DROP TABLE stocks" not in sql
    assert "DROP TABLE daily_prices" not in sql
    assert "DROP TABLE analysis_runs" not in sql
    assert "DROP TABLE analysis_results" not in sql
