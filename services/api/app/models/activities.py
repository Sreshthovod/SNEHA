from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CreatedAtMixin, IdMixin, TimestampMixin
from app.db.types import UTCDateTime, str_enum
from app.models.enums import (
    ActivityType,
    Engagement,
    RecommendationAction,
    RecordSource,
    SessionEndReason,
    SessionStatus,
)


class ActivityDefinition(IdMixin, TimestampMixin, Base):
    """Catalog entry for a cognitive activity.

    Content packs ship with the app; this table is the index.
    """

    __tablename__ = "activity_definitions"
    __table_args__ = (
        CheckConstraint("min_difficulty >= 1 AND max_difficulty <= 10", name="difficulty_range"),
        CheckConstraint("min_difficulty <= max_difficulty", name="difficulty_order"),
    )

    slug: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    activity_type: Mapped[ActivityType] = mapped_column(
        str_enum(ActivityType, "activity_type"), nullable=False
    )
    cognitive_domains: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    min_difficulty: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    max_difficulty: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    default_duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    supports_offline: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    uses_memory_bank: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class ActivitySession(IdMixin, TimestampMixin, Base):
    """One sitting of activities. IDs may be generated on the device while offline."""

    __tablename__ = "activity_sessions"
    __table_args__ = (
        CheckConstraint("ended_at IS NULL OR ended_at >= started_at", name="end_after_start"),
        Index("ix_activity_sessions_patient_started", "patient_id", "started_at"),
    )

    patient_id: Mapped[str] = mapped_column(
        ForeignKey("patient_profiles.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[SessionStatus] = mapped_column(
        str_enum(SessionStatus, "session_status"), nullable=False
    )
    end_reason: Mapped[SessionEndReason | None] = mapped_column(
        str_enum(SessionEndReason, "session_end_reason")
    )
    source: Mapped[RecordSource] = mapped_column(
        str_enum(RecordSource, "record_source"), nullable=False
    )
    device_install_id: Mapped[str | None] = mapped_column(String(36))
    started_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    created_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))


class ActivityResult(IdMixin, TimestampMixin, Base):
    """Outcome of one activity within a session. Immutable once written (idempotent by ID)."""

    __tablename__ = "activity_results"
    __table_args__ = (
        CheckConstraint("score IS NULL OR (score >= 0 AND score <= 1)", name="score_range"),
        CheckConstraint("difficulty_level BETWEEN 1 AND 10", name="difficulty_range"),
        CheckConstraint("correct_count >= 0 AND attempt_count >= 0", name="counts_non_negative"),
        CheckConstraint("correct_count <= attempt_count", name="correct_le_attempts"),
        CheckConstraint("hint_count >= 0", name="hints_non_negative"),
        CheckConstraint("duration_ms >= 0", name="duration_non_negative"),
        CheckConstraint("completed_at >= started_at", name="completed_after_start"),
        Index("ix_activity_results_patient_completed", "patient_id", "completed_at"),
    )

    session_id: Mapped[str] = mapped_column(
        ForeignKey("activity_sessions.id", ondelete="CASCADE"), index=True, nullable=False
    )
    patient_id: Mapped[str] = mapped_column(
        ForeignKey("patient_profiles.id", ondelete="CASCADE"), nullable=False
    )
    activity_id: Mapped[str] = mapped_column(
        ForeignKey("activity_definitions.id", ondelete="RESTRICT"), nullable=False
    )
    activity_version: Mapped[int] = mapped_column(Integer, nullable=False)
    difficulty_level: Mapped[int] = mapped_column(Integer, nullable=False)
    started_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    completed_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    score: Mapped[float | None] = mapped_column(Float)
    correct_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    hint_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    abandoned: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Small, schema-validated activity-specific metrics (see schemas/activities.py).
    metrics: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    # Explicit feedback. NULL engagement = not asked/not answered (never treated as negative).
    engagement: Mapped[Engagement | None] = mapped_column(str_enum(Engagement, "engagement"))
    fatigue_reported: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    recommendation_id: Mapped[str | None] = mapped_column(
        ForeignKey("activity_recommendations.id", ondelete="SET NULL")
    )


class PersonalizationState(IdMixin, TimestampMixin, Base):
    """Per-patient, per-activity adaptive-difficulty state. Computed by the rules engine on the
    device (offline) and mirrored here via sync; last write wins by `state_updated_at`."""

    __tablename__ = "personalization_states"
    __table_args__ = (
        CheckConstraint("current_difficulty BETWEEN 1 AND 10", name="difficulty_range"),
        Index(
            "uq_personalization_states_patient_activity",
            "patient_id",
            "activity_id",
            unique=True,
        ),
    )

    patient_id: Mapped[str] = mapped_column(
        ForeignKey("patient_profiles.id", ondelete="CASCADE"), nullable=False
    )
    activity_id: Mapped[str] = mapped_column(
        ForeignKey("activity_definitions.id", ondelete="CASCADE"), nullable=False
    )
    current_difficulty: Mapped[int] = mapped_column(Integer, nullable=False)
    rules_version: Mapped[str] = mapped_column(String(20), nullable=False)
    state: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    state_updated_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)


class ActivityRecommendation(IdMixin, CreatedAtMixin, Base):
    """Every recommendation the personalization engine makes, with its full explanation."""

    __tablename__ = "activity_recommendations"
    __table_args__ = (
        Index("ix_activity_recommendations_patient_created", "patient_id", "created_at"),
    )

    patient_id: Mapped[str] = mapped_column(
        ForeignKey("patient_profiles.id", ondelete="CASCADE"), nullable=False
    )
    session_id: Mapped[str | None] = mapped_column(
        ForeignKey("activity_sessions.id", ondelete="SET NULL")
    )
    action: Mapped[RecommendationAction] = mapped_column(
        str_enum(RecommendationAction, "recommendation_action"), nullable=False
    )
    activity_id: Mapped[str | None] = mapped_column(
        ForeignKey("activity_definitions.id", ondelete="SET NULL")
    )
    difficulty: Mapped[int | None] = mapped_column(Integer)
    reason_codes: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    supporting: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    content_refs: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    hints_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    algorithm_version: Mapped[str] = mapped_column(String(20), nullable=False)
    config_version: Mapped[str] = mapped_column(String(20), nullable=False)
    fallback_used: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    fallback_reason: Mapped[str | None] = mapped_column(String(64))
    request_context: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
