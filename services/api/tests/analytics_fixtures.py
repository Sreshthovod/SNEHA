"""SYNTHETIC analytics fixtures: fictional activity data written straight to the database
so dates, scores and response times are exact. No real person's data."""

import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.models.activities import ActivityResult, ActivitySession
from app.models.care import CaregiverObservation
from app.models.enums import (
    Engagement,
    ObservationCategory,
    RecordSource,
    SessionEndReason,
    SessionStatus,
)

IST = ZoneInfo("Asia/Kolkata")
PAIRS = "4b0c2d0e-5f0e-4c39-9d43-1a6f3f0a0001"  # picture-pairs, levels 1–5
OBJECTS = "4b0c2d0e-5f0e-4c39-9d43-1a6f3f0a0009"  # name-the-object, levels 1–3
STORY = "4b0c2d0e-5f0e-4c39-9d43-1a6f3f0a0007"  # story-time, unscored


@dataclass
class R:
    """One synthetic result. `at` is local (IST) time on `day`."""

    day: date
    score: float | None = 0.9
    at: time = time(10, 0)
    activity: str = PAIRS
    difficulty: int = 2
    hints: int = 0
    abandoned: bool = False
    rt_ms: float | None = 2000.0
    engagement: str | None = None
    fatigue: bool = False


def local(day: date, at: time = time(10, 0)) -> datetime:
    return datetime.combine(day, at, tzinfo=IST).astimezone(UTC)


def seed(db: Session, patient_id: str, rows: list[R], *, end_reason: str | None = None) -> None:
    """One session per day containing that day's results."""
    by_day: dict[date, list[R]] = {}
    for row in rows:
        by_day.setdefault(row.day, []).append(row)
    for day, day_rows in sorted(by_day.items()):
        start = local(day, min(r.at for r in day_rows)) - timedelta(minutes=1)
        abandoned = any(r.abandoned for r in day_rows)
        session = ActivitySession(
            id=str(uuid.uuid4()),
            patient_id=patient_id,
            status=SessionStatus.ABANDONED if abandoned else SessionStatus.COMPLETED,
            end_reason=SessionEndReason(end_reason)
            if end_reason
            else (SessionEndReason.USER_STOPPED if abandoned else SessionEndReason.COMPLETED),
            source=RecordSource.DEVICE,
            started_at=start,
            ended_at=local(day, max(r.at for r in day_rows)) + timedelta(minutes=3),
        )
        db.add(session)
        db.flush()
        for r in day_rows:
            completed = local(day, r.at)
            db.add(
                ActivityResult(
                    id=str(uuid.uuid4()),
                    session_id=session.id,
                    patient_id=patient_id,
                    activity_id=r.activity,
                    activity_version=1,
                    difficulty_level=r.difficulty,
                    started_at=completed - timedelta(minutes=2),
                    completed_at=completed,
                    score=r.score,
                    correct_count=0,
                    attempt_count=0,
                    hint_count=r.hints,
                    duration_ms=120_000,
                    abandoned=r.abandoned,
                    metrics={"mean_response_ms": r.rt_ms} if r.rt_ms is not None else {},
                    engagement=Engagement(r.engagement) if r.engagement else None,
                    fatigue_reported=r.fatigue,
                )
            )
    db.commit()


def observe(
    db: Session,
    patient_id: str,
    day: date,
    category: str = "fatigue",
    note: str = "Synthetic note: seemed tired after lunch",
) -> str:
    obs = CaregiverObservation(
        id=str(uuid.uuid4()),
        patient_id=patient_id,
        observed_at=local(day, time(14, 0)),
        category=ObservationCategory(category),
        note=note,
    )
    db.add(obs)
    db.commit()
    return obs.id


def days(start: date, n: int) -> list[date]:
    return [start + timedelta(days=i) for i in range(n)]


# Baseline: 12 comfortable results over 6 days before the period.
PERIOD_START = date(2026, 9, 20)
PERIOD_END = date(2026, 9, 28)  # 9 days
BASELINE_DAYS = days(date(2026, 9, 10), 6)


def baseline_rows(score: float = 0.9, rt: float = 2000.0) -> list[R]:
    return [R(d, score=score, rt_ms=rt, at=t) for d in BASELINE_DAYS for t in (time(10), time(11))]
