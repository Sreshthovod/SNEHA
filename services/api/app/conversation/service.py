"""conversation text → provider (with fallback) → guard → approved-memory retrieval →
deterministic activity recommendation → safe templated reply.

The text is used only in memory for this request. It is never stored, never logged and
never echoed back except as short, verified mentions of the person's own words.
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.conversation import templates
from app.conversation.context import PatientContext, load_context
from app.conversation.extraction import Clarification, Intent
from app.conversation.guard import Guarded, apply_guard
from app.conversation.providers.base import FailureCode, ProviderFailure
from app.conversation.providers.deterministic import DeterministicProvider
from app.conversation.providers.gemini import GeminiProvider
from app.conversation.providers.local import LocalModelProvider
from app.core.config import ConversationProvider, Settings
from app.core.errors import conflict
from app.core.time import utc_now
from app.models.activities import ActivityDefinition
from app.models.care import ConversationRecord
from app.models.enums import ConsentType, ConversationProviderUsed, Language, RecommendationAction
from app.models.memories import MemoryItem
from app.models.patients import PatientProfile
from app.personalization.config import get_personalization_config
from app.personalization.memory_retrieval import retrieve
from app.personalization.service import recommend_and_store
from app.services.access import has_consent

logger = logging.getLogger(__name__)


@dataclass
class ProviderOverrides:
    """Injection points for tests (fake Gemini client, fake local HTTP opener)."""

    gemini_client_factory: Callable[[str, float], Any] | None = None
    local_opener: Callable[..., Any] | None = None


@dataclass
class Outcome:
    provider: str
    fallback_used: bool
    fallback_reason: str | None
    guarded: Guarded
    context: PatientContext


def choose_provider(settings: Settings, db: Session, patient_id: str, overrides: ProviderOverrides):
    """Returns (provider or None, reason it was skipped)."""
    match settings.conversation_provider:
        case ConversationProvider.GEMINI:
            if not settings.gemini_configured:
                return None, FailureCode.NOT_CONFIGURED
            if not has_consent(db, patient_id, ConsentType.CLOUD_AI):
                return None, FailureCode.NO_CLOUD_CONSENT
            return GeminiProvider(
                api_key=settings.gemini_api_key.get_secret_value(),
                model=settings.gemini_model,
                timeout_seconds=settings.gemini_timeout_seconds,
                max_output_tokens=settings.gemini_max_output_tokens,
                client_factory=overrides.gemini_client_factory,
            ), None
        case ConversationProvider.LOCAL:
            if not settings.local_llm_base_url:
                return None, FailureCode.NOT_CONFIGURED
            return LocalModelProvider(
                base_url=settings.local_llm_base_url,
                model=settings.local_llm_model,
                timeout_seconds=settings.local_llm_timeout_seconds,
                opener=overrides.local_opener,
            ), None
        case _:
            return None, None


def understand(
    db: Session,
    settings: Settings,
    patient_id: str,
    text: str,
    language: Language,
    overrides: ProviderOverrides,
) -> Outcome:
    context = load_context(db, patient_id, get_personalization_config())
    provider, skipped = choose_provider(settings, db, patient_id, overrides)
    fallback_reason = skipped.value if skipped else None
    name = DeterministicProvider.name
    extraction = None
    if provider is not None:
        try:
            extraction = provider.analyze(text, language, context)
            name = provider.name
        except ProviderFailure as failure:
            fallback_reason = failure.code.value
            logger.info(
                "Conversation provider %s failed: %s; using deterministic",
                provider.name,
                failure.code,
            )
    if extraction is None:
        extraction = DeterministicProvider().analyze(text, language, context)
    return Outcome(
        provider=name,
        fallback_used=fallback_reason is not None,
        fallback_reason=fallback_reason,
        guarded=apply_guard(extraction, text, context),
        context=context,
    )


def record_turn(
    db: Session,
    *,
    patient_id: str,
    conversation_id: str | None,
    session_id: str | None,
    language: Language,
    outcome: Outcome,
) -> ConversationRecord:
    """Upsert conversation METADATA. The text is never stored."""
    record = db.get(ConversationRecord, conversation_id) if conversation_id else None
    if record is not None and record.patient_id != patient_id:
        raise conflict("id_conflict", "This conversation ID is already in use.")
    if record is None:
        record = ConversationRecord(
            patient_id=patient_id,
            session_id=session_id,
            started_at=utc_now(),
            language=language,
            provider=ConversationProviderUsed.DETERMINISTIC,
            turn_count=0,
            intents=[],
            extra={},
        )
        if conversation_id:
            record.id = conversation_id
        db.add(record)
    record.provider = ConversationProviderUsed(outcome.provider)
    record.language = language
    record.turn_count += 1
    record.intents = sorted(set(record.intents or []) | {i.value for i in outcome.guarded.intents})[
        :50
    ]
    record.fallback_used = record.fallback_used or outcome.fallback_used
    record.error_code = outcome.fallback_reason if outcome.fallback_used else record.error_code
    db.flush()
    return record


def build_reply(
    language: Language,
    patient: PatientProfile,
    outcome: Outcome,
    memories: list[MemoryItem],
    suggestion,
    suggestion_title: str | None,
) -> str:
    g = outcome.guarded
    t = lambda key, **v: templates.text(language, key, **v)  # noqa: E731
    if g.distress:
        return t("safety")
    if g.stop:
        return t("stop")
    if g.fatigue:
        return t("fatigue")

    tz = ZoneInfo(patient.timezone)
    local_now = datetime.now(tz)
    parts: list[str] = []
    if Intent.GREETING in g.intents:
        parts.append(t("greeting"))
    if Intent.ASK_TIME in g.intents:
        parts.append(t("time", time=local_now.strftime("%H:%M")))
    if Intent.ASK_DATE in g.intents:
        parts.append(t("date", date=local_now.strftime("%A, %d %B %Y")))
    if Intent.ASK_ROUTINE in g.intents or g.routines:
        upcoming = [
            r for r in outcome.context.routines if r.local_time > local_now.strftime("%H:%M")
        ]
        parts.append(
            t("routine_next", title=upcoming[0].title, time=upcoming[0].local_time)
            if upcoming
            else t("routine_none")
        )
    if memories:
        parts.append(t("memory", title=memories[0].title))
    clarify = {
        Clarification.WHICH_PERSON: "which_person",
        Clarification.WHICH_PLACE: "which_place",
        Clarification.WHICH_ROUTINE: "which_routine",
        Clarification.UNCLEAR_REQUEST: "unclear",
    }.get(g.clarification)
    if clarify and not memories:
        parts.append(t(clarify))
    if g.candidates:
        parts.append(t("candidate"))
    if (
        suggestion is not None
        and suggestion.action is RecommendationAction.ACTIVITY
        and suggestion.activity_id
    ):
        title = suggestion_title
        if title and (
            Intent.REQUEST_ACTIVITY in g.intents or memories or g.topic_tags or not parts
        ):
            parts.append(t("suggest", title=title))
    if Intent.FAREWELL in g.intents:
        parts.append(t("farewell"))
    return " ".join(parts) if parts else t("unclear")


def relevant_memories(db: Session, patient_id: str, guarded: Guarded) -> list[MemoryItem]:
    """This patient's approved memories: named in the conversation first, then tag matches."""
    if not guarded.memory_ids and not guarded.topic_tags:
        return []
    matches = retrieve(
        db, patient_id, tags=guarded.topic_tags, memory_ids=guarded.memory_ids, limit=5
    )
    return [m.memory for m in matches if m.score > 2]  # photo bonus alone is not relevance


def suggest(
    db: Session,
    patient: PatientProfile,
    guarded: Guarded,
    memories: list[MemoryItem],
    *,
    session_id: str | None,
    available_slugs: list[str] | None,
):
    if guarded.distress:
        return None, None  # safety first: no activity
    rec = recommend_and_store(
        db,
        patient,
        session_id=session_id,
        stop_requested=guarded.stop,
        fatigue_reported=guarded.fatigue,
        available_slugs=available_slugs,
        context_tags=guarded.topic_tags,
        context_memory_ids=[m.id for m in memories],
    )
    activity = db.get(ActivityDefinition, rec.activity_id) if rec.activity_id else None
    return rec, (activity.title if activity else None)
