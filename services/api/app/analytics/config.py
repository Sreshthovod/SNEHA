"""Load and validate config/analytics.toml (override with SNEHA_ANALYTICS_CONFIG)."""

import os
import tomllib
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "analytics.toml"


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class BaselineRules(_Strict):
    window_days: int = Field(ge=7, le=365)
    min_results: int = Field(ge=3)
    min_days: int = Field(ge=2)


class PeriodRules(_Strict):
    min_results: int = Field(ge=2)
    min_days: int = Field(ge=2)  # >= 2 guarantees a flag never rests on a single day


class ReviewRules(_Strict):
    min_share_of_days: float = Field(gt=0.5, le=1)
    accuracy_drop: float = Field(gt=0, le=1)
    response_time_increase: float = Field(gt=0)
    interruption_rate_increase: float = Field(gt=0, le=1)
    min_sessions_for_interruptions: int = Field(ge=2)
    hint_rate_increase: float = Field(gt=0)
    low_engagement_min_answers: int = Field(ge=2)
    low_engagement_share: float = Field(gt=0, le=1)
    data_gap_share: float = Field(gt=0, le=1)
    data_gap_consecutive_days: int = Field(ge=2)
    fatigue_min_signals: int = Field(ge=2)
    fatigue_min_days: int = Field(ge=2)


class AnalyticsConfig(_Strict):
    config_version: str = Field(min_length=1, max_length=20)
    baseline: BaselineRules
    period: PeriodRules
    review: ReviewRules


@lru_cache
def get_analytics_config() -> AnalyticsConfig:
    path = Path(os.environ.get("SNEHA_ANALYTICS_CONFIG", CONFIG_PATH))
    return AnalyticsConfig.model_validate(tomllib.loads(path.read_text(encoding="utf-8")))
