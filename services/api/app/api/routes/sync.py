"""Explicit device synchronisation (push outbox, pull change log). Patient devices only."""

from typing import Annotated

from fastapi import APIRouter, Query, Request
from sqlalchemy import select

from app.api.deps import DbSessionDep, PrincipalDep, require_roles
from app.core.errors import AppError
from app.models.enums import AuditOutcome, SyncMutationStatus, UserRole
from app.models.patients import PatientProfile
from app.schemas.common import ErrorResponse
from app.schemas.sync import SyncPullResponse, SyncPushRequest, SyncPushResponse
from app.services import audit, sync
from app.services.access import Permission, authorize
from app.services.activities import require_data_consent

router = APIRouter(prefix="/sync", tags=["sync"], dependencies=[require_roles(UserRole.PATIENT)])

_ERRORS = {
    401: {"model": ErrorResponse},
    403: {"model": ErrorResponse},
    409: {"model": ErrorResponse},
    422: {"model": ErrorResponse},
}


def _device_patient_id(db, principal) -> str:
    patient_id = db.scalar(select(PatientProfile.id).where(PatientProfile.user_id == principal.id))
    if patient_id is None:
        raise AppError(403, "not_paired", "This device is not paired with a patient profile.")
    return patient_id


@router.post("/push", response_model=SyncPushResponse, responses=_ERRORS)
def push(
    body: SyncPushRequest, principal: PrincipalDep, db: DbSessionDep, request: Request
) -> SyncPushResponse:
    """Apply a batch of device mutations. Each mutation gets its own outcome; the batch never
    fails as a whole because of one bad record. Safe to retry with the same mutation IDs."""
    patient_id = _device_patient_id(db, principal)
    authorize(db, principal.user, patient_id, Permission.RECORD_ACTIVITY, request=request)
    require_data_consent(db, patient_id)
    results = sync.push(
        db,
        patient_id=patient_id,
        user_id=principal.id,
        device_install_id=body.device_install_id,
        mutations=body.mutations,
    )
    counts = {s: sum(r.status is s for r in results) for s in SyncMutationStatus}
    audit.record(
        db,
        "sync.push",
        outcome=AuditOutcome.SUCCESS,
        actor_id=principal.id,
        patient_id=patient_id,
        request=request,
        details={
            "applied": counts[SyncMutationStatus.APPLIED],
            "duplicates": counts[SyncMutationStatus.DUPLICATE],
            "conflicts": counts[SyncMutationStatus.CONFLICT],
            "rejected": counts[SyncMutationStatus.REJECTED],
        },
        commit=True,
    )
    return SyncPushResponse(results=results)


@router.get("/pull", response_model=SyncPullResponse, responses=_ERRORS)
def pull(
    principal: PrincipalDep,
    db: DbSessionDep,
    request: Request,
    since: Annotated[
        int, Query(ge=0, description="Last `next_since` received; 0 for a full sync")
    ] = 0,
    limit: Annotated[int, Query(ge=1, le=sync.PULL_PAGE_SIZE)] = sync.PULL_PAGE_SIZE,
) -> SyncPullResponse:
    patient_id = _device_patient_id(db, principal)
    authorize(db, principal.user, patient_id, Permission.VIEW_MEMORIES, request=request)
    changes, next_since, has_more = sync.pull(db, patient_id=patient_id, since=since, limit=limit)
    return SyncPullResponse(changes=changes, next_since=next_since, has_more=has_more)
