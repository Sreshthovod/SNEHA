"""Load persisted data into frames and assemble an AnalyticsSummary."""

from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analytics import compute
from app.analytics.config import AnalyticsConfig, get_analytics_config
from app.analytics.schemas import AnalyticsSummary
from app.models.activities import ActivityDefinition, ActivityResult, ActivitySession
from app.models.care import CaregiverObservation
from app.models.patients import PatientProfile
from app.services.history import day_bounds

MAX_ANALYTICS_DAYS = 366


def _results(
    db: Session, patient: PatientProfile, lower: datetime, upper: datetime
) -> pd.DataFrame:
    tz = ZoneInfo(patient.timezone)
    rows = db.execute(
        select(ActivityResult, ActivityDefinition.slug, ActivityDefinition.title)
        .join(ActivityDefinition, ActivityDefinition.id == ActivityResult.activity_id)
        .where(
            ActivityResult.patient_id == patient.id,
            ActivityResult.completed_at >= lower,
            ActivityResult.completed_at < upper,
        )
        .order_by(ActivityResult.completed_at)
    ).all()
    if not rows:
        return compute.empty(compute.RESULT_COLUMNS)
    records = []
    for r, slug, title in rows:
        rt = (r.metrics or {}).get("mean_response_ms")
        records.append(
            {
                "id": r.id,
                "activity_id": r.activity_id,
                "slug": slug,
                "title": title,
                "session_id": r.session_id,
                "completed_at": r.completed_at,
                "day": r.completed_at.astimezone(tz).date(),
                "difficulty": r.difficulty_level,
                "score": r.score,
                "hints": r.hint_count,
                "abandoned": bool(r.abandoned),
                "engagement": r.engagement.value if r.engagement else None,
                "fatigue_reported": bool(r.fatigue_reported),
                "mean_response_ms": float(rt)
                if isinstance(rt, int | float) and not isinstance(rt, bool)
                else None,
                "duration_ms": r.duration_ms,
            }
        )
    return pd.DataFrame.from_records(records, columns=compute.RESULT_COLUMNS)


def _sessions(
    db: Session, patient: PatientProfile, lower: datetime, upper: datetime
) -> pd.DataFrame:
    tz = ZoneInfo(patient.timezone)
    rows = db.scalars(
        select(ActivitySession).where(
            ActivitySession.patient_id == patient.id,
            ActivitySession.started_at >= lower,
            ActivitySession.started_at < upper,
        )
    ).all()
    if not rows:
        return compute.empty(compute.SESSION_COLUMNS)
    return pd.DataFrame.from_records(
        [
            {
                "id": s.id,
                "started_at": s.started_at,
                "ended_at": s.ended_at,
                "day": s.started_at.astimezone(tz).date(),
                "status": s.status.value,
                "end_reason": s.end_reason.value if s.end_reason else None,
            }
            for s in rows
        ],
        columns=compute.SESSION_COLUMNS,
    )


def observations_in(
    db: Session, patient: PatientProfile, lower: datetime, upper: datetime
) -> list[CaregiverObservation]:
    return list(
        db.scalars(
            select(CaregiverObservation)
            .where(
                CaregiverObservation.patient_id == patient.id,
                CaregiverObservation.observed_at >= lower,
                CaregiverObservation.observed_at < upper,
            )
            .order_by(CaregiverObservation.observed_at)
        )
    )


def _observation_frame(rows: list[CaregiverObservation], tz: ZoneInfo) -> pd.DataFrame:
    if not rows:
        return compute.empty(compute.OBSERVATION_COLUMNS)
    return pd.DataFrame.from_records(
        [
            {
                "id": o.id,
                "observed_at": o.observed_at,
                "day": o.observed_at.astimezone(tz).date(),
                "category": o.category.value,
                "status": o.status.value,
                "source": o.source.value,
            }
            for o in rows
        ],
        columns=compute.OBSERVATION_COLUMNS,
    )


def summarise(
    db: Session,
    patient: PatientProfile,
    from_date: date,
    to_date: date,
    *,
    cfg: AnalyticsConfig | None = None,
    now: datetime | None = None,
) -> AnalyticsSummary:
    cfg = cfg or get_analytics_config()
    now = now or datetime.now(UTC)
    tz = ZoneInfo(patient.timezone)
    today = now.astimezone(tz).date()

    lower, upper = day_bounds(patient, from_date, to_date)
    baseline_to = from_date - timedelta(days=1)
    baseline_from = from_date - timedelta(days=cfg.baseline.window_days)
    b_lower, b_upper = day_bounds(patient, baseline_from, baseline_to)

    results = _results(db, patient, lower, upper)
    baseline_results = _results(db, patient, b_lower, b_upper)
    sessions = _sessions(db, patient, lower, upper)
    obs_rows = observations_in(db, patient, lower, upper)
    observations = _observation_frame(obs_rows, tz)

    days = compute.elapsed_days(from_date, to_date, today)
    active = set(results["day"]) if len(results) else set()
    missing = [d for d in days if d not in active]
    base = compute.baseline(baseline_results, results, baseline_from, baseline_to, cfg)
    flags, skipped = compute.review_flags(
        results, baseline_results, sessions, observations, base, days, cfg
    )
    activities = compute.per_activity(results)

    return AnalyticsSummary(
        patient_id=patient.id,
        timezone=patient.timezone,
        from_date=from_date,
        to_date=to_date,
        generated_at=now,
        method_version=compute.METHOD_VERSION,
        config_version=cfg.config_version,
        completeness={
            "days_elapsed": len(days),
            "days_with_activity": len(active & set(days)),
            "completeness_ratio": round(len(active & set(days)) / len(days), 4) if days else None,
            "missing_days": missing,
            "longest_gap_days": compute.longest_run(days, set(missing)),
        },
        totals=compute.totals(results, sessions),
        engagement=compute.engagement(results),
        activities=activities,
        preferences=compute.preferences(activities),
        daily=compute.daily(results, days),
        baseline={
            "status": base.status,
            "from_date": base.from_date,
            "to_date": base.to_date,
            "results": base.results,
            "days": base.days,
            "required_results": base.required_results,
            "required_days": base.required_days,
            "comparisons": base.comparisons,
        },
        review_flags=[f.__dict__ for f in flags],
        rules_not_evaluated=[s.__dict__ for s in skipped],
        context_observations=[
            {
                "id": o.id,
                "observed_at": o.observed_at,
                "category": o.category.value,
                "status": o.status.value,
                "source": o.source.value,
            }
            for o in obs_rows
        ],
        methodology=compute.METHODOLOGY,
        disclaimer=compute.DISCLAIMER,
    )
