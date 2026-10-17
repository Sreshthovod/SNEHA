"""Activity events: what happened inside an activity run (migration 0009)."""

from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import Field, StringConstraints

from app.models.enums import ActivityEventType
from app.schemas.base import RecordId, RequestModel, ResponseModel, UtcDatetime

ReasonCode = Annotated[str, StringConstraints(pattern=r"^[A-Z][A-Z0-9_]{0,63}$")]
AdaptationAction = Literal["continue", "show_hint", "shorten", "offer_break", "end_session"]
EventSource = Literal["patient", "caregiver", "system"]
FatigueLevel = Literal["mild", "severe"]
EndOutcome = Literal["completed", "stopped", "tired", "shortened", "ended_by_policy"]
ContentSource = Literal["personal", "generic"]
DecidedOn = Literal["device", "server"]


class EventData(RequestModel):
    """Small, typed values only. There is deliberately no free-text field."""

    correct: bool | None = None
    latency_ms: int | None = Field(default=None, ge=0, le=60 * 60 * 1000)
    hint_number: int | None = Field(default=None, ge=1, le=20)
    source: EventSource | None = None
    level: FatigueLevel | None = None
    action: AdaptationAction | None = None
    reason_codes: list[ReasonCode] = Field(default_factory=list, max_length=10)
    rounds_planned: int | None = Field(default=None, ge=0, le=100)
    rounds_remaining: int | None = Field(default=None, ge=0, le=100)
    difficulty: int | None = Field(default=None, ge=1, le=10)
    outcome: EndOutcome | None = None
    # Memory use (memory-based activities). IDs only, never titles or text. The server
    # stores them as sent; the dashboard shows titles only for memories that still exist,
    # belong to this patient and that the viewer may see.
    memory_ids: list[RecordId] = Field(
        default_factory=list, max_length=20, description="activity_started: every memory used"
    )
    memory_id: RecordId | None = Field(default=None, description="The memory this round shows")
    content_source: ContentSource | None = Field(
        default=None, description="activity_started: personal (approved memories) or generic"
    )
    # Engine 1.2.0: why this run was suggested, and where the decision was made.
    engine_reason_codes: list[ReasonCode] = Field(
        default_factory=list, max_length=16, description="activity_started: the engine's reasons"
    )
    decided_on: DecidedOn | None = Field(
        default=None,
        description="activity_started: 'device' (offline engine) or 'server'; absent when "
        "the person chose the activity themselves",
    )


class EventPayload(RequestModel):
    id: RecordId
    session_id: RecordId
    activity_id: RecordId
    seq: int = Field(ge=0, le=100_000, description="Order within the session.")
    event_type: ActivityEventType
    occurred_at: UtcDatetime
    round_index: int | None = Field(default=None, ge=0, le=100)
    data: EventData = Field(default_factory=EventData)


class EventOut(ResponseModel):
    id: str
    session_id: str
    activity_id: str
    seq: int
    event_type: ActivityEventType
    occurred_at: datetime
    round_index: int | None
    data: dict[str, Any]
