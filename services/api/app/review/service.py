"""Turn automated review prompts into review items, and record caregivers' decisions.

A review prompt (analytics/compute.py) is an automated, descriptive interpretation of
stored activity data. It becomes a review item for one period so that a caregiver can
look at the evidence and either confirm it (worth discussing with a clinician) or
dismiss it (it has an everyday explanation), always with a reason. Clinicians only ever
see confirmed items. Nothing here diagnoses anything.
"""

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analytics.service import summarise
from app.core.errors import AppError, conflict
from app.core.time import utc_now
from app.models.care import ReviewItem
from app.models.enums import ReviewItemStatus
from app.models.patients import PatientProfile
from app.services import audit


def items_for_period(
    db: Session, patient_id: str, period_start: date, period_end: date
) -> list[ReviewItem]:
    return list(
        db.scalars(
            select(ReviewItem)
            .where(
                ReviewItem.patient_id == patient_id,
                ReviewItem.period_start == period_start,
                ReviewItem.period_end == period_end,
            )
            .order_by(ReviewItem.created_at, ReviewItem.rule_id)
        )
    )


def scan(
    db: Session,
    patient: PatientProfile,
    period_start: date,
    period_end: date,
    *,
    actor_id: str | None = None,
) -> list[ReviewItem]:
    """Create an item for every prompt the rules raise for this period.

    Re-scanning refreshes the evidence of items still awaiting review. An item a caregiver
    has already decided is never changed, so the decision always matches what they saw.
    An awaiting item whose prompt no longer appears (for example after late data synced)
    is kept, and its evidence is left as it was when it was raised.
    """
    summary = summarise(db, patient, period_start, period_end)
    existing = {i.rule_id: i for i in items_for_period(db, patient.id, period_start, period_end)}
    created = 0
    for flag in summary.review_flags:
        item = existing.get(flag.rule_id)
        if item is None:
            item = ReviewItem(
                patient_id=patient.id,
                rule_id=flag.rule_id,
                period_start=period_start,
                period_end=period_end,
                status=ReviewItemStatus.AWAITING_REVIEW,
            )
            db.add(item)
            existing[flag.rule_id] = item
            created += 1
        elif item.status is not ReviewItemStatus.AWAITING_REVIEW:
            continue
        item.kind = flag.kind
        item.title = flag.title
        item.explanation = flag.explanation
        item.numbers = dict(flag.numbers)
        item.observation_ids = list(flag.observation_ids)
        item.method_version = summary.method_version
        item.config_version = summary.config_version
    db.flush()
    if created:
        audit.record(
            db,
            "review_item.scan",
            actor_id=actor_id,
            patient_id=patient.id,
            target_type="patient",
            target_id=patient.id,
            details={"count": created},
        )
    return items_for_period(db, patient.id, period_start, period_end)


def decide(
    db: Session,
    item: ReviewItem,
    decision: ReviewItemStatus,
    reason: str,
    *,
    actor_id: str,
) -> ReviewItem:
    if decision is ReviewItemStatus.AWAITING_REVIEW:
        raise AppError(422, "validation_error", "Choose confirmed or dismissed.")
    if item.status is not ReviewItemStatus.AWAITING_REVIEW:
        raise conflict(
            "already_decided",
            f"This item was already {item.status.value}. Decisions are kept as they were made.",
        )
    item.status = decision
    item.decided_by_id = actor_id
    item.decided_at = utc_now()
    item.decision_reason = reason
    audit.record(
        db,
        "review_item.decide",
        actor_id=actor_id,
        patient_id=item.patient_id,
        target_type="review_item",
        target_id=item.id,
        details={"status": decision.value},
    )
    return item
