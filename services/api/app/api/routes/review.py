"""Review items: automated prompts → caregiver decision → (only if confirmed) clinician."""

from typing import Annotated

from fastapi import APIRouter, Query
from sqlalchemy import select

from app.api.deps import DbSessionDep, PrincipalDep, patient_access
from app.core.errors import not_found
from app.models.care import ReviewItem
from app.models.enums import ReviewItemStatus
from app.review import service
from app.schemas.common import ErrorResponse
from app.schemas.review import ReviewDecision, ReviewItemOut, ReviewScanRequest
from app.services.access import PatientAccess, Permission

router = APIRouter(prefix="/patients/{patient_id}/review-items", tags=["review"])

_ERRORS = {
    401: {"model": ErrorResponse},
    403: {"model": ErrorResponse},
    404: {"model": ErrorResponse},
    409: {"model": ErrorResponse},
    422: {"model": ErrorResponse},
}


@router.get("", response_model=list[ReviewItemOut], responses=_ERRORS)
def list_review_items(
    db: DbSessionDep,
    status_filter: Annotated[ReviewItemStatus | None, Query(alias="status")] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    access: PatientAccess = patient_access(Permission.VIEW_REVIEW_ITEMS),
) -> list[ReviewItem]:
    """Caregivers see every item. Clinicians see only items a caregiver confirmed."""
    query = select(ReviewItem).where(ReviewItem.patient_id == access.patient.id)
    if access.is_clinician:
        query = query.where(ReviewItem.status == ReviewItemStatus.CONFIRMED)
    if status_filter is not None:
        query = query.where(ReviewItem.status == status_filter)
    return list(
        db.scalars(query.order_by(ReviewItem.period_end.desc(), ReviewItem.created_at).limit(limit))
    )


@router.post("/scan", response_model=list[ReviewItemOut], responses=_ERRORS)
def scan_review_items(
    body: ReviewScanRequest,
    principal: PrincipalDep,
    db: DbSessionDep,
    access: PatientAccess = patient_access(Permission.SCAN_REVIEW_ITEMS),
) -> list[ReviewItem]:
    """Run the review rules over stored data for the period and keep what they raise as
    items awaiting a caregiver's review. Safe to repeat."""
    items = service.scan(
        db, access.patient, body.period_start, body.period_end, actor_id=principal.id
    )
    db.commit()
    return items


@router.post("/{item_id}/decision", response_model=ReviewItemOut, responses=_ERRORS)
def decide_review_item(
    item_id: str,
    body: ReviewDecision,
    principal: PrincipalDep,
    db: DbSessionDep,
    access: PatientAccess = patient_access(Permission.DECIDE_REVIEW_ITEM),
) -> ReviewItem:
    """Confirm (worth discussing with a clinician) or dismiss (explained), with a reason.
    A decision is final; it is recorded with who made it and when."""
    item = db.get(ReviewItem, item_id)
    if item is None or item.patient_id != access.patient.id:
        raise not_found("Review item")
    service.decide(db, item, ReviewItemStatus(body.decision), body.reason, actor_id=principal.id)
    db.commit()
    return item
