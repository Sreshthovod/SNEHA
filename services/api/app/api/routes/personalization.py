"""Personalization: activity catalog with specs, next-activity recommendation, result loop,
preferences, progress and Memory Bank retrieval.

The engine is deterministic (app/personalization/engine.py) and never calls an LLM or
any network service, so recommendations work whenever the API itself is reachable.
"""

from collections import Counter
from typing import Annotated

from fastapi import APIRouter, Query, Request, Response, status
from sqlalchemy import select

from app.api.deps import DbSessionDep, PrincipalDep, patient_access
from app.core.errors import AppError
from app.models.activities import (
    ActivityDefinition,
    ActivityRecommendation,
    ActivityResult,
)
from app.models.enums import Engagement, MemoryKind, MemoryStatus
from app.models.memories import MemoryItem
from app.models.patients import PatientPreferences
from app.personalization import engine
from app.personalization.config import get_activity_specs, get_personalization_config
from app.personalization.memory_retrieval import retrieve
from app.personalization.service import recommend_and_store, refresh_state, result_fact
from app.schemas.activities import ResultOut
from app.schemas.common import ErrorResponse
from app.schemas.memories import MemoryOut
from app.schemas.personalization import (
    ActivityProgress,
    CatalogEntry,
    FallbackOut,
    LevelOut,
    MemoryMatchOut,
    NextRequest,
    PreferencesOut,
    PreferencesUpdate,
    ProgressOut,
    RecommendationOut,
    ResultSubmission,
    ResultSubmissionOut,
    StateOut,
    SupportOut,
)
from app.services import activities as activity_service
from app.services import audit
from app.services.access import PatientAccess, Permission, authorize

router = APIRouter(tags=["personalization"])

_ERRORS = {
    401: {"model": ErrorResponse},
    403: {"model": ErrorResponse},
    404: {"model": ErrorResponse},
    409: {"model": ErrorResponse},
    422: {"model": ErrorResponse},
}


def to_out(db, rec: ActivityRecommendation) -> RecommendationOut:
    activity = db.get(ActivityDefinition, rec.activity_id) if rec.activity_id else None
    spec = get_activity_specs().get(activity.slug) if activity else None
    level = None
    if spec is not None and rec.difficulty is not None:
        try:
            level = spec.level(rec.difficulty).parameters
        except KeyError:
            level = None
    return RecommendationOut(
        id=rec.id,
        patient_id=rec.patient_id,
        session_id=rec.session_id,
        action=rec.action,
        activity_id=rec.activity_id,
        activity_slug=activity.slug if activity else None,
        activity_title=activity.title if activity else None,
        difficulty=rec.difficulty,
        level_parameters=level,
        instructions=spec.instructions if spec else None,
        hints_enabled=rec.hints_enabled,
        break_minutes=(rec.request_context or {}).get("break_minutes"),
        reason_codes=list(rec.reason_codes),
        supporting=[SupportOut(**s) for s in rec.supporting],
        content_refs={k: list(v) for k, v in (rec.content_refs or {}).items()},
        algorithm_version=rec.algorithm_version,
        config_version=rec.config_version,
        fallback=FallbackOut(used=rec.fallback_used, reason=rec.fallback_reason),
        created_at=rec.created_at,
    )


@router.get("/activities/catalog", response_model=list[CatalogEntry], responses=_ERRORS)
def catalog(_: PrincipalDep, db: DbSessionDep) -> list[CatalogEntry]:
    """Active activities with difficulty levels, instructions, hints, evaluation and stop rules."""
    specs = get_activity_specs()
    cfg = get_personalization_config()
    entries = []
    for a in db.scalars(
        select(ActivityDefinition)
        .where(ActivityDefinition.is_active.is_(True))
        .order_by(ActivityDefinition.slug)
    ):
        spec = specs.get(a.slug)
        if spec is None:  # guarded by tests; skip rather than serve an incomplete entry
            continue
        entries.append(
            CatalogEntry(
                id=a.id,
                slug=a.slug,
                version=a.version,
                title=a.title,
                description=a.description,
                activity_type=a.activity_type,
                cognitive_domains=a.cognitive_domains,
                min_difficulty=a.min_difficulty,
                max_difficulty=a.max_difficulty,
                default_duration_seconds=a.default_duration_seconds,
                supports_offline=a.supports_offline,
                uses_memory_bank=a.uses_memory_bank,
                instructions=spec.instructions,
                hint=spec.hint,
                evaluation=spec.evaluation,
                stop=spec.stop,
                accessibility=spec.accessibility,
                levels=[
                    LevelOut(level=lv.level, parameters=lv.parameters)
                    for lv in spec.levels
                    if a.min_difficulty <= lv.level <= a.max_difficulty
                ],
                content_languages=cfg.content_languages.get(a.slug, ["*"]),
                interest_tags=cfg.activity_interest_tags.get(a.slug, []),
            )
        )
    return entries


