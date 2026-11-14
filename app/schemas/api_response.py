from pydantic import BaseModel, ConfigDict, Field


class ValidationIssue(BaseModel):
    """请求参数校验问题。"""

    field: str = Field(title="字段")
    message: str = Field(title="问题")


class APIResponse(BaseModel):
    """统一的 API 错误响应。"""

    model_config = ConfigDict(title="错误响应")

    code: int = Field(title="HTTP 状态码")
    message: str = Field(title="错误信息")
    error_code: str | None = Field(default=None, title="稳定的业务错误标识")
    errors: list[ValidationIssue] | None = Field(default=None, title="参数校验问题")
