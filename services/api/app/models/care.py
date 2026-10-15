from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, CheckConstraint, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CreatedAtMixin, IdMixin, TimestampMixin
from app.db.types import UTCDateTime, str_enum
from app.models.enums import (
    ConversationProviderUsed,
    Language,
    ObservationCategory,
    ObservationStatus,
    RecordSource,
    ReportStatus,
)


class RoutineItem(IdMixin, TimestampMixin, Base):
    """A recurring daily-routine reminder, in the patient's local time."""

    __tablename__ = "routine_items"
    __table_args__ = (
        # Bitmask Mon=1 … Sun=64; at least one day.
        CheckConstraint("days_of_week BETWEEN 1 AND 127", name="days_of_week"),
    )

    patient_id: Mapped[str] = mapped_column(
        ForeignKey("patient_profiles.id", ondelete="CASCADE"), index=True, nullable=False
    )
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    local_time: Mapped[str] = mapped_column(String(5), nullable=False)  # "HH:MM"
    days_of_week: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))


class CaregiverObservation(IdMixin, CreatedAtMixin, Base):
    """A caregiver's note about the patient's day. Descriptive only; never a diagnosis."""

    __tablename__ = "caregiver_observations"
    __table_args__ = (
        Index("ix_caregiver_observations_patient_observed", "patient_id", "observed_at"),
    )

    patient_id: Mapped[str] = mapped_column(
        ForeignKey("patient_profiles.id", ondelete="CASCADE"), nullable=False
    )
    author_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    observed_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    category: Mapped[ObservationCategory] = mapped_column(
        str_enum(ObservationCategory, "observation_category"), nullable=False
    )
    note: Mapped[str] = mapped_column(Text, nullable=False)
    # Workflow (Stage 6). Every step records who and when.
    source: Mapped[RecordSource] = mapped_column(
        str_enum(RecordSource, "record_source"), default=RecordSource.DASHBOARD, nullable=False
    )
    status: Mapped[ObservationStatus] = mapped_column(
        str_enum(ObservationStatus, "observation_status"),
        default=ObservationStatus.OPEN,
        nullable=False,
    )
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    updated_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    reviewed_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    reviewed_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    review_note: Mapped[str | None] = mapped_column(String(500))
    resolved_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    resolved_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    resolution_note: Mapped[str | None] = mapped_column(String(500))


class ObservationRevision(IdMixin, CreatedAtMixin, Base):
    """Snapshot of an observation's content BEFORE a correction (append-only history)."""

    __tablename__ = "observation_revisions"
    __table_args__ = (
        Index("ix_observation_revisions_observation_version", "observation_id", "version"),
    )

    observation_id: Mapped[str] = mapped_column(
        ForeignKey("caregiver_observations.id", ondelete="CASCADE"), nullable=False
    )
    patient_id: Mapped[str] = mapped_column(
        ForeignKey("patient_profiles.id", ondelete="CASCADE"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    observed_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    category: Mapped[ObservationCategory] = mapped_column(
        str_enum(ObservationCategory, "observation_category"), nullable=False
    )
    note: Mapped[str] = mapped_column(Text, nullable=False)
    corrected_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    correction_reason: Mapped[str | None] = mapped_column(String(500))


class ConversationRecord(IdMixin, CreatedAtMixin, Base):
    """Metadata about a conversation. Transcripts and audio are deliberately NOT stored."""

    __tablename__ = "conversation_records"
    __table_args__ = (
        CheckConstraint("turn_count >= 0", name="turns_non_negative"),
        Index("ix_conversation_records_patient_started", "patient_id", "started_at"),
    )

    patient_id: Mapped[str] = mapped_column(
        ForeignKey("patient_profiles.id", ondelete="CASCADE"), nullable=False
    )
    session_id: Mapped[str | None] = mapped_column(
        ForeignKey("activity_sessions.id", ondelete="SET NULL")
    )
    started_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    language: Mapped[Language] = mapped_column(str_enum(Language, "language"), nullable=False)
    provider: Mapped[ConversationProviderUsed] = mapped_column(
        str_enum(ConversationProviderUsed, "conversation_provider"), nullable=False
    )
    fallback_used: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    turn_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # Coarse intent labels only, e.g. ["greeting", "ask_time"].
    intents: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(64))
    extra: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class Report(IdMixin, TimestampMixin, Base):
    """Metadata for an 8–9 day summary report. The PDF itself is a StoredFile."""

    __tablename__ = "reports"
    __table_args__ = (CheckConstraint("period_end > period_start", name="period_order"),)

    patient_id: Mapped[str] = mapped_column(
        ForeignKey("patient_profiles.id", ondelete="CASCADE"), index=True, nullable=False
    )
    period_start: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    period_end: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    status: Mapped[ReportStatus] = mapped_column(
        str_enum(ReportStatus, "report_status"), nullable=False
    )
    requested_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    file_id: Mapped[str | None] = mapped_column(ForeignKey("stored_files.id", ondelete="SET NULL"))
    generated_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    error_message: Mapped[str | None] = mapped_column(String(500))
    # True when created by scripts/generate_due_reports.py rather than a person.
    automated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Versions of the analytics config/method used, for reproducibility.
    method_version: Mapped[str | None] = mapped_column(String(40))
