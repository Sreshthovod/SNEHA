"""Activity catalog, sessions, results and performance history."""

from datetime import date, timedelta
from typing import Annotated

from fastapi import APIRouter, Query, Response, status
from sqlalchemy import select

from app.api.deps import DbSessionDep, PrincipalDep, patient_access
from app.core.errors import AppError
from app.core.time import utc_now
from app.models.activities import (
    ActivityDefinition,
    ActivityEvent,
    ActivityResult,
    ActivitySession,
)
from app.models.enums import RecordSource, UserRole
from app.schemas.activities import (
    ActivityDefinitionOut,
    PerformanceHistory,
    ResultCreate,
    ResultOut,
    SessionComplete,
    SessionCreate,
    SessionOut,
)
from app.schemas.common import ErrorResponse
from app.schemas.events import EventOut
from app.services import activities
from app.services.access import PatientAccess, Permission
from app.services.history import MAX_HISTORY_DAYS, performance_history

router = APIRouter(tags=["activities"])

_ERRORS = {
    401: {"model": ErrorResponse},
    403: {"model": ErrorResponse},
    404: {"model": ErrorResponse},
    409: {"model": ErrorResponse},
    422: {"model": ErrorResponse},
}


@router.get("/activities", response_model=list[ActivityDefinitionOut], responses=_ERRORS)
def list_activities(_: PrincipalDep, db: DbSessionDep) -> list[ActivityDefinition]:
    """The active activity catalog (not patient-specific)."""
    return list(
        db.scalars(
            select(ActivityDefinition)
            .where(ActivityDefinition.is_active.is_(True))
            .order_by(ActivityDefinition.slug)
        )
    )


@router.get("/patients/{patient_id}/sessions", response_model=list[SessionOut], responses=_ERRORS)
def list_sessions(
    db: DbSessionDep,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    access: PatientAccess = patient_access(Permission.VIEW_HISTORY),
) -> list[ActivitySession]:
    return list(
        db.scalars(
            select(ActivitySession)
            .where(ActivitySession.patient_id == access.patient.id)
            .order_by(ActivitySession.started_at.desc())
            .limit(limit)
        )
    )


@router.post(
    "/patients/{patient_id}/sessions",
    response_model=SessionOut,
    status_code=status.HTTP_201_CREATED,
    responses={**_ERRORS, 200: {"model": SessionOut, "description": "Session already existed"}},
)
def create_session(
    body: SessionCreate,
    principal: PrincipalDep,
    db: DbSessionDep,
    response: Response,
    access: PatientAccess = patient_access(Permission.RECORD_ACTIVITY),
) -> ActivitySession:
    """Start a session. Idempotent when a client `id` is supplied."""
    activities.require_data_consent(db, access.patient.id)
    if body.started_at > utc_now() + timedelta(minutes=5):
        raise AppError(422, "validation_error", "started_at cannot be in the future.")
    session, created = activities.create_session(
        db,
        patient_id=access.patient.id,
        session_id=body.id,
        started_at=body.started_at,
        source=RecordSource.DEVICE
        if principal.role is UserRole.PATIENT
        else RecordSource.DASHBOARD,
        device_install_id=body.device_install_id,
        created_by_id=principal.id,
    )
    db.commit()
    if not created:
        response.status_code = status.HTTP_200_OK
    return session


@router.post(
    "/patients/{patient_id}/sessions/{session_id}/complete",
    response_model=SessionOut,
    responses=_ERRORS,
)
def complete_session(
    session_id: str,
    body: SessionComplete,
    db: DbSessionDep,
    access: PatientAccess = patient_access(Permission.RECORD_ACTIVITY),
) -> ActivitySession:
    session = activities.get_session_for_patient(db, access.patient.id, session_id)
    activities.finish_session(session, ended_at=body.ended_at, end_reason=body.end_reason)
    db.commit()
    return session


@router.get(
    "/patients/{patient_id}/sessions/{session_id}/results",
    response_model=list[ResultOut],
    responses=_ERRORS,
)
def list_results(
    session_id: str,
    db: DbSessionDep,
    access: PatientAccess = patient_access(Permission.VIEW_HISTORY),
) -> list[ActivityResult]:
    session = activities.get_session_for_patient(db, access.patient.id, session_id)
    return list(
        db.scalars(
            select(ActivityResult)
            .where(ActivityResult.session_id == session.id)
            .order_by(ActivityResult.started_at)
        )
    )


@router.get(
    "/patients/{patient_id}/sessions/{session_id}/events",
    response_model=list[EventOut],
    responses=_ERRORS,
)
def list_events(
    session_id: str,
    db: DbSessionDep,
    access: PatientAccess = patient_access(Permission.VIEW_HISTORY),
) -> list[ActivityEvent]:
    """What happened inside the session, in order: answers, hints, pauses, tiredness
    reports, stop requests and every in-session adaptation decision with its reasons."""
    session = activities.get_session_for_patient(db, access.patient.id, session_id)
    return list(
        db.scalars(
            select(ActivityEvent)
            .where(ActivityEvent.session_id == session.id)
            .order_by(ActivityEvent.seq, ActivityEvent.occurred_at)
        )
    )


@router.post(
    "/patients/{patient_id}/sessions/{session_id}/results",
    response_model=ResultOut,
    status_code=status.HTTP_201_CREATED,
    responses={**_ERRORS, 200: {"model": ResultOut, "description": "Duplicate submission"}},
)
def submit_result(
    session_id: str,
    body: ResultCreate,
    db: DbSessionDep,
    response: Response,
    access: PatientAccess = patient_access(Permission.RECORD_ACTIVITY),
) -> ActivityResult:
    """Submit one activity result. Safe to retry: an identical resubmission returns 200."""
    activities.require_data_consent(db, access.patient.id)
    session = activities.get_session_for_patient(db, access.patient.id, session_id)
    result, created = activities.submit_result(db, session, body)
    db.commit()
    if not created:
        response.status_code = status.HTTP_200_OK
    return result


@router.get("/patients/{patient_id}/history", response_model=PerformanceHistory, responses=_ERRORS)
def get_history(
    db: DbSessionDep,
    from_date: Annotated[date, Query(alias="from")],
    to_date: Annotated[date, Query(alias="to")],
    access: PatientAccess = patient_access(Permission.VIEW_HISTORY),
) -> PerformanceHistory:
    """Per-day, per-activity descriptive statistics in the patient's timezone (inclusive range)."""
    if to_date < from_date:
        raise AppError(422, "validation_error", "'to' must not be before 'from'.")
    if (to_date - from_date).days + 1 > MAX_HISTORY_DAYS:
        raise AppError(422, "validation_error", f"Range is limited to {MAX_HISTORY_DAYS} days.")
    return performance_history(db, access.patient, from_date, to_date)
