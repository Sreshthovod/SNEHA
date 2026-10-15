"""Conversation understanding (Stage 4).

POST /conversation/analyze: understand one message, ground it in the patient's approved
Memory Bank, and suggest an activity through the deterministic personalization engine.
The model (if any) never talks to the patient directly and never acts on its own.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Request

from app.api.deps import DbSessionDep, PrincipalDep, SettingsDep
from app.api.routes.personalization import to_out
from app.conversation import service
from app.conversation.guard import Guarded
from app.conversation.service import ProviderOverrides
from app.schemas.common import ErrorResponse
from app.schemas.conversation import (
    AnalyzeRequest,
    AnalyzeResponse,
    FallbackOut,
    MemoryCandidateOut,
    PersonOut,
    PlaceOut,
    RoutineOut,
    SafetyOut,
    UncertainOut,
    UnderstandingOut,
)
from app.schemas.memories import MemoryOut
from app.services import activities as activity_service
from app.services.access import Permission, authorize

router = APIRouter(prefix="/conversation", tags=["conversation"])


def get_provider_overrides() -> ProviderOverrides:
    return ProviderOverrides()


_ERRORS = {
    401: {"model": ErrorResponse},
    403: {"model": ErrorResponse},
    404: {"model": ErrorResponse},
    409: {"model": ErrorResponse},
    422: {"model": ErrorResponse},
}


def _understanding(g: Guarded, context) -> UnderstandingOut:
    def routine_out(r):
        stored = context.routine(r.routine_id)
        return RoutineOut(
            mention=r.mention,
            status="stored_fact" if stored else "uncertain",
            routine_id=stored.id if stored else None,
            title=stored.title if stored else None,
            local_time=stored.local_time if stored else None,
        )

    return UnderstandingOut(
        topic=g.topic,
        intents=g.intents,
        people=[
            PersonOut(
                mention=p.mention,
                status="stored_fact" if p.memory_id else "uncertain",
                memory_id=p.memory_id,
                relationship_word=p.relationship_word,
            )
            for p in g.people
        ],
        places=[
            PlaceOut(
                mention=p.mention,
                status="stored_fact" if p.memory_id else "uncertain",
                memory_id=p.memory_id,
            )
            for p in g.places
        ],
        routines=[routine_out(r) for r in g.routines],
        topic_tags=g.topic_tags,
        fatigue_expressed=g.fatigue,
        distress_expressed=g.distress,
        stop_requested=g.stop,
        uncertain=g.uncertain,
        clarification=g.clarification,
        uncertain_interpretations=[
            UncertainOut(type=u.type, mention=u.mention, note=u.note)
            for u in g.uncertain_interpretations
        ],
    )


@router.post("/analyze", response_model=AnalyzeResponse, responses=_ERRORS)
def analyze(
    body: AnalyzeRequest,
    principal: PrincipalDep,
    db: DbSessionDep,
    settings: SettingsDep,
    request: Request,
    overrides: Annotated[ProviderOverrides, Depends(get_provider_overrides)],
) -> AnalyzeResponse:
    """Understand one message. The text is not stored or logged."""
    access = authorize(
        db, principal.user, body.patient_id, Permission.RECORD_ACTIVITY, request=request
    )
    patient = access.patient
    activity_service.require_data_consent(db, patient.id)
    if body.session_id is not None:
        activity_service.get_session_for_patient(db, patient.id, body.session_id)

    outcome = service.understand(db, settings, patient.id, body.text, body.language, overrides)
    memories = service.relevant_memories(db, patient.id, outcome.guarded)
    rec, title = service.suggest(
        db,
        patient,
        outcome.guarded,
        memories,
        session_id=body.session_id,
        available_slugs=body.available_slugs,
    )
    record = service.record_turn(
        db,
        patient_id=patient.id,
        conversation_id=body.conversation_id,
        session_id=body.session_id,
        language=body.language,
        outcome=outcome,
    )
    reply = service.build_reply(body.language, patient, outcome, memories, rec, title)
    db.commit()

    g = outcome.guarded
    return AnalyzeResponse(
        conversation_id=record.id,
        provider=outcome.provider,
        fallback=FallbackOut(used=outcome.fallback_used, reason=outcome.fallback_reason),
        understanding=_understanding(g, outcome.context),
        memories=[MemoryOut.model_validate(m) for m in memories],
        memory_candidates=[
            MemoryCandidateOut(title=c.title, kind=c.kind, description=c.description)
            for c in g.candidates
        ],
        safety=SafetyOut(distress_detected=g.distress, message=reply if g.distress else None),
        suggestion=to_out(db, rec) if rec is not None else None,
        reply=reply,
    )
