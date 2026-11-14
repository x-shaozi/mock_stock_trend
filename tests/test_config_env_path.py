"""防止从 app/ 目录启动时错误读取 app/.env 并使用默认数据库账号。"""

from pathlib import Path

from app.core.config import Settings


def test_env_path_is_project_root_even_when_working_directory_changes(
    monkeypatch,
) -> None:
    """PyCharm 运行脚本可能把工作目录设为 app/；配置必须仍指向项目根目录。"""
    project_root = Path(__file__).resolve().parents[1]
    monkeypatch.chdir(project_root / "app")

    configured_env = Path(Settings.model_config["env_file"])

    assert configured_env.is_absolute()
    assert configured_env == project_root / ".env"
