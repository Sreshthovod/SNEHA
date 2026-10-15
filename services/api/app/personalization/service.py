"""Glue between the database and the pure engine: load facts, recommend, persist."""

from dataclasses import asdict
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.time import utc_now
from app.models.activities import (
    ActivityDefinition,
    ActivityRecommendation,
    ActivityResult,
    ActivitySession,
    PersonalizationState,
)
from app.models.care import CaregiverObservation
from app.models.enums import RecommendationAction, SyncEntity, SyncOperation
from app.models.patients import PatientPreferences, PatientProfile
from app.personalization import engine
from app.personalization.config import PersonalizationConfig, get_personalization_config
from app.personalization.memory_retrieval import content_for_activities
from app.services.changes import log_change

MAX_RESULTS_LOADED = 400


def result_fact(r: ActivityResult) -> engine.ResultFact:
    mean_ms = (r.metrics or {}).get("mean_response_ms")
    return engine.ResultFact(
        id=r.id,
        activity_id=r.activity_id,
        completed_at=r.completed_at,
        difficulty=r.difficulty_level,
        score=r.score,
        hints=r.hint_count,
        abandoned=r.abandoned,
        engagement=r.engagement.value if r.engagement else None,
        fatigue_reported=r.fatigue_reported,
        mean_response_ms=float(mean_ms) if isinstance(mean_ms, int | float) else None,
    )


def get_preferences(db: Session, patient_id: str) -> PatientPreferences | None:
    return db.get(PatientPreferences, patient_id)


def build_input(
    db: Session,
    patient: PatientProfile,
    cfg: PersonalizationConfig,
    *,
    stop_requested: bool = False,
    fatigue_reported: bool = False,
    available_slugs: list[str] | None = None,
    context_tags: list[str] | None = None,
    context_memory_ids: list[str] | None = None,
) -> engine.EngineInput:
    now = utc_now()
    prefs = get_preferences(db, patient.id)
    interests = tuple(prefs.interests) if prefs else ()
    activities = tuple(
        engine.ActivityFact(a.id, a.slug, a.min_difficulty, a.max_difficulty, a.uses_memory_bank)
        for a in db.scalars(
            select(ActivityDefinition)
            .where(ActivityDefinition.is_active.is_(True))
            .order_by(ActivityDefinition.slug)
        )
    )
    rows = list(
        db.scalars(
            select(ActivityResult)
            .where(ActivityResult.patient_id == patient.id)
            .order_by(ActivityResult.completed_at.desc(), ActivityResult.id)
            .limit(MAX_RESULTS_LOADED)
        )
    )
    rows.reverse()
    results = tuple(result_fact(r) for r in rows)
    window = timedelta(
        hours=max(cfg.fatigue.observation_window_hours, cfg.fatigue.feedback_window_hours)
    )
    observations = tuple(
        engine.ObservationFact(o.id, o.category.value, o.observed_at)
        for o in db.scalars(
            select(CaregiverObservation).where(
                CaregiverObservation.patient_id == patient.id,
                CaregiverObservation.observed_at >= now - window,
            )
        )
    )
    session_ends = tuple(
        engine.SessionEndFact(s.id, s.ended_at, s.end_reason.value if s.end_reason else None)
        for s in db.scalars(
            select(ActivitySession).where(
                ActivitySession.patient_id == patient.id,
                ActivitySession.ended_at >= now - window,
            )
        )
        if s.ended_at is not None
    )
    return engine.EngineInput(
        now=now,
        language=patient.preferred_language.value,
        activities=activities,
        results=results,
        interests=interests,
        disliked_slugs=frozenset(prefs.disliked_activity_slugs) if prefs else frozenset(),
        observations=observations,
        session_ends=session_ends,
        content=content_for_activities(
            db,
            patient.id,
            interests,
            cfg,
            context_memory_ids=context_memory_ids or (),
            context_tags=context_tags or (),
        ),
        context_tags=tuple(context_tags or ()),
        stop_requested=stop_requested,
        fatigue_reported=fatigue_reported,
        available_slugs=frozenset(available_slugs) if available_slugs is not None else None,
    )


def recommend_and_store(
    db: Session,
    patient: PatientProfile,
    *,
    session_id: str | None = None,
    stop_requested: bool = False,
    fatigue_reported: bool = False,
    available_slugs: list[str] | None = None,
    context_tags: list[str] | None = None,
    context_memory_ids: list[str] | None = None,
    cfg: PersonalizationConfig | None = None,
) -> ActivityRecommendation:
    cfg = cfg or get_personalization_config()
    inp = build_input(
        db,
        patient,
        cfg,
        stop_requested=stop_requested,
        fatigue_reported=fatigue_reported,
        available_slugs=available_slugs,
        context_tags=context_tags,
        context_memory_ids=context_memory_ids,
    )
    rec = engine.recommend(inp, cfg)
    row = ActivityRecommendation(
        patient_id=patient.id,
        session_id=session_id,
        action=RecommendationAction(rec.action.value),
        activity_id=rec.activity.id if rec.activity else None,
        difficulty=rec.difficulty,
        reason_codes=rec.reason_codes,
        supporting=[asdict(s) for s in rec.supporting],
        content_refs={
            "memory_item_ids": list(rec.memory_item_ids),
            "routine_item_ids": list(rec.routine_item_ids),
        },
        hints_enabled=rec.hints_enabled,
        algorithm_version=engine.ALGORITHM_VERSION,
        config_version=cfg.config_version,
        fallback_used=rec.fallback_used,
        fallback_reason=rec.fallback_reason,
        request_context={
            "stop_requested": stop_requested,
            "fatigue_reported": fatigue_reported,
            "available_slugs": sorted(available_slugs) if available_slugs is not None else None,
            "context_tags": sorted(context_tags or []),
            "break_minutes": rec.break_minutes,
        },
    )
    db.add(row)
    db.flush()
    return row


def refresh_state(
    db: Session, patient_id: str, activity_id: str, cfg: PersonalizationConfig | None = None
) -> PersonalizationState:
    """Store the engine's current difficulty for one activity so devices can pull it."""
    cfg = cfg or get_personalization_config()
    activity = db.get(ActivityDefinition, activity_id)
    fact = engine.ActivityFact(
        activity.id,
        activity.slug,
        activity.min_difficulty,
        activity.max_difficulty,
        activity.uses_memory_bank,
    )
    rows = db.scalars(
        select(ActivityResult)
        .where(ActivityResult.patient_id == patient_id, ActivityResult.activity_id == activity_id)
        .order_by(ActivityResult.completed_at, ActivityResult.id)
    )
    facts = [result_fact(r) for r in rows]
    decision = engine.decide_difficulty(fact, facts, cfg)
    state = db.scalar(
        select(PersonalizationState).where(
            PersonalizationState.patient_id == patient_id,
            PersonalizationState.activity_id == activity_id,
        )
    )
    if state is None:
        state = PersonalizationState(patient_id=patient_id, activity_id=activity_id)
        db.add(state)
    state.current_difficulty = decision.level
    state.rules_version = engine.ALGORITHM_VERSION
    state.state = {
        "hints_enabled": decision.hints_enabled,
        "last_reason": decision.reasons[0].value,
        "results_considered": len(facts),
    }
    state.state_updated_at = utc_now()
    db.flush()
    log_change(db, SyncEntity.PERSONALIZATION_STATE, state.id, SyncOperation.UPSERT, patient_id)
    return state
