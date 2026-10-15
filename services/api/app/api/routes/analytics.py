"""Longitudinal analytics (Stage 6). Descriptive only; review flags are prompts, not findings."""

from datetime import UTC, date, datetime, timedelta
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Query

from app.analytics.schemas import AnalyticsSummary, ReviewFlagsResponse
from app.analytics.service import MAX_ANALYTICS_DAYS, summarise
from app.api.deps import DbSessionDep, patient_access
from app.core.errors import AppError
from app.models.patients import PatientProfile
from app.schemas.common import ErrorResponse
from app.services.access import PatientAccess, Permission

router = APIRouter(prefix="/patients/{patient_id}/analytics", tags=["analytics"])

_ERRORS = {
    401: {"model": ErrorResponse},
    403: {"model": ErrorResponse},
    404: {"model": ErrorResponse},
    422: {"model": ErrorResponse},
}
DEFAULT_DAYS = 9


def _range(
    patient: PatientProfile, from_date: date | None, to_date: date | None
) -> tuple[date, date]:
    today = datetime.now(UTC).astimezone(ZoneInfo(patient.timezone)).date()
    to_date = to_date or today
    from_date = from_date or to_date - timedelta(days=DEFAULT_DAYS - 1)
    if to_date < from_date:
        raise AppError(422, "validation_error", "'to' must not be before 'from'.")
    if (to_date - from_date).days + 1 > MAX_ANALYTICS_DAYS:
        raise AppError(422, "validation_error", f"Range is limited to {MAX_ANALYTICS_DAYS} days.")
    return from_date, to_date


@router.get("", response_model=AnalyticsSummary, responses=_ERRORS)
def get_analytics(
    db: DbSessionDep,
    from_date: Annotated[date | None, Query(alias="from")] = None,
    to_date: Annotated[date | None, Query(alias="to")] = None,
    access: PatientAccess = patient_access(Permission.VIEW_HISTORY),
) -> AnalyticsSummary:
    """Metrics for an inclusive date range in the patient's timezone (default: last 9 days),
    with own-baseline comparison where enough data exists and conservative review flags."""
    start, end = _range(access.patient, from_date, to_date)
    return summarise(db, access.patient, start, end)


@router.get("/review-flags", response_model=ReviewFlagsResponse, responses=_ERRORS)
def get_review_flags(
    db: DbSessionDep,
    from_date: Annotated[date | None, Query(alias="from")] = None,
    to_date: Annotated[date | None, Query(alias="to")] = None,
    access: PatientAccess = patient_access(Permission.VIEW_HISTORY),
) -> ReviewFlagsResponse:
    """Only the review prompts (and the rules that could not be checked, with reasons)."""
    start, end = _range(access.patient, from_date, to_date)
    summary = summarise(db, access.patient, start, end)
    return ReviewFlagsResponse(
        patient_id=summary.patient_id,
        from_date=start,
        to_date=end,
        method_version=summary.method_version,
        config_version=summary.config_version,
        review_flags=summary.review_flags,
        rules_not_evaluated=summary.rules_not_evaluated,
        disclaimer=summary.disclaimer,
    )
