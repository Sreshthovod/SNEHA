from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: Literal["ok"]
    service: str
    version: str
    environment: str
    server_time: datetime = Field(description="Current server time, timezone-aware (UTC).")


class ReadinessCheck(BaseModel):
    name: str
    status: Literal["ok", "error"]
    detail: str | None = None


class ReadinessResponse(BaseModel):
    status: Literal["ready", "not_ready"]
    checks: list[ReadinessCheck]
    server_time: datetime
