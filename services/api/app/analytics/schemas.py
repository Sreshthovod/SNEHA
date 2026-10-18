"""Analytics response models. Every field is descriptive; none is a clinical measure."""

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class Completeness(BaseModel):
    days_elapsed: int = Field(description="Days in range up to today (patient timezone).")
    days_with_activity: int
    completeness_ratio: float | None = Field(description="days_with_activity ÷ days_elapsed.")
    missing_days: list[date]
    longest_gap_days: int


class Totals(BaseModel):
    results: int
    scored_results: int
    interrupted_results: int
    sessions_started: int
    sessions_ended: int
    sessions_completed: int
    sessions_stopped: int
    sessions_ended_for_fatigue: int
    sessions_interrupted: int = Field(
        default=0, description="Ended because the app was closed during an activity (timeout)."
    )
    sessions_in_progress: int = Field(
        default=0, description="Not ended yet (or the phone has not shared the ending)."
    )
    completion_rate: float | None
    interruption_rate: float | None
    accuracy_mean: float | None
    accuracy_median: float | None
    median_response_ms: float | None
    hints_per_result: float | None
    share_results_with_hints: float | None
    median_session_minutes: float | None
    total_session_minutes: float | None
    mean_difficulty: float | None


class EngagementCounts(BaseModel):
    enjoyed: int
    neutral: int
    not_enjoyed: int
    unanswered: int


class ActivityMetrics(BaseModel):
    activity_id: str
    slug: str
    title: str
    results: int
    completed: int
    interrupted: int
    accuracy_mean: float | None
    median_response_ms: float | None
    hints_per_result: float | None
    mean_difficulty: float | None
    enjoyed: int
    not_enjoyed: int
    last_played: date


class ActivityPreference(BaseModel):
    slug: str
    title: str
    results: int
    enjoyed: int
    not_enjoyed: int


class DailyMetrics(BaseModel):
    day: date
    has_data: bool
    results: int
    interrupted: int
    accuracy_mean: float | None
    median_response_ms: float | None
    hints_per_result: float | None


class BaselineComparison(BaseModel):
    metric: str
    unit: str
    baseline: float | None
    current: float | None
    change: float | None


class BaselineSummary(BaseModel):
    status: Literal["compared", "insufficient_data"]
    from_date: date
    to_date: date
    results: int
    days: int
    required_results: int
    required_days: int
    comparisons: list[BaselineComparison]
    activities_compared: list[str] = Field(
        default_factory=list, description="Activities played in both windows (like with like)."
    )
    activities_not_compared: list[str] = Field(
        default_factory=list, description="Played in this period only: not compared."
    )
    per_activity: list["ActivityComparison"] = Field(default_factory=list)
    reason: str | None = Field(default=None, description="Why no comparison was made.")


class ActivityComparison(BaseModel):
    activity_id: str
    title: str
    baseline_results: int
    period_results: int
    baseline_accuracy: float | None
    period_accuracy: float | None
    baseline_median_response_ms: float | None
    period_median_response_ms: float | None
    baseline_hints_per_result: float | None
    period_hints_per_result: float | None


class SupportSummary(BaseModel):
    """Support given during activities, from activity events. Counts are present only when
    at least one session in the period has a step-by-step record."""

    sessions_with_events: int
    sessions_started: int
    hints_asked_for: int | None = None
    hints_given_automatically: int | None = None
    read_aloud_presses: int | None = None
    pauses_by_person: int | None = None
    pauses_screen_left: int | None = None
    stop_requests: int | None = None
    rests_taken: int | None = None
    rests_declined: int | None = None
    adjustments: dict[str, int] | None = None


class SyncStatus(BaseModel):
    """Whether everything the phone recorded for this period has probably reached the server."""

    phone_paired: bool
    last_phone_sync_at: datetime | None
    may_be_incomplete: bool
    reason: str | None


class ReviewFlag(BaseModel):
    rule_id: str
    kind: Literal["change", "data", "context"]
    title: str
    explanation: str
    numbers: dict[str, Any]
    observation_ids: list[str] = Field(
        description="Caregiver observations in the period, as context for the reviewer."
    )
    wording: str = (
        "Not a finding. An automated prompt that a caregiver reviews before anything is "
        "shared with a clinician."
    )


class RuleNotEvaluated(BaseModel):
    rule_id: str
    reason: str


class ContextObservation(BaseModel):
    id: str
    observed_at: datetime
    category: str
    status: str
    source: str


class AnalyticsSummary(BaseModel):
    patient_id: str
    timezone: str
    from_date: date
    to_date: date
    generated_at: datetime
    method_version: str
    config_version: str
    completeness: Completeness
    totals: Totals
    engagement: EngagementCounts
    activities: list[ActivityMetrics]
    preferences: list[ActivityPreference]
    daily: list[DailyMetrics]
    baseline: BaselineSummary
    support: SupportSummary | None = None
    sync: SyncStatus | None = None
    review_flags: list[ReviewFlag]
    review_flags_withheld: bool = Field(
        default=False,
        description="True for clinicians: automated prompts are not shown to them. They see "
        "only items a caregiver confirmed (GET /patients/{id}/review-items).",
    )
    rules_not_evaluated: list[RuleNotEvaluated]
    context_observations: list[ContextObservation]
    methodology: list[str]
    disclaimer: str


class ReviewFlagsResponse(BaseModel):
    patient_id: str
    from_date: date
    to_date: date
    method_version: str
    config_version: str
    review_flags: list[ReviewFlag]
    review_flags_withheld: bool = Field(
        default=False,
        description="True for clinicians: automated prompts are not shown to them. They see "
        "only items a caregiver confirmed (GET /patients/{id}/review-items).",
    )
    rules_not_evaluated: list[RuleNotEvaluated]
    disclaimer: str
