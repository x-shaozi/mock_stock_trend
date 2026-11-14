from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from loguru import logger
from starlette.exceptions import HTTPException

from app.schemas.api_response import APIResponse, ValidationIssue


async def handle_http_error(request: Request, exc: HTTPException) -> JSONResponse:
    """将已知 HTTP 错误转换为统一格式。"""
    default_messages = {
        (404, "Not Found"): "资源不存在",
        (405, "Method Not Allowed"): "请求方法不允许",
    }
    message = exc.detail
    if isinstance(message, str):
        message = default_messages.get((exc.status_code, message), message)
    else:
        message = "请求失败"
    response = APIResponse(code=exc.status_code, message=message)
    return JSONResponse(
        status_code=exc.status_code,
        content=response.model_dump(exclude_none=True),
        headers=exc.headers,
    )


async def handle_validation_error(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """返回不包含请求原值的参数错误信息。"""
    issues = [
        ValidationIssue(
            field=".".join(str(part) for part in error["loc"]),
            message=error["msg"],
        )
        for error in exc.errors()
    ]
    response = APIResponse(code=422, message="请求参数不合法", errors=issues)
    return JSONResponse(status_code=422, content=response.model_dump(exclude_none=True))


async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    """记录意外异常，同时避免向客户端暴露内部细节。"""
    logger.error(
        "未处理的请求异常：{} {} ({})",
        request.method,
        request.url.path,
        type(exc).__name__,
    )
    response = APIResponse(code=500, message="服务器内部错误")
    return JSONResponse(status_code=500, content=response.model_dump(exclude_none=True))


def register_exception_handlers(app: FastAPI) -> None:
    """为应用注册统一错误处理器。"""
    app.add_exception_handler(HTTPException, handle_http_error)
    app.add_exception_handler(RequestValidationError, handle_validation_error)
    app.add_exception_handler(Exception, handle_unexpected_error)
