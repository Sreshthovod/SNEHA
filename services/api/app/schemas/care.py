from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints, model_validator

from app.models.enums import (
    FatigueLevel,
    ObservationCategory,
    ObservationStatus,
    RecordSource,
    ReportStatus,
)
from app.schemas.base import RequestModel, ResponseModel, ShortText, UtcDatetime

LocalTime = Annotated[str, StringConstraints(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")]


class ObservationCreate(RequestModel):
    observed_at: UtcDatetime
    category: ObservationCategory
    note: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]
    fatigue_level: FatigueLevel | None = Field(
        default=None,
        description="Only for category 'fatigue'. 'severe' means the next suggestion is a "
        "rest, and the patient's phone stops a running activity once it has synced.",
    )

    @model_validator(mode="after")
    def _level_only_for_fatigue(self) -> "ObservationCreate":
        if self.fatigue_level is not None and self.category is not ObservationCategory.FATIGUE:
            raise ValueError("fatigue_level is only allowed for category 'fatigue'")
        return self


ObservationNote = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)
]
WorkflowNote = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)
]


class ObservationCorrection(RequestModel):
    """Correct an observation. The previous content is kept as a revision."""

    expected_version: int = Field(ge=1)
    observed_at: UtcDatetime | None = None
    category: ObservationCategory | None = None
    note: ObservationNote | None = None
    fatigue_level: FatigueLevel | None = None
    reason: WorkflowNote = Field(description="Why it was corrected (kept in the history).")


class ObservationReview(RequestModel):
    expected_version: int = Field(ge=1)
    note: WorkflowNote | None = None


class ObservationResolve(RequestModel):
    expected_version: int = Field(ge=1)
    note: WorkflowNote = Field(description="What was done or why no action is needed.")


class ObservationOut(ResponseModel):
    id: str
    patient_id: str
    author_id: str | None
    observed_at: datetime
    category: ObservationCategory
    note: str
    fatigue_level: FatigueLevel | None = None
    created_at: datetime
    source: RecordSource
    status: ObservationStatus
    version: int
    updated_at: datetime | None
    reviewed_by_id: str | None
    reviewed_at: datetime | None
    review_note: str | None
    resolved_by_id: str | None
    resolved_at: datetime | None
    resolution_note: str | None


class ObservationRevisionOut(ResponseModel):
    id: str
    observation_id: str
    version: int = Field(description="The version these values belonged to.")
    observed_at: datetime
    category: ObservationCategory
    note: str
    corrected_by_id: str | None
    correction_reason: str | None
    created_at: datetime = Field(description="When the correction was made.")


class RoutineCreate(RequestModel):
    title: ShortText
    local_time: LocalTime = Field(description="24-hour HH:MM in the patient's timezone.")
    days_of_week: int = Field(ge=1, le=127, description="Bitmask: Mon=1, Tue=2 … Sun=64.")
    is_active: bool = True


class RoutineOut(ResponseModel):
    id: str
    patient_id: str
    title: str
    local_time: str
    days_of_week: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


REPORT_MIN_DAYS = 8
REPORT_MAX_DAYS = 9


class ReportRequest(RequestModel):
    """Request an 8–9 day summary report (inclusive calendar days, patient timezone)."""

    period_start: date
    period_end: date

    @model_validator(mode="after")
    def _check_period(self) -> "ReportRequest":
        days = (self.period_end - self.period_start).days + 1
        if not REPORT_MIN_DAYS <= days <= REPORT_MAX_DAYS:
            raise ValueError(
                f"Report period must cover {REPORT_MIN_DAYS}–{REPORT_MAX_DAYS} days (got {days})"
            )
        return self


class ReportOut(ResponseModel):
    id: str
    patient_id: str
    period_start: datetime
    period_end: datetime
    status: ReportStatus
    requested_by_id: str | None
    file_id: str | None
    generated_at: datetime | None
    error_message: str | None
    created_at: datetime
    automated: bool
    method_version: str | None


class FileOut(ResponseModel):
    id: str
    patient_id: str
    purpose: str
    content_type: str
    size_bytes: int
    sha256: str
    created_at: datetime


class DeviceSyncOut(BaseModel):
    device_name: str | None
    last_sync_at: datetime | None = Field(description="Last time the phone fetched changes.")


class FatigueDeliveryItem(BaseModel):
    observation_id: str
    status: Literal["sent", "waiting", "no_phone", "from_phone"] = Field(
        description="sent: the phone has fetched it; waiting: not yet (the phone applies it "
        "at its next sync); no_phone: no phone is paired; from_phone: reported on the phone"
    )
    sent_at: datetime | None = None


class FatigueDeliveryOut(BaseModel):
    """Whether caregivers' tiredness notes have reached the patient's phone. Honest status
    only: 'sent' means the phone fetched the change, not that an activity was running."""

    devices: list[DeviceSyncOut]
    items: list[FatigueDeliveryItem]
