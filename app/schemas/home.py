"""定义 API 首页返回给浏览器的固定信息。"""

from pydantic import BaseModel, ConfigDict, Field


class HomeResponse(BaseModel):
    """首页响应；只列出服务名称和可访问的入口地址。"""

    model_config = ConfigDict(title="首页响应")

    name: str = Field(title="服务名称")
    docs: str = Field(title="接口文档地址")
    health: str = Field(title="健康检查地址")
