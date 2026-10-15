"""Liveness and readiness endpoints."""

import logging

from fastapi import APIRouter, Response, status
from sqlalchemy import text

from app.api.deps import EngineDep, SettingsDep
from app.core.time import utc_now
from app.core.version import service_version
from app.db.migrations import migration_status
from app.schemas.health import HealthResponse, ReadinessCheck, ReadinessResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/health", tags=["health"])


@router.get("", response_model=HealthResponse, summary="Liveness check")
def health(settings: SettingsDep) -> HealthResponse:
    """Returns 200 whenever the process is serving requests. Does not touch the database."""
    return HealthResponse(
        status="ok",
        service=settings.app_name,
        version=service_version(),
        environment=settings.environment.value,
        server_time=utc_now(),
    )


@router.get(
    "/ready",
    response_model=ReadinessResponse,
    summary="Readiness check",
    responses={503: {"model": ReadinessResponse, "description": "A dependency is unavailable"}},
)
def readiness(response: Response, engine: EngineDep) -> ReadinessResponse:
    """Checks database connectivity and that migrations are at the latest revision."""
    checks: list[ReadinessCheck] = []

    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        checks.append(ReadinessCheck(name="database", status="ok"))
    except Exception:
        logger.exception("Readiness: database check failed")
        checks.append(
            ReadinessCheck(name="database", status="error", detail="Database is unreachable")
        )

    if checks[-1].status == "ok":
        try:
            current, heads = migration_status(engine)
            if current == heads:
                checks.append(ReadinessCheck(name="migrations", status="ok"))
            else:
                checks.append(
                    ReadinessCheck(
                        name="migrations",
                        status="error",
                        detail="Database schema is not at the latest revision; "
                        "run `uv run alembic upgrade head`",
                    )
                )
        except Exception:
            logger.exception("Readiness: migration check failed")
            checks.append(
                ReadinessCheck(
                    name="migrations", status="error", detail="Could not read migration state"
                )
            )

    ready = all(check.status == "ok" for check in checks)
    if not ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return ReadinessResponse(
        status="ready" if ready else "not_ready", checks=checks, server_time=utc_now()
    )
