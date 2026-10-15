from datetime import datetime
from typing import Annotated, Any

from pydantic import BaseModel, Field, StringConstraints

from app.models.enums import MemoryKind, RecommendationAction
from app.schemas.activities import ActivityDefinitionOut, ResultCreate, ResultOut
from app.schemas.base import RecordId, RequestModel, ResponseModel
from app.schemas.memories import MemoryOut

Slug = Annotated[str, StringConstraints(pattern=r"^[a-z0-9][a-z0-9-]{0,63}$")]
InterestTag = Annotated[
    str, StringConstraints(strip_whitespace=True, to_lower=True, min_length=1, max_length=40)
]

DISCLAIMER = (
    "Recommendations follow engagement rules to keep activities comfortable and enjoyable. "
    "They do not measure or indicate any medical condition."
)


class LevelOut(BaseModel):
    level: int
    parameters: dict[str, Any]


class CatalogEntry(ActivityDefinitionOut):
    instructions: str
    hint: str
    evaluation: str
    stop: str
    accessibility: str
    levels: list[LevelOut]
    content_languages: list[str]
    interest_tags: list[str]


class NextRequest(RequestModel):
    patient_id: RecordId
    session_id: RecordId | None = None
    stop_requested: bool = Field(default=False, description="Always honoured first.")
    fatigue_reported: bool = Field(default=False, description="The patient says they are tired.")
    available_slugs: list[Slug] | None = Field(
        default=None,
        max_length=50,
        description="Activities this device can run right now (e.g. offline content). Null = any.",
    )


class SupportOut(BaseModel):
    kind: str = Field(description="activity_result, caregiver_observation, memory_item, …")
    id: str
    detail: str


class FallbackOut(BaseModel):
    used: bool
    reason: str | None


class RecommendationOut(BaseModel):
    id: str
    patient_id: str
    session_id: str | None
    action: RecommendationAction
    activity_id: str | None
    activity_slug: str | None
    activity_title: str | None
    difficulty: int | None
    level_parameters: dict[str, Any] | None
    instructions: str | None
    hints_enabled: bool
    break_minutes: int | None
    reason_codes: list[str]
    supporting: list[SupportOut]
    content_refs: dict[str, list[str]]
    algorithm_version: str
    config_version: str
    fallback: FallbackOut
    created_at: datetime
    disclaimer: str = DISCLAIMER


class ResultSubmission(RequestModel):
    patient_id: RecordId
    session_id: RecordId
    result: ResultCreate
    stop_requested: bool = Field(default=False, description="Stop after this activity.")
    available_slugs: list[Slug] | None = Field(default=None, max_length=50)


class StateOut(ResponseModel):
    activity_id: str
    current_difficulty: int
    rules_version: str
    state: dict[str, Any]
    state_updated_at: datetime


class ResultSubmissionOut(BaseModel):
    result: ResultOut
    duplicate: bool = Field(description="True if this exact result was already stored.")
    personalization: StateOut
    next: RecommendationOut


class PreferencesUpdate(RequestModel):
    interests: list[InterestTag] = Field(default_factory=list, max_length=30)
    disliked_activity_slugs: list[Slug] = Field(default_factory=list, max_length=20)
    session_minutes: int = Field(default=15, ge=5, le=60)


class PreferencesOut(BaseModel):
    patient_id: str
    preferred_language: str
    interests: list[str] = Field(description="Approved by a managing caregiver.")
    disliked_activity_slugs: list[str]
    session_minutes: int
    memory_tags: dict[str, int] = Field(description="Tags on approved memories, with counts.")
    updated_at: datetime | None
    updated_by_id: str | None


class ActivityProgress(BaseModel):
    activity_id: str
    slug: str
    title: str
    current_difficulty: int
    min_difficulty: int
    max_difficulty: int
    results: int
    completed: int
    interrupted: int
    hints_used: int
    enjoyed: int
    neutral: int
    not_enjoyed: int
    fatigue_reports: int
    last_played_at: datetime | None
    difficulty_reason: str


class ProgressOut(BaseModel):
    patient_id: str
    algorithm_version: str
    config_version: str
    activities: list[ActivityProgress]
    recent_recommendations: list[RecommendationOut]
    disclaimer: str = DISCLAIMER


class MemoryMatchOut(BaseModel):
    memory: MemoryOut
    score: int
    matched_tags: list[str]
    via_relationship_to: list[str]
    recently_used: bool
    basis: str = Field(
        default="stored_fact",
        description="Matches come only from stored, approved tags, kinds and relationships.",
    )


class RetrieveQuery(BaseModel):
    tags: list[InterestTag] = []
    kind: MemoryKind | None = None
    with_photo: bool = False
    limit: int = 10
