"""定义所有 SQLAlchemy 数据库模型共用的基础类。"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """所有数据库模型共同继承的基类，用来收集表结构。"""
