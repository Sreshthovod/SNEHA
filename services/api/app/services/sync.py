"""Device <-> server synchronisation.

The patient device and the server each have their own database (SQLite on the
device, PostgreSQL on the server). Nothing synchronises automatically: the device
explicitly PUSHES its outbox of mutations and PULLS the server change log.

Ownership rules (who may write what) — see docs/offline-strategy.md:
- Device-owned (pushed): activity sessions, activity results, conversation metadata,
  personalization state.
- Server-owned (pulled): approved memory items, memory relationships, routine items,
  activity catalog, and personalization state (echoed back so a reinstalled
  device can recover it).

Every pushed mutation carries a client `mutation_id`. The server stores a receipt
per mutation, so replays return the original outcome instead of re-applying.
"""

from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.time import utc_now
from app.models.activities import (
    ActivityDefinition,
    ActivitySession,
    PersonalizationState,
)
from app.models.care import ConversationRecord, RoutineItem
from app.models.enums import (
    MemoryStatus,
    RecordSource,
    SessionEndReason,
    SyncEntity,
    SyncMutationStatus,
    SyncOperation,
)
from app.models.memories import MemoryItem, MemoryRelationship
from app.models.sync import SyncChange, SyncMutation
from app.schemas.activities import ActivityDefinitionOut, ResultCreate
from app.schemas.care import RoutineOut
from app.schemas.memories import MemoryOut, MemoryRelationshipOut
from app.schemas.sync import (
    ConversationMutation,
    MutationResult,
    PersonalizationMutation,
    ResultMutation,
    SessionMutation,
    SyncChangeOut,
)
from app.services import activities
from app.services.changes import log_change

PULL_PAGE_SIZE = 500


class _Outcome(Exception):
    def __init__(self, status: SyncMutationStatus, detail: str | None = None) -> None:
        self.status = status
        self.detail = detail


def _apply_session(db: Session, patient_id: str, m: SessionMutation, user_id: str, device: str):
    data = m.data
    session, created = activities.create_session(
        db,
        patient_id=patient_id,
        session_id=data.id,
        started_at=data.started_at,
        source=RecordSource.DEVICE,
        device_install_id=device,
        created_by_id=user_id,
    )
    changed = created
    if data.ended_at is not None:
        reason = data.end_reason or SessionEndReason.COMPLETED
        changed = (
            activities.finish_session(session, ended_at=data.ended_at, end_reason=reason) or changed
        )
    if not changed:
        raise _Outcome(SyncMutationStatus.DUPLICATE, "Session already up to date")


def _apply_result(db: Session, patient_id: str, m: ResultMutation):
    session = db.get(ActivitySession, m.data.session_id)
    if session is None or session.patient_id != patient_id:
        raise _Outcome(SyncMutationStatus.REJECTED, "Unknown session; push the session first")
    payload = ResultCreate.model_validate(m.data.model_dump(exclude={"session_id"}))
    _, created = activities.submit_result(db, session, payload)
    if not created:
        raise _Outcome(SyncMutationStatus.DUPLICATE, "Result already stored")


def _apply_conversation(db: Session, patient_id: str, m: ConversationMutation):
    data = m.data
    existing = db.get(ConversationRecord, data.id)
    if existing is not None:
        if existing.patient_id != patient_id:
            raise _Outcome(SyncMutationStatus.REJECTED, "ID already in use")
        if data.ended_at is not None and existing.ended_at is None:
            existing.ended_at = data.ended_at
            existing.turn_count = data.turn_count
            existing.intents = list(data.intents)
            existing.fallback_used = data.fallback_used
            existing.error_code = data.error_code
            return
        raise _Outcome(SyncMutationStatus.DUPLICATE, "Conversation already stored")
    if data.session_id is not None:
        session = db.get(ActivitySession, data.session_id)
        if session is None or session.patient_id != patient_id:
            raise _Outcome(SyncMutationStatus.REJECTED, "Unknown session")
    db.add(
        ConversationRecord(
            id=data.id,
            patient_id=patient_id,
            session_id=data.session_id,
            started_at=data.started_at,
            ended_at=data.ended_at,
            language=data.language,
            provider=data.provider,
            fallback_used=data.fallback_used,
            turn_count=data.turn_count,
            intents=list(data.intents),
            error_code=data.error_code,
        )
    )


def _apply_personalization(db: Session, patient_id: str, m: PersonalizationMutation):
    data = m.data
    if db.get(ActivityDefinition, data.activity_id) is None:
        raise _Outcome(SyncMutationStatus.REJECTED, "Unknown activity")
    state = db.scalar(
        select(PersonalizationState).where(
            PersonalizationState.patient_id == patient_id,
            PersonalizationState.activity_id == data.activity_id,
        )
    )
    if state is None:
        state = PersonalizationState(patient_id=patient_id, activity_id=data.activity_id)
        db.add(state)
    elif data.state_updated_at <= state.state_updated_at:
        # Last-writer-wins by the device's state timestamp; older pushes lose.
        raise _Outcome(SyncMutationStatus.CONFLICT, "Server has newer personalization state")
    state.current_difficulty = data.current_difficulty
    state.rules_version = data.rules_version
    state.state = dict(data.state)
    state.state_updated_at = data.state_updated_at
    db.flush()
    log_change(db, SyncEntity.PERSONALIZATION_STATE, state.id, SyncOperation.UPSERT, patient_id)


