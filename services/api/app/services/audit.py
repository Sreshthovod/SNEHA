"""Audit logging.

Audit events record WHO did WHAT to WHICH record and the outcome. They never contain
passwords, tokens, pairing codes, conversation transcripts, memory content or notes.
Detail keys are allow-listed and values must be short scalars to enforce this.
"""

from typing import Any

from fastapi import Request
from sqlalchemy.orm import Session

from app.core.time import utc_now
from app.models.enums import AuditOutcome
from app.models.sync import AuditEvent

ALLOWED_DETAIL_KEYS = frozenset(
    {
        "reason",
        "role",
        "status",
        "consent_type",
        "relation_type",
        "kind",
        "purpose",
        "content_type",
        "size_bytes",
        "count",
        "applied",
        "duplicates",
        "conflicts",
        "rejected",
        "version",
        "expires_at",
        "can_manage",
    }
)
_MAX_VALUE_LENGTH = 100


def _clean(details: dict[str, Any] | None) -> dict[str, Any]:
    cleaned: dict[str, Any] = {}
    for key, value in (details or {}).items():
        if key not in ALLOWED_DETAIL_KEYS:
            raise ValueError(f"Audit detail key '{key}' is not allow-listed")
        if isinstance(value, str):
            value = value[:_MAX_VALUE_LENGTH]
        elif not isinstance(value, int | float | bool) and value is not None:
            value = str(value)[:_MAX_VALUE_LENGTH]
        cleaned[key] = value
    return cleaned


def record(
    db: Session,
    action: str,
    *,
    outcome: AuditOutcome = AuditOutcome.SUCCESS,
    actor_id: str | None = None,
    patient_id: str | None = None,
    target_type: str | None = None,
    target_id: str | None = None,
    request: Request | None = None,
    details: dict[str, Any] | None = None,
    commit: bool = False,
) -> None:
    """Add an audit event to the session. Successful actions are committed with the change
    they describe; pass commit=True for denials/failures that have no other change."""
    db.add(
        AuditEvent(
            occurred_at=utc_now(),
            actor_user_id=actor_id,
            action=action,
            outcome=outcome.value,
            patient_id=patient_id,
            target_type=target_type,
            target_id=target_id,
            request_id=getattr(request.state, "request_id", None) if request else None,
            details=_clean(details),
        )
    )
    if commit:
        db.commit()
