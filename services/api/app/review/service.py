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
from app.models.activities import ActivityDefinition, ActivityResult
from app.models.care import ReviewItem
from app.models.enums import ReviewItemStatus
from app.models.patients import PatientProfile
from app.services import audit
from app.services.history import day_bounds


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
        item.evidence = evidence_for(db, patient, period_start, period_end, flag, summary)
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


MAX_EVIDENCE_RESULTS = 100


def evidence_for(db: Session, patient, period_start, period_end, flag, summary) -> dict:
    """The stored records a prompt is based on. Change prompts use only the activities
    compared with the person's usual pattern (like with like)."""
    lower, upper = day_bounds(patient, period_start, period_end)
    query = (
        select(ActivityResult.id, ActivityDefinition.title)
        .join(ActivityDefinition, ActivityDefinition.id == ActivityResult.activity_id)
        .where(
            ActivityResult.patient_id == patient.id,
            ActivityResult.completed_at >= lower,
            ActivityResult.completed_at < upper,
        )
        .order_by(ActivityResult.completed_at)
    )
    compared = summary.baseline.activities_compared
    if flag.kind == "change" and compared:
        query = query.where(ActivityDefinition.title.in_(compared))
    rows = db.execute(query).all()
    limitations = [f"{r.rule_id}: {r.reason}" for r in summary.rules_not_evaluated]
    if summary.sync and summary.sync.may_be_incomplete and summary.sync.reason:
        limitations.append(f"Data may be incomplete: {summary.sync.reason}.")
    return {
        "result_ids": [r[0] for r in rows[:MAX_EVIDENCE_RESULTS]],
        "results_considered": len(rows),
        "activities": sorted({r[1] for r in rows}),
        "missing_days": [str(d) for d in summary.completeness.missing_days],
        "limitations": limitations,
    }


def add_context(db: Session, item: ReviewItem, note: str, *, actor_id: str) -> ReviewItem:
    """Append a caregiver's context; the decision and the evidence are left unchanged."""
    notes = list(item.context_notes or [])
    notes.append({"by": actor_id, "at": utc_now().isoformat(), "note": note})
    item.context_notes = notes
    audit.record(
        db,
        "review_item.context",
        actor_id=actor_id,
        patient_id=item.patient_id,
        target_type="review_item",
        target_id=item.id,
        details={"count": len(notes)},
    )
    return item


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
