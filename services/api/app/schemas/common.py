"""Schemas shared across endpoints. These are part of the public API contract."""

from typing import Any

from pydantic import BaseModel, Field


class ErrorBody(BaseModel):
    code: str = Field(description="Stable machine-readable error code, e.g. 'validation_error'.")
    message: str = Field(description="Human-readable explanation suitable for logs and UIs.")
    details: list[dict[str, Any]] | None = Field(
        default=None, description="Optional structured details, e.g. per-field validation errors."
    )
    request_id: str | None = Field(default=None, description="Echo of the X-Request-ID header.")


class ErrorResponse(BaseModel):
    error: ErrorBody
