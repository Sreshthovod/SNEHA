"""Load persisted data into frames and assemble an AnalyticsSummary."""

from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.analytics import compute
from app.analytics.config import AnalyticsConfig, get_analytics_config
from app.analytics.schemas import AnalyticsSummary
from app.models.activities import (
    ActivityDefinition,
    ActivityEvent,
    ActivityResult,
    ActivitySession,
)
from app.models.care import CaregiverObservation
from app.models.enums import AuthSessionKind
from app.models.patients import PatientProfile
from app.models.sync import SyncMutation
from app.models.users import AuthSession
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


def _events(db: Session, session_ids: list[str]) -> pd.DataFrame:
    columns = ["id", "session_id", "event_type", "source", "action"]
    if not session_ids:
        return pd.DataFrame({c: pd.Series(dtype="object") for c in columns})
    rows = db.scalars(select(ActivityEvent).where(ActivityEvent.session_id.in_(session_ids))).all()
    return pd.DataFrame.from_records(
        [
            {
                "id": e.id,
                "session_id": e.session_id,
                "event_type": e.event_type.value,
                "source": (e.data or {}).get("source"),
                "action": (e.data or {}).get("action"),
            }
            for e in rows
        ],
        columns=columns,
    )


def sync_status(db: Session, patient: PatientProfile, upper: datetime, now: datetime) -> dict:
    """'May be incomplete' when a paired phone has not synced since the period ended (it may
    still hold activities recorded offline), or the period is still running."""
    phones = list(
        db.scalars(
            select(AuthSession).where(
                AuthSession.user_id == patient.user_id,
                AuthSession.kind == AuthSessionKind.DEVICE,
                AuthSession.revoked_at.is_(None),
            )
        )
    )
    pushed = db.scalar(
        select(func.max(SyncMutation.received_at)).where(SyncMutation.patient_id == patient.id)
    )
    pulled = max((p.last_pull_at for p in phones if p.last_pull_at), default=None)
    last = max((t for t in (pushed, pulled) if t is not None), default=None)
    if not phones:
        return {
            "phone_paired": False,
            "last_phone_sync_at": last,
            "may_be_incomplete": False,
            "reason": None,
        }
    if upper > now:
        return {
            "phone_paired": True,
            "last_phone_sync_at": last,
            "may_be_incomplete": True,
            "reason": "the period has not ended yet",
        }
    if last is None or last < upper:
        return {
            "phone_paired": True,
            "last_phone_sync_at": last,
            "may_be_incomplete": True,
            "reason": "the phone has not shared its records since the end of this period; "
            "activities done offline may be missing",
        }
    return {
        "phone_paired": True,
        "last_phone_sync_at": last,
        "may_be_incomplete": False,
        "reason": None,
    }


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
        support=compute.support_summary(
            _events(db, list(sessions["id"]) if len(sessions) else []), sessions
        ),
        sync=sync_status(db, patient, upper, now),
        baseline={
            "status": base.status,
            "from_date": base.from_date,
            "to_date": base.to_date,
            "results": base.results,
            "days": base.days,
            "required_results": base.required_results,
            "required_days": base.required_days,
            "comparisons": base.comparisons,
            "activities_compared": base.activities_compared,
            "activities_not_compared": base.activities_not_compared,
            "per_activity": base.per_activity,
            "reason": base.reason,
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
