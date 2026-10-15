"""Append entries to the outbound sync change log (see models/sync.py)."""

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.time import utc_now
from app.models.enums import MemoryStatus, SyncEntity, SyncOperation
from app.models.memories import MemoryItem
from app.models.sync import SyncChange

# Arbitrary constant identifying the change-log lock.
_CHANGE_LOG_LOCK_KEY = 0x5E4A_0001


def _serialise_change_log(db: Session) -> None:
    """Make `seq` order equal commit order.

    Devices pull `seq > since`. If two PostgreSQL transactions took seq 6 and 7 and 7
    committed first, a device could pull 7, advance its cursor and never see 6. A
    transaction-scoped advisory lock makes writers take seq values in commit order.
    SQLite already allows only one writer at a time.
    """
    if db.get_bind().dialect.name == "postgresql":
        db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": _CHANGE_LOG_LOCK_KEY})


def log_change(
    db: Session,
    entity_type: SyncEntity,
    entity_id: str,
    operation: SyncOperation,
    patient_id: str | None,
) -> None:
    _serialise_change_log(db)
    db.add(
        SyncChange(
            patient_id=patient_id,
            entity_type=entity_type,
            entity_id=entity_id,
            operation=operation,
            changed_at=utc_now(),
        )
    )


def log_memory_change(db: Session, memory: MemoryItem, *, deleted: bool = False) -> None:
    """Devices only ever receive APPROVED memories; anything else is sent as a delete."""
    visible = not deleted and memory.status is MemoryStatus.APPROVED
    log_change(
        db,
        SyncEntity.MEMORY_ITEM,
        memory.id,
        SyncOperation.UPSERT if visible else SyncOperation.DELETE,
        memory.patient_id,
    )