@router.post("/activities/next", response_model=RecommendationOut, responses=_ERRORS)
def next_activity(
    body: NextRequest, principal: PrincipalDep, db: DbSessionDep, request: Request
) -> RecommendationOut:
    """Recommend what to do next. A stop request is always honoured first."""
    access = authorize(
        db, principal.user, body.patient_id, Permission.RECORD_ACTIVITY, request=request
    )
    if body.session_id is not None:
        activity_service.get_session_for_patient(db, access.patient.id, body.session_id)
    rec = recommend_and_store(
        db,
        access.patient,
        session_id=body.session_id,
        stop_requested=body.stop_requested,
        fatigue_reported=body.fatigue_reported,
        available_slugs=body.available_slugs,
    )
    db.commit()
    return to_out(db, rec)


@router.post(
    "/activities/result",
    response_model=ResultSubmissionOut,
    status_code=status.HTTP_201_CREATED,
    responses={**_ERRORS, 200: {"model": ResultSubmissionOut, "description": "Duplicate result"}},
)
def submit_result(
    body: ResultSubmission,
    principal: PrincipalDep,
    db: DbSessionDep,
    request: Request,
    response: Response,
) -> ResultSubmissionOut:
    """Store a result, update personalization state and return the next recommendation.

    Safe to retry (idempotent by result ID). `stop_requested` or a result that reports
    tiredness changes the next recommendation (stop / break).
    """
    access = authorize(
        db, principal.user, body.patient_id, Permission.RECORD_ACTIVITY, request=request
    )
    activity_service.require_data_consent(db, access.patient.id)
    session = activity_service.get_session_for_patient(db, access.patient.id, body.session_id)
    result, created = activity_service.submit_result(db, session, body.result)
    state = refresh_state(db, access.patient.id, result.activity_id)
    rec = recommend_and_store(
        db,
        access.patient,
        session_id=session.id,
        stop_requested=body.stop_requested,
        available_slugs=body.available_slugs,
    )
    db.commit()
    if not created:
        response.status_code = status.HTTP_200_OK
    return ResultSubmissionOut(
        result=ResultOut.model_validate(result),
        duplicate=not created,
        personalization=StateOut.model_validate(state),
        next=to_out(db, rec),
    )


@router.get(
    "/patients/{patient_id}/recommendations",
    response_model=list[RecommendationOut],
    responses=_ERRORS,
)
def list_recommendations(
    db: DbSessionDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    access: PatientAccess = patient_access(Permission.VIEW_PROGRESS),
) -> list[RecommendationOut]:
    rows = db.scalars(
        select(ActivityRecommendation)
        .where(ActivityRecommendation.patient_id == access.patient.id)
        .order_by(ActivityRecommendation.created_at.desc())
        .limit(limit)
    )
    return [to_out(db, r) for r in rows]


# ---------- preferences ----------


def _preferences_out(db, access: PatientAccess) -> PreferencesOut:
    prefs = db.get(PatientPreferences, access.patient.id)
    tags: Counter[str] = Counter()
    for memory_tags in db.scalars(
        select(MemoryItem.tags).where(
            MemoryItem.patient_id == access.patient.id, MemoryItem.status == MemoryStatus.APPROVED
        )
    ):
        tags.update(t.lower() for t in memory_tags or [])
    return PreferencesOut(
        patient_id=access.patient.id,
        preferred_language=access.patient.preferred_language.value,
        interests=list(prefs.interests) if prefs else [],
        disliked_activity_slugs=list(prefs.disliked_activity_slugs) if prefs else [],
        session_minutes=prefs.session_minutes if prefs else 15,
        memory_tags=dict(sorted(tags.items())),
        updated_at=prefs.updated_at if prefs else None,
        updated_by_id=prefs.updated_by_id if prefs else None,
    )


@router.get("/patients/{patient_id}/preferences", response_model=PreferencesOut, responses=_ERRORS)
def get_preferences(
    db: DbSessionDep, access: PatientAccess = patient_access(Permission.VIEW_PROFILE)
) -> PreferencesOut:
    return _preferences_out(db, access)


