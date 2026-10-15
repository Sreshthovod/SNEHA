from datetime import datetime

from sqlalchemy import JSON, CheckConstraint, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CreatedAtMixin, IdMixin, TimestampMixin
from app.db.types import UTCDateTime, str_enum
from app.models.enums import MemoryKind, MemoryRelationType, MemoryStatus, RecordSource


class MemoryItem(IdMixin, TimestampMixin, Base):
    """An entry in the patient's caregiver-approved Memory Bank.

    Only APPROVED items are ever shown to the patient or used by activities.
    Deletion is a hard delete (content and media are removed); the sync change log
    keeps only a tombstone with the ID.
    """

    __tablename__ = "memory_items"
    __table_args__ = (
        CheckConstraint("version >= 1", name="version_positive"),
        CheckConstraint("approx_year IS NULL OR approx_year BETWEEN 1900 AND 2100", name="year"),
    )

    patient_id: Mapped[str] = mapped_column(
        ForeignKey("patient_profiles.id", ondelete="CASCADE"), index=True, nullable=False
    )
    kind: Mapped[MemoryKind] = mapped_column(str_enum(MemoryKind, "memory_kind"), nullable=False)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    approx_year: Mapped[int | None] = mapped_column(Integer)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    media_file_id: Mapped[str | None] = mapped_column(
        ForeignKey("stored_files.id", ondelete="SET NULL")
    )
    status: Mapped[MemoryStatus] = mapped_column(
        str_enum(MemoryStatus, "memory_status"), nullable=False
    )
    source: Mapped[RecordSource] = mapped_column(
        str_enum(RecordSource, "record_source"), nullable=False
    )
    # Optimistic concurrency: corrections must send the version they edited.
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    reviewed_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    reviewed_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    review_note: Mapped[str | None] = mapped_column(String(500))


class MemoryRelationship(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "memory_relationships"
    __table_args__ = (
        UniqueConstraint("from_memory_id", "to_memory_id", "relation_type"),
        CheckConstraint("from_memory_id <> to_memory_id", name="no_self_link"),
    )

    patient_id: Mapped[str] = mapped_column(
        ForeignKey("patient_profiles.id", ondelete="CASCADE"), index=True, nullable=False
    )
    from_memory_id: Mapped[str] = mapped_column(
        ForeignKey("memory_items.id", ondelete="CASCADE"), nullable=False
    )
    to_memory_id: Mapped[str] = mapped_column(
        ForeignKey("memory_items.id", ondelete="CASCADE"), nullable=False
    )
    relation_type: Mapped[MemoryRelationType] = mapped_column(
        str_enum(MemoryRelationType, "memory_relation_type"), nullable=False
    )
    created_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
