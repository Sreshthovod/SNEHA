from datetime import datetime
from typing import Any

from sqlalchemy import JSON, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.types import BigIntPK, UTCDateTime, str_enum
from app.models.enums import SyncEntity, SyncMutationStatus, SyncOperation


class SyncChange(Base):
    """Outbound change log: every server-side change a device must pull, in commit order.

    Devices pull with `since=<last seq>`; `seq` is monotonic so no change is skipped
    regardless of clock skew. Deletes appear here as tombstones (no payload).
    """

    __tablename__ = "sync_changes"
    __table_args__ = (Index("ix_sync_changes_patient_seq", "patient_id", "seq"),)

    seq: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    patient_id: Mapped[str | None] = mapped_column(
        ForeignKey("patient_profiles.id", ondelete="CASCADE")
    )  # NULL = global (e.g. activity catalog)
    entity_type: Mapped[SyncEntity] = mapped_column(
        str_enum(SyncEntity, "sync_entity"), nullable=False
    )
    entity_id: Mapped[str] = mapped_column(String(36), nullable=False)
    operation: Mapped[SyncOperation] = mapped_column(
        str_enum(SyncOperation, "sync_operation"), nullable=False
    )
    changed_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)


class SyncMutation(Base):
    """Inbound receipt for each device mutation, keyed by the client's mutation ID.

    Replaying the same mutation (e.g. after a dropped response) returns the stored
    outcome instead of applying it twice.
    """

    __tablename__ = "sync_mutations"
    __table_args__ = (Index("ix_sync_mutations_patient_received", "patient_id", "received_at"),)

    mutation_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    patient_id: Mapped[str] = mapped_column(
        ForeignKey("patient_profiles.id", ondelete="CASCADE"), nullable=False
    )
    device_install_id: Mapped[str] = mapped_column(String(36), nullable=False)
    entity_type: Mapped[SyncEntity] = mapped_column(
        str_enum(SyncEntity, "sync_entity"), nullable=False
    )
    entity_id: Mapped[str] = mapped_column(String(36), nullable=False)
    status: Mapped[SyncMutationStatus] = mapped_column(
        str_enum(SyncMutationStatus, "sync_mutation_status"), nullable=False
    )
    detail: Mapped[str | None] = mapped_column(String(300))
    received_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)


class AuditEvent(Base):
    """Security-relevant actions. Never stores transcripts, memory content, passwords or tokens."""

    __tablename__ = "audit_events"
    __table_args__ = (
        Index("ix_audit_events_occurred", "occurred_at"),
        Index("ix_audit_events_patient", "patient_id", "occurred_at"),
    )

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    actor_user_id: Mapped[str | None] = mapped_column(String(36))
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    outcome: Mapped[str] = mapped_column(String(16), nullable=False)
    patient_id: Mapped[str | None] = mapped_column(String(36))
    target_type: Mapped[str | None] = mapped_column(String(40))
    target_id: Mapped[str | None] = mapped_column(String(36))
    request_id: Mapped[str | None] = mapped_column(String(64))
    # Small, whitelisted, non-sensitive metadata only (see services/audit.py).
    details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
