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


class ReviewFlag(BaseModel):
    rule_id: str
    kind: Literal["change", "data", "context"]
    title: str
    explanation: str
    numbers: dict[str, Any]
    observation_ids: list[str] = Field(
        description="Caregiver observations in the period, as context for the reviewer."
    )
    wording: str = "May be worth a caregiver or clinician taking a look. Not a finding."


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
    review_flags: list[ReviewFlag]
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
    rules_not_evaluated: list[RuleNotEvaluated]
    disclaimer: str
