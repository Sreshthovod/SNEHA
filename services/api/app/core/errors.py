"""Uniform error envelope.

Every error response has the shape `{"error": {code, message, details?, request_id?}}`.
"""

import logging
from http import HTTPStatus
from typing import Any

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, OperationalError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.schemas.common import ErrorBody, ErrorResponse

logger = logging.getLogger(__name__)


class AppError(Exception):
    """A domain error with a stable code, safe to show to the client."""

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: list[dict[str, Any]] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details
        self.headers = headers


def not_found(what: str = "Resource") -> AppError:
    return AppError(404, "not_found", f"{what} not found.")


def forbidden(message: str = "You do not have permission to do this.") -> AppError:
    return AppError(403, "forbidden", message)


def conflict(code: str, message: str) -> AppError:
    return AppError(409, code, message)


def _error_response(
    request: Request,
    status_code: int,
    code: str,
    message: str,
    details: list[dict[str, Any]] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    body = ErrorResponse(
        error=ErrorBody(
            code=code,
            message=message,
            details=details,
            request_id=getattr(request.state, "request_id", None),
        )
    )
    return JSONResponse(
        status_code=status_code,
        content=jsonable_encoder(body, exclude_none=True),
        headers=headers,
    )


def _code_for_status(status_code: int) -> str:
    try:
        return HTTPStatus(status_code).phrase.lower().replace(" ", "_").replace("-", "_")
    except ValueError:
        return "http_error"


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(StarletteHTTPException)
    async def _http_exception(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        message = exc.detail if isinstance(exc.detail, str) else _code_for_status(exc.status_code)
        return _error_response(
            request,
            exc.status_code,
            _code_for_status(exc.status_code),
            message,
            headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_exception(request: Request, exc: RequestValidationError) -> JSONResponse:
        details = [
            {
                "loc": list(err.get("loc", ())),
                "msg": err.get("msg", ""),
                "type": err.get("type", ""),
            }
            for err in exc.errors()
        ]
        return _error_response(
            request, 422, "validation_error", "The request contains invalid fields.", details
        )

    @app.exception_handler(AppError)
    async def _app_error(request: Request, exc: AppError) -> JSONResponse:
        return _error_response(
            request, exc.status_code, exc.code, exc.message, exc.details, exc.headers
        )

    @app.exception_handler(IntegrityError)
    async def _integrity_error(request: Request, exc: IntegrityError) -> JSONResponse:
        # Constraint details can leak schema/data; log them, return a generic message.
        logger.warning("Integrity error: %s", exc.orig)
        return _error_response(
            request, 409, "constraint_violation", "The request conflicts with existing data."
        )

    @app.exception_handler(OperationalError)
    async def _database_unavailable(request: Request, exc: OperationalError) -> JSONResponse:
        logger.error("Database unavailable: %s", exc.orig)
        return _error_response(
            request,
            503,
            "database_unavailable",
            "The service is temporarily unavailable. Please try again shortly.",
            headers={"Retry-After": "5"},
        )

    @app.exception_handler(Exception)
    async def _unhandled_exception(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error", exc_info=exc)
        return _error_response(
            request, 500, "internal_error", "An unexpected error occurred. Please try again."
        )
