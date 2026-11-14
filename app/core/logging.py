import sys

from loguru import logger

from app.core.config import get_settings


def configure_logging() -> None:
    """统一配置应用日志输出级别。"""
    logger.remove()
    logger.add(sys.stderr, level=get_settings().log_level.upper())
