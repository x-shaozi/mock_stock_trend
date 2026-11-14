"""检查应用创建 MySQL 连接时会设置统一的 UTC 会话时区。"""

from unittest.mock import Mock

from app.core import database


def test_database_engine_configures_utc_for_new_connections(monkeypatch) -> None:
    """检查引擎传给异步驱动的连接初始化命令；本测试不连接 MySQL。"""
    # 用假的引擎工厂代替真正的 create_async_engine：
    # 这样可以检查配置是否传入，而不会打开数据库连接。
    fake_engine = object()
    fake_factory = Mock(return_value=fake_engine)
    monkeypatch.setattr(database, "create_async_engine", fake_factory)

    created_engine = database.create_database_engine()

    assert created_engine is fake_engine
    assert fake_factory.call_count == 1
    # init_command 是 asyncmy 在每条新连接建立后执行的 SQL。
    assert fake_factory.call_args.kwargs["connect_args"] == {
        "init_command": "SET time_zone = '+00:00'"
    }
