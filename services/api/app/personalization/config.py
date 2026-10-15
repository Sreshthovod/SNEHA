"""Load and validate the personalization and activity-spec configuration files.

Paths can be overridden with SNEHA_PERSONALIZATION_CONFIG and SNEHA_ACTIVITY_SPECS.
Invalid configuration fails loudly at load time rather than producing odd recommendations.
"""

import os
import tomllib
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

CONFIG_DIR = Path(__file__).resolve().parents[2] / "config"


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class DifficultyRules(_Strict):
    success_score: float = Field(ge=0, le=1)
    max_hints_for_success: int = Field(ge=0)
    slow_response_factor: float = Field(gt=1)
    struggle_score: float = Field(ge=0, le=1)
    increase_after_successes: int = Field(ge=1)
    decrease_after_struggles: int = Field(ge=1)
    min_results_between_changes: int = Field(ge=1)
    hints_after_struggles: int = Field(ge=1)
    history_window: int = Field(ge=5, le=500)

    @model_validator(mode="after")
    def _ordered(self) -> "DifficultyRules":
        if self.struggle_score >= self.success_score:
            raise ValueError("struggle_score must be below success_score")
        return self


class SelectionRules(_Strict):
    recent_window: int = Field(ge=1)
    repeat_last_penalty: int = Field(ge=0)
    repeat_recent_penalty: int = Field(ge=0)
    interest_match_bonus: int = Field(ge=0)
    interest_bonus_cap: int = Field(ge=0)
    context_match_bonus: int = Field(ge=0)
    enjoyed_bonus: int = Field(ge=0)
    not_enjoyed_penalty: int = Field(ge=0)
    interruption_penalty: int = Field(ge=0)
    familiar_bonus: int = Field(ge=0)
    low_engagement_window: int = Field(ge=1)
    low_engagement_threshold: int = Field(ge=1)
    cold_start_order: list[str]


class FatigueRules(_Strict):
    feedback_window_hours: float = Field(gt=0)
    observation_window_hours: float = Field(gt=0)
    low_effort_slugs: list[str] = Field(min_length=1)
    break_minutes: int = Field(ge=1)


class MemoryRules(_Strict):
    min_photo_memories: int = Field(ge=1)
    min_person_photo_memories: int = Field(ge=1)
    min_story_memories: int = Field(ge=1)
    min_routine_items: int = Field(ge=2)
    items_per_activity: int = Field(ge=1, le=50)
    recent_use_recommendations: int = Field(ge=0)


class PersonalizationConfig(_Strict):
    config_version: str = Field(min_length=1, max_length=20)
    difficulty: DifficultyRules
    selection: SelectionRules
    fatigue: FatigueRules
    memory: MemoryRules
    activity_interest_tags: dict[str, list[str]] = Field(default_factory=dict)
    content_languages: dict[str, list[str]] = Field(default_factory=dict)


class LevelSpec(_Strict):
    model_config = ConfigDict(extra="allow", frozen=True)
    level: int = Field(ge=1, le=10)

    @property
    def parameters(self) -> dict[str, Any]:
        return {k: v for k, v in (self.model_extra or {}).items()}


class ActivitySpec(_Strict):
    instructions: str
    hint: str
    evaluation: str
    stop: str
    accessibility: str
    levels: list[LevelSpec] = Field(min_length=1)

    def level(self, difficulty: int) -> LevelSpec:
        for spec in self.levels:
            if spec.level == difficulty:
                return spec
        raise KeyError(difficulty)


def _load(path: Path) -> dict[str, Any]:
    try:
        return tomllib.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise RuntimeError(f"Configuration file not found: {path}") from error


@lru_cache
def get_personalization_config() -> PersonalizationConfig:
    path = Path(os.environ.get("SNEHA_PERSONALIZATION_CONFIG", CONFIG_DIR / "personalization.toml"))
    return PersonalizationConfig.model_validate(_load(path))


@lru_cache
def get_activity_specs() -> dict[str, ActivitySpec]:
    path = Path(os.environ.get("SNEHA_ACTIVITY_SPECS", CONFIG_DIR / "activities.toml"))
    return {slug: ActivitySpec.model_validate(raw) for slug, raw in _load(path).items()}
