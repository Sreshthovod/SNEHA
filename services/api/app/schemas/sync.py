from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import Field, StringConstraints

from app.models.enums import (
    ConversationProviderUsed,
    Language,
    SessionEndReason,
    SessionStatus,
    SyncEntity,
    SyncMutationStatus,
    SyncOperation,
)
from app.schemas.activities import ResultCreate
from app.schemas.base import RecordId, RequestModel, ResponseModel, UtcDatetime

MAX_MUTATIONS_PER_PUSH = 200
IntentLabel = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]{0,39}$")]


class SessionPayload(RequestModel):
    id: RecordId
    started_at: UtcDatetime
    ended_at: UtcDatetime | None = None
    status: SessionStatus
    end_reason: SessionEndReason | None = None


class ResultPayload(ResultCreate):
    session_id: RecordId


class ConversationPayload(RequestModel):
    """Conversation METADATA only. There is deliberately no field for transcripts."""

    id: RecordId
    session_id: RecordId | None = None
    started_at: UtcDatetime
    ended_at: UtcDatetime | None = None
    language: Language
    provider: ConversationProviderUsed
    fallback_used: bool = False
    turn_count: int = Field(ge=0, le=1000)
    intents: list[IntentLabel] = Field(default_factory=list, max_length=50)
    error_code: Annotated[str, StringConstraints(max_length=64)] | None = None


class PersonalizationPayload(RequestModel):
    activity_id: RecordId
    current_difficulty: int = Field(ge=1, le=10)
    rules_version: Annotated[str, StringConstraints(min_length=1, max_length=20)]
    state: dict[Annotated[str, StringConstraints(max_length=40)], float | int | bool | str] = Field(
        default_factory=dict, max_length=30
    )
    state_updated_at: UtcDatetime


class SessionMutation(RequestModel):
    mutation_id: RecordId
    entity_type: Literal[SyncEntity.ACTIVITY_SESSION]
    operation: Literal[SyncOperation.UPSERT] = SyncOperation.UPSERT
    data: SessionPayload


class ResultMutation(RequestModel):
    mutation_id: RecordId
    entity_type: Literal[SyncEntity.ACTIVITY_RESULT]
    operation: Literal[SyncOperation.UPSERT] = SyncOperation.UPSERT
    data: ResultPayload


class ConversationMutation(RequestModel):
    mutation_id: RecordId
    entity_type: Literal[SyncEntity.CONVERSATION]
    operation: Literal[SyncOperation.UPSERT] = SyncOperation.UPSERT
    data: ConversationPayload


class PersonalizationMutation(RequestModel):
    mutation_id: RecordId
    entity_type: Literal[SyncEntity.PERSONALIZATION_STATE]
    operation: Literal[SyncOperation.UPSERT] = SyncOperation.UPSERT
    data: PersonalizationPayload


Mutation = Annotated[
    SessionMutation | ResultMutation | ConversationMutation | PersonalizationMutation,
    Field(discriminator="entity_type"),
]


class SyncPushRequest(RequestModel):
    device_install_id: RecordId
    mutations: list[Mutation] = Field(min_length=1, max_length=MAX_MUTATIONS_PER_PUSH)


class MutationResult(ResponseModel):
    mutation_id: str
    entity_type: SyncEntity
    entity_id: str
    status: SyncMutationStatus
    detail: str | None = None


class SyncPushResponse(ResponseModel):
    results: list[MutationResult]


class SyncChangeOut(ResponseModel):
    seq: int
    entity_type: SyncEntity
    entity_id: str
    operation: SyncOperation
    changed_at: datetime
    data: dict[str, Any] | None = Field(description="Current record; null for deletes.")


class SyncPullResponse(ResponseModel):
    changes: list[SyncChangeOut]
    next_since: int = Field(description="Pass as `since` on the next pull.")
    has_more: bool