def _entity_id(m: Any) -> str:
    if isinstance(m, PersonalizationMutation):
        return m.data.activity_id
    return m.data.id


def push(
    db: Session, *, patient_id: str, user_id: str, device_install_id: str, mutations: list[Any]
) -> list[MutationResult]:
    results: list[MutationResult] = []
    for m in mutations:
        entity_id = _entity_id(m)
        receipt = db.get(SyncMutation, m.mutation_id)
        if receipt is not None:
            if receipt.patient_id != patient_id:
                status, detail = SyncMutationStatus.REJECTED, "mutation_id already used"
            else:
                status, detail = SyncMutationStatus.DUPLICATE, "Mutation already processed"
            results.append(
                MutationResult(
                    mutation_id=m.mutation_id,
                    entity_type=m.entity_type,
                    entity_id=entity_id,
                    status=status,
                    detail=detail,
                )
            )
            continue

        status, detail = SyncMutationStatus.APPLIED, None
        savepoint = db.begin_nested()
        try:
            match m:
                case SessionMutation():
                    _apply_session(db, patient_id, m, user_id, device_install_id)
                case ResultMutation():
                    _apply_result(db, patient_id, m)
                case ConversationMutation():
                    _apply_conversation(db, patient_id, m)
                case PersonalizationMutation():
                    _apply_personalization(db, patient_id, m)
            db.flush()
            savepoint.commit()
        except _Outcome as outcome:
            savepoint.rollback()
            status, detail = outcome.status, outcome.detail
        except AppError as error:
            savepoint.rollback()
            status = (
                SyncMutationStatus.CONFLICT
                if error.status_code == 409
                else SyncMutationStatus.REJECTED
            )
            detail = error.message
        except IntegrityError:
            savepoint.rollback()
            status, detail = SyncMutationStatus.REJECTED, "Violates a data constraint"

        db.add(
            SyncMutation(
                mutation_id=m.mutation_id,
                patient_id=patient_id,
                device_install_id=device_install_id,
                entity_type=m.entity_type,
                entity_id=entity_id,
                status=status,
                detail=detail,
                received_at=utc_now(),
            )
        )
        results.append(
            MutationResult(
                mutation_id=m.mutation_id,
                entity_type=m.entity_type,
                entity_id=entity_id,
                status=status,
                detail=detail,
            )
        )
    db.commit()
    return results


_PULL_MODELS: dict[SyncEntity, tuple[type, type]] = {
    SyncEntity.MEMORY_ITEM: (MemoryItem, MemoryOut),
    SyncEntity.MEMORY_RELATIONSHIP: (MemoryRelationship, MemoryRelationshipOut),
    SyncEntity.ROUTINE_ITEM: (RoutineItem, RoutineOut),
    SyncEntity.ACTIVITY_DEFINITION: (ActivityDefinition, ActivityDefinitionOut),
}


def _payload(db: Session, change: SyncChange) -> dict[str, Any] | None:
    if change.operation is SyncOperation.DELETE:
        return None
    if change.entity_type is SyncEntity.PERSONALIZATION_STATE:
        state = db.get(PersonalizationState, change.entity_id)
        if state is None:
            return None
        return {
            "activity_id": state.activity_id,
            "current_difficulty": state.current_difficulty,
            "rules_version": state.rules_version,
            "state": state.state,
            "state_updated_at": state.state_updated_at.isoformat(),
        }
    model, schema = _PULL_MODELS[change.entity_type]
    row = db.get(model, change.entity_id)
    if row is None:
        return None
    if isinstance(row, MemoryItem) and row.status is not MemoryStatus.APPROVED:
        return None
    return schema.model_validate(row).model_dump(mode="json")


def pull(
    db: Session, *, patient_id: str, since: int, limit: int = PULL_PAGE_SIZE
) -> tuple[list[SyncChangeOut], int, bool]:
    rows = list(
        db.scalars(
            select(SyncChange)
            .where(
                SyncChange.seq > since,
                or_(SyncChange.patient_id == patient_id, SyncChange.patient_id.is_(None)),
            )
            .order_by(SyncChange.seq)
            .limit(limit + 1)
        )
    )
    has_more = len(rows) > limit
    rows = rows[:limit]
    changes: list[SyncChangeOut] = []
    for change in rows:
        data = _payload(db, change)
        operation = change.operation if data is not None else SyncOperation.DELETE
        changes.append(
            SyncChangeOut(
                seq=change.seq,
                entity_type=change.entity_type,
                entity_id=change.entity_id,
                operation=operation,
                changed_at=change.changed_at,
                data=data,
            )
        )
    next_since = rows[-1].seq if rows else since
    return changes, next_since, has_more
