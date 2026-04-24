from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import get_request_id
from app.schemas.common import ErrorDetail, ErrorResponse


logger = logging.getLogger(__name__)


class AppError(Exception):
    def __init__(
        self,
        message: str,
        *,
        code: str = "application_error",
        status_code: int = status.HTTP_400_BAD_REQUEST,
        details: Any | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details
        self.headers = dict(headers or {})


def _error_response(
    *,
    message: str,
    code: str,
    status_code: int,
    details: Any | None = None,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    payload = ErrorResponse(
        error=ErrorDetail(
            code=code,
            message=message,
            details=details,
            request_id=get_request_id(),
        )
    )
    return JSONResponse(
        status_code=status_code,
        content=payload.model_dump(mode="json"),
        headers=dict(headers or {}),
    )


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(_: Request, exc: AppError) -> JSONResponse:
        logger.warning(
            "Application error raised",
            extra={"event": "application_error", "code": exc.code, "details": exc.details},
        )
        return _error_response(
            message=exc.message,
            code=exc.code,
            status_code=exc.status_code,
            details=exc.details,
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        logger.warning(
            "Request validation failed",
            extra={"event": "request_validation_error", "errors": exc.errors()},
        )
        return _error_response(
            message="Request validation failed.",
            code="request_validation_error",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            details=exc.errors(),
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        logger.warning(
            "HTTP error raised",
            extra={"event": "http_error", "status_code": exc.status_code, "detail": exc.detail},
        )
        message = exc.detail if isinstance(exc.detail, str) else "HTTP error raised."
        return _error_response(
            message=message,
            code="http_error",
            status_code=exc.status_code,
            details=exc.detail if not isinstance(exc.detail, str) else None,
        )

    @app.exception_handler(SQLAlchemyError)
    async def handle_database_error(_: Request, exc: SQLAlchemyError) -> JSONResponse:
        logger.exception(
            "Database error raised",
            extra={"event": "database_error", "exception_type": exc.__class__.__name__},
        )
        return _error_response(
            message="A database error occurred.",
            code="database_error",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(_: Request, exc: Exception) -> JSONResponse:
        logger.exception(
            "Unhandled exception raised",
            extra={"event": "unhandled_exception", "exception_type": exc.__class__.__name__},
        )
        return _error_response(
            message="An unexpected internal error occurred.",
            code="internal_server_error",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
