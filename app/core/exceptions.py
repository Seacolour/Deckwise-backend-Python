"""Application errors rendered in the Java Backend's response envelope."""

import logging

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.error_codes import ErrorCode
from app.core.responses import BaseResponse

logger = logging.getLogger("uvicorn.error")


class BusinessError(Exception):
    def __init__(self, status: int, code: int | ErrorCode, message: str) -> None:
        self.status = status
        self.code = code
        self.message = message
        super().__init__(message)


def handle_business_error(_request: Request, error: BusinessError) -> JSONResponse:
    return JSONResponse(
        status_code=error.status,
        content=BaseResponse[object](code=error.code, data=None, message=error.message).model_dump(),
    )


def handle_validation_error(_request: Request, error: RequestValidationError) -> JSONResponse:
    fields = sorted({".".join(str(part) for part in item["loc"]) for item in error.errors()})
    location = ", ".join(fields[:3])
    message = "请求参数校验失败" + (f": {location}" if location else "")
    return JSONResponse(
        status_code=422,
        content=BaseResponse[object](
            code=ErrorCode.PARAM_VALIDATION_FAILED,
            data=None,
            message=message,
        ).model_dump(),
    )


def handle_http_error(_request: Request, error: StarletteHTTPException) -> JSONResponse:
    if error.status_code == 404:
        code, message = ErrorCode.NOT_FOUND, "请求数据不存在"
    elif error.status_code == 401:
        code, message = ErrorCode.TOKEN_INVALID, "登录状态已失效"
    else:
        code, message = error.status_code, str(error.detail)
    return JSONResponse(
        status_code=error.status_code,
        content=BaseResponse[object](code=code, data=None, message=message).model_dump(),
        headers=error.headers,
    )


def handle_unexpected_error(request: Request, error: Exception) -> JSONResponse:
    request_id = getattr(request.state, "request_id", "-")
    logger.error("request failed id=%s exception=%s", request_id, type(error).__name__)
    return JSONResponse(
        status_code=500,
        content=BaseResponse[object](
            code=ErrorCode.SYSTEM_ERROR, data=None, message="系统内部异常"
        ).model_dump(),
        headers={"X-Request-ID": request_id},
    )
