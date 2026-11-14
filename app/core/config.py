from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL


class Settings(BaseSettings):
    """从环境变量或项目根目录的 .env 读取服务配置。"""

    # __file__ 是本文件的位置，不受运行命令的工作目录影响。
    # 从 app/core/config.py 向上两级找到项目根目录，再读取根目录的 .env。
    # 否则 PyCharm 从 app/ 启动脚本时会寻找 app/.env，找不到后悄悄使用
    # 默认的 MySQL 用户 app，股票列表便会因数据库登录失败返回 500。
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[2] / ".env", extra="ignore"
    )

    mysql_host: str = "127.0.0.1"
    mysql_port: int = 3306
    mysql_user: str = "app"
    mysql_password: str = ""
    mysql_database: str = "app"
    redis_url: str = "redis://127.0.0.1:6379/0"
    log_level: str = "INFO"
    # 美股行情服务的个人密钥只从环境变量或本地 .env 读取，不写进代码。
    # 留空时 A 股仍可采集；美股请求会返回清晰的配置错误。
    twelve_data_api_key: str = ""

    @property
    def database_url(self) -> URL:
        """构造可安全转义密码的异步 MySQL 连接地址。"""
        return URL.create(
            "mysql+asyncmy",
            username=self.mysql_user,
            password=self.mysql_password,
            host=self.mysql_host,
            port=self.mysql_port,
            database=self.mysql_database,
        )


@lru_cache
def get_settings() -> Settings:
    """缓存进程内的配置对象。"""
    return Settings()
