from typing import Literal

from pydantic import BaseModel, Field

from app.conversation.extraction import MAX_INPUT_CHARS, Clarification, Intent
from app.models.enums import Language, MemoryKind
from app.schemas.base import RecordId, RequestModel
from app.schemas.memories import MemoryOut
from app.schemas.personalization import RecommendationOut, Slug

FactStatus = Literal["stored_fact", "uncertain"]


class AnalyzeRequest(RequestModel):
    patient_id: RecordId
    text: str = Field(
        min_length=1, max_length=MAX_INPUT_CHARS, description="Never stored or logged."
    )
    language: Language
    conversation_id: RecordId | None = Field(default=None, description="Client UUID; groups turns.")
    session_id: RecordId | None = None
    available_slugs: list[Slug] | None = Field(default=None, max_length=50)


class PersonOut(BaseModel):
    mention: str = Field(description="The person's own words.")
    status: FactStatus
    memory_id: str | None
    relationship_word: str | None = Field(
        description="Only when said by the person AND recorded in the approved memory."
    )


class PlaceOut(BaseModel):
    mention: str
    status: FactStatus
    memory_id: str | None


class RoutineOut(BaseModel):
    mention: str
    status: FactStatus
    routine_id: str | None
    title: str | None
    local_time: str | None


class UncertainOut(BaseModel):
    type: Literal["person", "place", "routine", "relationship"]
    mention: str
    note: str


class UnderstandingOut(BaseModel):
    topic: str
    intents: list[Intent]
    people: list[PersonOut]
    places: list[PlaceOut]
    routines: list[RoutineOut]
    topic_tags: list[str] = Field(description="Only tags already known to SNEHA.")
    fatigue_expressed: bool
    distress_expressed: bool
    stop_requested: bool
    uncertain: bool
    clarification: Clarification
    uncertain_interpretations: list[UncertainOut]


class MemoryCandidateOut(BaseModel):
    title: str
    kind: MemoryKind
    description: str | None
    requires_approval: Literal[True] = True
    note: str = "Not saved. A caregiver must review and approve it before it becomes a memory."


class SafetyOut(BaseModel):
    distress_detected: bool
    message: str | None


class FallbackOut(BaseModel):
    used: bool
    reason: str | None


class AnalyzeResponse(BaseModel):
    conversation_id: str
    provider: Literal["deterministic", "gemini", "local"]
    fallback: FallbackOut
    understanding: UnderstandingOut
    memories: list[MemoryOut] = Field(
        description="Approved memories that are relevant (stored facts)."
    )
    memory_candidates: list[MemoryCandidateOut]
    safety: SafetyOut
    suggestion: RecommendationOut | None = Field(
        description="From the deterministic personalization engine; null when distress is detected."
    )
    reply: str = Field(
        description="Safe text for the patient, built from templates and stored data."
    )
    disclaimer: str = (
        "SNEHA's assistant supports conversation and activities. It does not give medical "
        "advice or assess memory."
    )
