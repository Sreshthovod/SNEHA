"""Descriptive performance history.

This summarises what happened; it does not assess or diagnose.
"""

from collections import defaultdict
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.activities import ActivityDefinition, ActivityResult, ActivitySession
from app.models.enums import SessionEndReason, SessionStatus
from app.models.patients import PatientProfile
from app.schemas.activities import HistoryDay, PerformanceHistory

DISCLAIMER = (
    "Activity statistics describe game performance only. They are affected by mood, "
    "sleep, eyesight, familiarity and many other factors, and are not a medical assessment."
)
MAX_HISTORY_DAYS = 366


def day_bounds(patient: PatientProfile, start: date, end: date) -> tuple[datetime, datetime]:
    """[start 00:00, end+1 00:00) in the patient's timezone, returned in UTC."""
    tz = ZoneInfo(patient.timezone)
    return (
        datetime.combine(start, time.min, tzinfo=tz).astimezone(UTC),
        datetime.combine(end + timedelta(days=1), time.min, tzinfo=tz).astimezone(UTC),
    )


def performance_history(
    db: Session, patient: PatientProfile, from_date: date, to_date: date
) -> PerformanceHistory:
    tz = ZoneInfo(patient.timezone)
    lower, upper = day_bounds(patient, from_date, to_date)

    rows = db.execute(
        select(ActivityResult, ActivityDefinition.slug)
        .join(ActivityDefinition, ActivityDefinition.id == ActivityResult.activity_id)
        .where(
            ActivityResult.patient_id == patient.id,
            ActivityResult.completed_at >= lower,
            ActivityResult.completed_at < upper,
        )
        .order_by(ActivityResult.completed_at)
    ).all()

    groups: dict[tuple[date, str], list[ActivityResult]] = defaultdict(list)
    slugs: dict[str, str] = {}
    for result, slug in rows:
        groups[(result.completed_at.astimezone(tz).date(), result.activity_id)].append(result)
        slugs[result.activity_id] = slug

    days = []
    for (day, activity_id), results in sorted(groups.items()):
        scores = [r.score for r in results if r.score is not None and not r.abandoned]
        days.append(
            HistoryDay(
                day=day,
                activity_id=activity_id,
                activity_slug=slugs[activity_id],
                results=len(results),
                abandoned=sum(r.abandoned for r in results),
                mean_score=round(sum(scores) / len(scores), 4) if scores else None,
                mean_duration_ms=round(sum(r.duration_ms for r in results) / len(results), 1),
                mean_difficulty=round(sum(r.difficulty_level for r in results) / len(results), 2),
            )
        )

    def _count(*conditions) -> int:
        return (
            db.scalar(
                select(func.count())
                .select_from(ActivitySession)
                .where(
                    ActivitySession.patient_id == patient.id,
                    ActivitySession.ended_at >= lower,
                    ActivitySession.ended_at < upper,
                    *conditions,
                )
            )
            or 0
        )

    today = datetime.now(tz).date()
    elapsed = [
        from_date + timedelta(days=i) for i in range((min(to_date, today) - from_date).days + 1)
    ]
    active_days = {day for day, _ in groups}

    return PerformanceHistory(
        patient_id=patient.id,
        timezone=patient.timezone,
        from_date=from_date,
        to_date=to_date,
        sessions_completed=_count(ActivitySession.status == SessionStatus.COMPLETED),
        sessions_ended_for_fatigue=_count(
            ActivitySession.end_reason == SessionEndReason.FATIGUE_DETECTED
        ),
        total_results=len(rows),
        days_with_activity=len(active_days),
        days_elapsed=len(elapsed),
        missing_days=[d for d in elapsed if d not in active_days],
        days=days,
        disclaimer=DISCLAIMER,
    )