@router.put("/patients/{patient_id}/preferences", response_model=PreferencesOut, responses=_ERRORS)
def put_preferences(
    body: PreferencesUpdate,
    principal: PrincipalDep,
    db: DbSessionDep,
    request: Request,
    access: PatientAccess = patient_access(Permission.MANAGE_PREFERENCES),
) -> PreferencesOut:
    """Replace the approved interests and preferences (managing caregivers only)."""
    known = set(db.scalars(select(ActivityDefinition.slug)))
    unknown = sorted(set(body.disliked_activity_slugs) - known)
    if unknown:
        raise AppError(422, "unknown_activity", f"Unknown activities: {', '.join(unknown)}")
    prefs = db.get(PatientPreferences, access.patient.id)
    if prefs is None:
        prefs = PatientPreferences(patient_id=access.patient.id)
        db.add(prefs)
    prefs.interests = sorted(set(body.interests))
    prefs.disliked_activity_slugs = sorted(set(body.disliked_activity_slugs))
    prefs.session_minutes = body.session_minutes
    prefs.updated_by_id = principal.id
    audit.record(
        db,
        "patient.preferences.update",
        actor_id=principal.id,
        patient_id=access.patient.id,
        request=request,
        details={"count": len(prefs.interests)},
    )
    db.commit()
    return _preferences_out(db, access)


# ---------- progress ----------


@router.get("/patients/{patient_id}/progress", response_model=ProgressOut, responses=_ERRORS)
def get_progress(
    db: DbSessionDep, access: PatientAccess = patient_access(Permission.VIEW_PROGRESS)
) -> ProgressOut:
    """Per-activity level and participation. Descriptive only; not a clinical measure."""
    cfg = get_personalization_config()
    pid = access.patient.id
    items = []
    for a in db.scalars(
        select(ActivityDefinition)
        .where(ActivityDefinition.is_active.is_(True))
        .order_by(ActivityDefinition.slug)
    ):
        rows = list(
            db.scalars(
                select(ActivityResult)
                .where(ActivityResult.patient_id == pid, ActivityResult.activity_id == a.id)
                .order_by(ActivityResult.completed_at, ActivityResult.id)
            )
        )
        fact = engine.ActivityFact(
            a.id, a.slug, a.min_difficulty, a.max_difficulty, a.uses_memory_bank
        )
        decision = engine.decide_difficulty(fact, [result_fact(r) for r in rows], cfg)
        items.append(
            ActivityProgress(
                activity_id=a.id,
                slug=a.slug,
                title=a.title,
                current_difficulty=decision.level,
                min_difficulty=a.min_difficulty,
                max_difficulty=a.max_difficulty,
                results=len(rows),
                completed=sum(not r.abandoned for r in rows),
                interrupted=sum(r.abandoned for r in rows),
                hints_used=sum(r.hint_count for r in rows),
                enjoyed=sum(r.engagement is Engagement.ENJOYED for r in rows),
                neutral=sum(r.engagement is Engagement.NEUTRAL for r in rows),
                not_enjoyed=sum(r.engagement is Engagement.NOT_ENJOYED for r in rows),
                fatigue_reports=sum(r.fatigue_reported for r in rows),
                last_played_at=rows[-1].completed_at if rows else None,
                difficulty_reason=decision.reasons[0].value,
            )
        )
    recent = db.scalars(
        select(ActivityRecommendation)
        .where(ActivityRecommendation.patient_id == pid)
        .order_by(ActivityRecommendation.created_at.desc())
        .limit(10)
    )
    return ProgressOut(
        patient_id=pid,
        algorithm_version=engine.ALGORITHM_VERSION,
        config_version=cfg.config_version,
        activities=items,
        recent_recommendations=[to_out(db, r) for r in recent],
    )


# ---------- memory retrieval ----------


@router.get(
    "/patients/{patient_id}/memories-retrieve",
    response_model=list[MemoryMatchOut],
    responses=_ERRORS,
)
def retrieve_memories(
    db: DbSessionDep,
    tags: Annotated[list[str], Query(max_length=20)] = [],  # noqa: B006
    kind: MemoryKind | None = None,
    with_photo: bool = False,
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
    access: PatientAccess = patient_access(Permission.VIEW_MEMORIES),
) -> list[MemoryMatchOut]:
    """Approved memories matching stored tags/kind (and stored relationships). Never inferred."""
    matches = retrieve(
        db, access.patient.id, tags=tags, kind=kind, with_photo=with_photo, limit=limit
    )
    return [
        MemoryMatchOut(
            memory=MemoryOut.model_validate(m.memory),
            score=m.score,
            matched_tags=m.matched_tags,
            via_relationship_to=m.via_relationship_to,
            recently_used=m.recently_used,
        )
        for m in matches
    ]
