"""Unified error codes, ApiError exception and FastAPI exception handlers.

Every error is returned as: {"error": {"code", "message", "status"}} per
docs/02-后端API设计与实现.md §6.
"""

import logging

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


class ErrorCode:
    VALIDATION_ERROR = "VALIDATION_ERROR"
    PAIRING_CODE_INVALID = "PAIRING_CODE_INVALID"
    PAIRING_CODE_CONFLICT = "PAIRING_CODE_CONFLICT"
    TOKEN_INVALID = "TOKEN_INVALID"
    TOKEN_MISSING = "TOKEN_MISSING"
    CLASS_FORBIDDEN = "CLASS_FORBIDDEN"
    CLASS_NOT_FOUND = "CLASS_NOT_FOUND"
    NOT_FOUND = "NOT_FOUND"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    MESSAGE_RECALL_EXPIRED = "MESSAGE_RECALL_EXPIRED"
    MESSAGE_RECALL_NOT_FOUND = "MESSAGE_RECALL_NOT_FOUND"
    IMAGE_TOO_LARGE = "IMAGE_TOO_LARGE"
    IMAGE_FORMAT_INVALID = "IMAGE_FORMAT_INVALID"
    SCHEDULE_INVALID = "SCHEDULE_INVALID"
    BATCH_LIMIT_EXCEEDED = "BATCH_LIMIT_EXCEEDED"


class ApiError(HTTPException):
    """HTTP exception carrying a stable machine-readable error code."""

    def __init__(self, status_code: int, code: str, message: str):
        super().__init__(status_code=status_code, detail=message)
        self.code = code
        self.message = message


def _body(code: str, message: str, status_code: int, **extra) -> JSONResponse:
    payload = {"error": {"code": code, "message": message, "status": status_code}}
    if extra:
        payload["error"].update(extra)
    return JSONResponse(status_code=status_code, content=payload)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api_error_handler(request: Request, exc: ApiError):
        # Log business errors at WARNING level (not full stack trace)
        logger.warning(
            "API_ERROR | %s %s -> %d | code=%s | %s",
            request.method,
            request.url.path,
            exc.status_code,
            exc.code,
            exc.message,
        )
        return _body(exc.code, exc.message, exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def _validation_handler(request: Request, exc: RequestValidationError):
        logger.warning(
            "VALIDATION_ERROR | %s %s -> 400 | %s",
            request.method,
            request.url.path,
            str(exc.errors)[:200],  # truncate long error details
        )
        return _body(
            ErrorCode.VALIDATION_ERROR,
            "请求体校验失败",
            status.HTTP_400_BAD_REQUEST,
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_handler(request: Request, exc: StarletteHTTPException):
        code = ErrorCode.NOT_FOUND if exc.status_code == 404 else ErrorCode.INTERNAL_ERROR
        logger.warning(
            "HTTP_ERROR | %s %s -> %d | %s",
            request.method,
            request.url.path,
            exc.status_code,
            str(exc.detail)[:200],
        )
        return _body(code, str(exc.detail), exc.status_code)

    @app.exception_handler(Exception)
    async def _unhandled_handler(request: Request, exc: Exception):
        # Log unhandled exceptions at ERROR level with full stack trace
        logger.error(
            "UNHANDLED_ERROR | %s %s -> 500 | %s",
            request.method,
            request.url.path,
            str(exc),
            exc_info=exc,
        )
        # Do not leak stack traces / internals to clients.
        return _body(
            ErrorCode.INTERNAL_ERROR,
            "服务端内部错误",
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
