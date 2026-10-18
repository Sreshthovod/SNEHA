from datetime import date, datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, StringConstraints, model_validator

from app.models.enums import ReviewItemStatus
from app.schemas.base import RequestModel, ResponseModel

REVIEW_MIN_DAYS = 3
REVIEW_MAX_DAYS = 31

Reason = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=1000)]

WORDING = (
    "An automated prompt from the person's own activity records. It is not a diagnosis and "
    "not a finding. A caregiver confirms or dismisses it; only confirmed items are shared "
    "with a clinician for discussion."
)


class ReviewScanRequest(RequestModel):
    period_start: date
    period_end: date

    @model_validator(mode="after")
    def _check_period(self) -> "ReviewScanRequest":
        days = (self.period_end - self.period_start).days + 1
        if not REVIEW_MIN_DAYS <= days <= REVIEW_MAX_DAYS:
            raise ValueError(
                f"Review period must cover {REVIEW_MIN_DAYS}–{REVIEW_MAX_DAYS} days (got {days})"
            )
        return self


class ReviewDecision(RequestModel):
    decision: Literal[ReviewItemStatus.CONFIRMED, ReviewItemStatus.DISMISSED]
    reason: Reason = Field(
        description="Why: what the caregiver knows (required for both decisions; kept)."
    )


class ReviewContext(RequestModel):
    note: Reason = Field(description="What the caregiver knows (kept; does not decide).")


class ContextNoteOut(BaseModel):
    by: str
    at: datetime
    note: str


class ReviewEvidence(BaseModel):
    result_ids: list[str] = Field(default_factory=list)
    results_considered: int = 0
    activities: list[str] = Field(default_factory=list)
    missing_days: list[date] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class ReviewItemOut(ResponseModel):
    id: str
    patient_id: str
    rule_id: str
    kind: Literal["change", "data", "context"]
    title: str
    explanation: str
    numbers: dict[str, Any]
    observation_ids: list[str]
    period_start: date
    period_end: date
    method_version: str
    config_version: str
    status: ReviewItemStatus
    decided_by_id: str | None
    decided_at: datetime | None
    decision_reason: str | None
    evidence: ReviewEvidence = Field(default_factory=ReviewEvidence)
    context_notes: list[ContextNoteOut] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    wording: str = WORDING
