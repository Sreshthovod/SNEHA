"""Activity sessions and results, shared by the REST endpoints and sync."""

from datetime import datetime

from sqlalchemy.orm import Session

from app.core.errors import AppError, conflict, not_found
from app.models.activities import (
    ActivityDefinition,
    ActivityRecommendation,
    ActivityResult,
    ActivitySession,
)
from app.models.enums import (
    ConsentType,
    RecordSource,
    SessionEndReason,
    SessionStatus,
)
from app.schemas.activities import ResultCreate
from app.services.access import has_consent

_RESULT_FIELDS = (
    "activity_id",
    "difficulty_level",
    "started_at",
    "completed_at",
    "score",
    "correct_count",
    "attempt_count",
    "hint_count",
    "duration_ms",
    "abandoned",
    "metrics",
    "engagement",
    "fatigue_reported",
    "recommendation_id",
)


def require_data_consent(db: Session, patient_id: str) -> None:
    if not has_consent(db, patient_id, ConsentType.DATA_PROCESSING):
        raise AppError(
            409,
            "consent_required",
            "Data-processing consent must be recorded for this patient before data is stored.",
        )


def get_session_for_patient(db: Session, patient_id: str, session_id: str) -> ActivitySession:
    session = db.get(ActivitySession, session_id)
    if session is None or session.patient_id != patient_id:
        raise not_found("Session")
    return session


def create_session(
    db: Session,
    *,
    patient_id: str,
    session_id: str | None,
    started_at: datetime,
    source: RecordSource,
    device_install_id: str | None,
    created_by_id: str,
) -> tuple[ActivitySession, bool]:
    """Returns (session, created). Re-creating an existing ID for the same patient is a no-op."""
    if session_id is not None:
        existing = db.get(ActivitySession, session_id)
        if existing is not None:
            if existing.patient_id != patient_id:
                raise conflict("id_conflict", "This session ID is already in use.")
            return existing, False
    session = ActivitySession(
        patient_id=patient_id,
        status=SessionStatus.IN_PROGRESS,
        source=source,
        device_install_id=device_install_id,
        started_at=started_at,
        created_by_id=created_by_id,
    )
    if session_id is not None:
        session.id = session_id
    db.add(session)
    db.flush()
    return session, True


def finish_session(
    session: ActivitySession, *, ended_at: datetime, end_reason: SessionEndReason
) -> bool:
    """Returns True if the session changed. Finishing twice with the same data is idempotent."""
    status = (
        SessionStatus.COMPLETED
        if end_reason is SessionEndReason.COMPLETED
        else SessionStatus.ABANDONED
    )
    if session.status is not SessionStatus.IN_PROGRESS:
        if session.ended_at == ended_at and session.end_reason is end_reason:
            return False
        raise conflict("session_already_ended", "This session has already ended.")
    if ended_at < session.started_at:
        raise AppError(422, "validation_error", "ended_at must not be before the session start.")
    session.status = status
    session.end_reason = end_reason
    session.ended_at = ended_at
    return True


def _same_result(existing: ActivityResult, payload: ResultCreate) -> bool:
    return all(getattr(existing, f) == getattr(payload, f) for f in _RESULT_FIELDS)


def submit_result(
    db: Session, session: ActivitySession, payload: ResultCreate
) -> tuple[ActivityResult, bool]:
    """Idempotent insert. Returns (result, created).

    Same ID + identical payload -> existing result (duplicate delivery).
    Same ID + different payload -> 409 (results are immutable).
    """
    existing = db.get(ActivityResult, payload.id)
    if existing is not None:
        if existing.session_id == session.id and _same_result(existing, payload):
            return existing, False
        raise conflict("result_conflict", "A different result with this ID already exists.")

    activity = db.get(ActivityDefinition, payload.activity_id)
    if activity is None or not activity.is_active:
        raise AppError(422, "unknown_activity", "activity_id does not match an active activity.")
    if not activity.min_difficulty <= payload.difficulty_level <= activity.max_difficulty:
        raise AppError(
            422,
            "invalid_difficulty",
            f"difficulty_level must be between {activity.min_difficulty} and "
            f"{activity.max_difficulty} for this activity.",
        )
    if payload.started_at < session.started_at:
        raise AppError(422, "validation_error", "Result cannot start before its session.")
    if payload.recommendation_id is not None:
        rec = db.get(ActivityRecommendation, payload.recommendation_id)
        if rec is None or rec.patient_id != session.patient_id:
            raise AppError(422, "unknown_recommendation", "recommendation_id is not valid here.")

    result = ActivityResult(
        id=payload.id,
        session_id=session.id,
        patient_id=session.patient_id,
        activity_version=activity.version,
        **{f: getattr(payload, f) for f in _RESULT_FIELDS},
    )
    db.add(result)
    db.flush()
    return result, True
