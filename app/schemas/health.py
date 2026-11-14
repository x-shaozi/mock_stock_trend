from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class HealthResponse(BaseModel):
    """健康检查响应。"""

    model_config = ConfigDict(title="健康检查响应")

    status: Literal["ok"] = Field(title="状态")
