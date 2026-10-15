from datetime import date, datetime
from typing import Annotated, Any

from pydantic import Field, StringConstraints, field_validator, model_validator

from app.models.enums import ActivityType, Engagement, SessionEndReason, SessionStatus
from app.schemas.base import RecordId, RequestModel, ResponseModel, UtcDatetime

MetricKey = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]{0,39}$")]
MAX_METRICS = 20


class ActivityDefinitionOut(ResponseModel):
    id: str
    slug: str
    version: int
    title: str
    description: str
    activity_type: ActivityType
    cognitive_domains: list[str]
    min_difficulty: int
    max_difficulty: int
    default_duration_seconds: int
    supports_offline: bool
    uses_memory_bank: bool


class SessionCreate(RequestModel):
    id: RecordId | None = Field(default=None, description="Client-generated UUID (offline).")
    started_at: UtcDatetime
    device_install_id: RecordId | None = None


class SessionComplete(RequestModel):
    ended_at: UtcDatetime
    end_reason: SessionEndReason


class SessionOut(ResponseModel):
    id: str
    patient_id: str
    status: SessionStatus
    end_reason: SessionEndReason | None
    started_at: datetime
    ended_at: datetime | None
    created_at: datetime


class ResultCreate(RequestModel):
    """Idempotent by `id`: resubmitting the identical result returns the stored one."""

    id: RecordId
    activity_id: RecordId
    difficulty_level: int = Field(ge=1, le=10)
    started_at: UtcDatetime
    completed_at: UtcDatetime
    score: float | None = Field(default=None, ge=0, le=1)
    correct_count: int = Field(default=0, ge=0, le=10_000)
    attempt_count: int = Field(default=0, ge=0, le=10_000)
    hint_count: int = Field(default=0, ge=0, le=10_000)
    duration_ms: int = Field(ge=0, le=6 * 60 * 60 * 1000)
    abandoned: bool = False
    metrics: dict[MetricKey, float | int | bool] = Field(
        default_factory=dict,
        description="Small numeric activity-specific metrics, e.g. {'mean_response_ms': 2100}.",
    )
    engagement: Engagement | None = Field(
        default=None, description="Answer to 'Did you enjoy this?'. Null = not asked/skipped."
    )
    fatigue_reported: bool = Field(default=False, description="The patient said they were tired.")
    recommendation_id: RecordId | None = Field(
        default=None, description="The recommendation this activity was started from."
    )

    @field_validator("metrics")
    @classmethod
    def _limit_metrics(cls, value: dict[str, Any]) -> dict[str, Any]:
        if len(value) > MAX_METRICS:
            raise ValueError(f"At most {MAX_METRICS} metrics are allowed")
        return value

    @model_validator(mode="after")
    def _check_consistency(self) -> "ResultCreate":
        if self.completed_at < self.started_at:
            raise ValueError("completed_at must not be before started_at")
        if self.correct_count > self.attempt_count:
            raise ValueError("correct_count cannot exceed attempt_count")
        return self


class ResultOut(ResponseModel):
    id: str
    session_id: str
    patient_id: str
    activity_id: str
    activity_version: int
    difficulty_level: int
    started_at: datetime
    completed_at: datetime
    score: float | None
    correct_count: int
    attempt_count: int
    hint_count: int
    duration_ms: int
    abandoned: bool
    metrics: dict[str, Any]
    engagement: Engagement | None
    fatigue_reported: bool
    recommendation_id: str | None
    created_at: datetime


class HistoryDay(ResponseModel):
    day: date = Field(description="Calendar day in the patient's timezone.")
    activity_id: str
    activity_slug: str
    results: int
    abandoned: int
    mean_score: float | None
    mean_duration_ms: float
    mean_difficulty: float


class PerformanceHistory(ResponseModel):
    """Descriptive activity statistics. Not a clinical assessment."""

    patient_id: str
    timezone: str
    from_date: date
    to_date: date
    sessions_completed: int
    sessions_ended_for_fatigue: int
    total_results: int
    days_with_activity: int
    days_elapsed: int = Field(description="Days in range up to today (patient timezone).")
    missing_days: list[date] = Field(
        description="Elapsed days with no activity results. Shown as a data-gap warning, "
        "never interpreted as decline."
    )
    days: list[HistoryDay]
    disclaimer: str
