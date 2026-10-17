"""Memory Bank: creation, caregiver approval, correction and deletion.

- Caregivers and the patient may PROPOSE memories (status pending_approval).
- Managing caregivers create memories already approved, and approve/reject/correct/delete.
- The patient (device) only ever sees approved memories.
- Clinicians have no access to Memory Bank content.
"""

from typing import Annotated

from fastapi import APIRouter, Query, Request, Response, status
from sqlalchemy import or_, select, true

from app.api.deps import DbSessionDep, PrincipalDep, SettingsDep, patient_access
from app.core.errors import AppError, conflict, not_found
from app.core.time import utc_now
from app.models.enums import (
    ConsentType,
    FilePurpose,
    MemoryKind,
    MemoryStatus,
    RecordSource,
    SyncEntity,
    SyncOperation,
    UserRole,
)
from app.models.files import StoredFile
from app.models.memories import MemoryItem, MemoryRelationship
from app.schemas.common import ErrorResponse
from app.schemas.memories import (
    MemoryCorrection,
    MemoryCreate,
    MemoryOut,
    MemoryRelationshipCreate,
    MemoryRelationshipOut,
    MemoryReview,
)
from app.services import audit
from app.services.access import PatientAccess, Permission, has_consent
from app.services.changes import log_change, log_memory_change
from app.services.files import FileStore

router = APIRouter(prefix="/patients/{patient_id}", tags=["memories"])

_ERRORS = {
    401: {"model": ErrorResponse},
    403: {"model": ErrorResponse},
    404: {"model": ErrorResponse},
    409: {"model": ErrorResponse},
    422: {"model": ErrorResponse},
}


def _get_memory(db, access: PatientAccess, memory_id: str) -> MemoryItem:
    memory = db.get(MemoryItem, memory_id)
    if memory is None or memory.patient_id != access.patient.id:
        raise not_found("Memory")
    if not access.can(Permission.MANAGE_MEMORIES) and memory.status is not MemoryStatus.APPROVED:
        raise not_found("Memory")
    return memory


def _check_media(
    db, patient_id: str, media_file_id: str | None, *, memory_id: str | None = None
) -> None:
    if media_file_id is None:
        return
    file = db.get(StoredFile, media_file_id)
    if (
        file is None
        or file.patient_id != patient_id
        or file.deleted_at is not None
        or file.purpose is not FilePurpose.MEMORY_MEDIA
    ):
        raise AppError(
            422, "invalid_media", "media_file_id does not refer to this patient's media."
        )
    # A photo belongs to one memory: deleting that memory deletes the photo.
    other = db.scalar(
        select(MemoryItem.id).where(
            MemoryItem.media_file_id == media_file_id,
            MemoryItem.id != memory_id if memory_id else true(),
        )
    )
    if other is not None:
        raise AppError(422, "invalid_media", "This photo is already used by another memory.")


def _require_version(memory: MemoryItem, expected: int) -> None:
    if memory.version != expected:
        raise conflict(
            "version_conflict",
            f"This memory was changed by someone else (current version {memory.version}). "
            "Reload and try again.",
        )


@router.get("/memories", response_model=list[MemoryOut], responses=_ERRORS)
def list_memories(
    db: DbSessionDep,
    status_filter: Annotated[MemoryStatus | None, Query(alias="status")] = None,
    access: PatientAccess = patient_access(Permission.VIEW_MEMORIES),
) -> list[MemoryItem]:
    query = select(MemoryItem).where(MemoryItem.patient_id == access.patient.id)
    if not access.can(Permission.MANAGE_MEMORIES):
        query = query.where(MemoryItem.status == MemoryStatus.APPROVED)
    elif status_filter is not None:
        query = query.where(MemoryItem.status == status_filter)
    return list(db.scalars(query.order_by(MemoryItem.created_at.desc())))


@router.post(
    "/memories", response_model=MemoryOut, status_code=status.HTTP_201_CREATED, responses=_ERRORS
)
def create_memory(
    body: MemoryCreate,
    principal: PrincipalDep,
    db: DbSessionDep,
    request: Request,
    access: PatientAccess = patient_access(Permission.PROPOSE_MEMORY),
) -> MemoryItem:
    if not has_consent(db, access.patient.id, ConsentType.DATA_PROCESSING):
        raise AppError(409, "consent_required", "Data-processing consent is required first.")
    if body.id is not None and db.get(MemoryItem, body.id) is not None:
        raise conflict("id_conflict", "A memory with this ID already exists.")
    _check_media(db, access.patient.id, body.media_file_id)

    approved = access.can(Permission.MANAGE_MEMORIES)
    now = utc_now()
    memory = MemoryItem(
        patient_id=access.patient.id,
        **body.model_dump(exclude={"id"}),
        status=MemoryStatus.APPROVED if approved else MemoryStatus.PENDING_APPROVAL,
        source=RecordSource.DEVICE
        if principal.role is UserRole.PATIENT
        else RecordSource.DASHBOARD,
        created_by_id=principal.id,
        reviewed_by_id=principal.id if approved else None,
        reviewed_at=now if approved else None,
    )
    if body.id is not None:
        memory.id = body.id
    db.add(memory)
    db.flush()
    log_memory_change(db, memory)
    audit.record(
        db,
        "memory.create",
        actor_id=principal.id,
        patient_id=access.patient.id,
        target_type="memory",
        target_id=memory.id,
        request=request,
        details={"status": memory.status.value, "kind": memory.kind.value},
    )
    db.commit()
    return memory


@router.get("/memories/{memory_id}", response_model=MemoryOut, responses=_ERRORS)
def get_memory(
    memory_id: str,
    db: DbSessionDep,
    access: PatientAccess = patient_access(Permission.VIEW_MEMORIES),
) -> MemoryItem:
    return _get_memory(db, access, memory_id)


@router.patch("/memories/{memory_id}", response_model=MemoryOut, responses=_ERRORS)
def correct_memory(
    memory_id: str,
    body: MemoryCorrection,
    principal: PrincipalDep,
    db: DbSessionDep,
    request: Request,
    settings: SettingsDep,
    access: PatientAccess = patient_access(Permission.MANAGE_MEMORIES),
) -> MemoryItem:
    memory = _get_memory(db, access, memory_id)
    _require_version(memory, body.expected_version)
    changes = body.model_dump(exclude_unset=True, exclude={"expected_version", "correction_note"})
    for required in ("kind", "title", "tags"):
        if required in changes and changes[required] is None:
            raise AppError(422, "validation_error", f"{required} cannot be null.")
    replaced = None
    if "media_file_id" in changes:
        _check_media(db, access.patient.id, changes["media_file_id"], memory_id=memory.id)
        if memory.media_file_id and memory.media_file_id != changes["media_file_id"]:
            # A replaced or removed photo is erased, not just unlinked.
            replaced = db.get(StoredFile, memory.media_file_id)
            if replaced is not None and replaced.deleted_at is None:
                replaced.deleted_at = utc_now()
            else:
                replaced = None
    for field, value in changes.items():
        setattr(memory, field, value)
    if memory.kind is not MemoryKind.PERSON:
        if changes.get("relationship"):
            raise AppError(422, "validation_error", "relationship is only for person memories.")
        memory.relationship = None  # a memory that stops being a person loses it
    memory.version += 1
    if body.correction_note:
        memory.review_note = body.correction_note
    log_memory_change(db, memory)
    audit.record(
        db,
        "memory.correct",
        actor_id=principal.id,
        patient_id=access.patient.id,
        target_type="memory",
        target_id=memory.id,
        request=request,
        details={"version": memory.version},
    )
    db.commit()
    if replaced is not None:
        FileStore(settings.media_root).delete(replaced.storage_key)
    return memory


def _review(
    memory_id: str,
    body: MemoryReview,
    new_status: MemoryStatus,
    principal,
    db,
    request: Request,
    access: PatientAccess,
) -> MemoryItem:
    memory = _get_memory(db, access, memory_id)
    _require_version(memory, body.expected_version)
    if memory.status is not MemoryStatus.PENDING_APPROVAL:
        raise conflict("not_pending", f"This memory is already {memory.status.value}.")
    memory.status = new_status
    memory.reviewed_by_id = principal.id
    memory.reviewed_at = utc_now()
    memory.review_note = body.note
    memory.version += 1
    log_memory_change(db, memory)
    audit.record(
        db,
        f"memory.{'approve' if new_status is MemoryStatus.APPROVED else 'reject'}",
        actor_id=principal.id,
        patient_id=access.patient.id,
        target_type="memory",
        target_id=memory.id,
        request=request,
    )
    db.commit()
    return memory


@router.post("/memories/{memory_id}/approve", response_model=MemoryOut, responses=_ERRORS)
def approve_memory(
    memory_id: str,
    body: MemoryReview,
    principal: PrincipalDep,
    db: DbSessionDep,
    request: Request,
    access: PatientAccess = patient_access(Permission.MANAGE_MEMORIES),
) -> MemoryItem:
    return _review(memory_id, body, MemoryStatus.APPROVED, principal, db, request, access)


@router.post("/memories/{memory_id}/reject", response_model=MemoryOut, responses=_ERRORS)
def reject_memory(
    memory_id: str,
    body: MemoryReview,
    principal: PrincipalDep,
    db: DbSessionDep,
    request: Request,
    access: PatientAccess = patient_access(Permission.MANAGE_MEMORIES),
) -> MemoryItem:
    return _review(memory_id, body, MemoryStatus.REJECTED, principal, db, request, access)


@router.delete("/memories/{memory_id}", status_code=status.HTTP_204_NO_CONTENT, responses=_ERRORS)
def delete_memory(
    memory_id: str,
    principal: PrincipalDep,
    db: DbSessionDep,
    settings: SettingsDep,
    request: Request,
    access: PatientAccess = patient_access(Permission.MANAGE_MEMORIES),
) -> Response:
    """Permanently delete a memory and its photo. Devices receive a tombstone on next sync."""
    memory = _get_memory(db, access, memory_id)
    media = db.get(StoredFile, memory.media_file_id) if memory.media_file_id else None
    for rel in db.scalars(
        select(MemoryRelationship).where(
            or_(
                MemoryRelationship.from_memory_id == memory.id,
                MemoryRelationship.to_memory_id == memory.id,
            )
        )
    ):
        log_change(
            db, SyncEntity.MEMORY_RELATIONSHIP, rel.id, SyncOperation.DELETE, memory.patient_id
        )
        db.delete(rel)
    db.flush()  # links first: no ORM relationship orders these deletes for us
    log_memory_change(db, memory, deleted=True)
    db.delete(memory)
    storage_key = None
    if media is not None and media.deleted_at is None:
        media.deleted_at = utc_now()
        storage_key = media.storage_key
    audit.record(
        db,
        "memory.delete",
        actor_id=principal.id,
        patient_id=access.patient.id,
        target_type="memory",
        target_id=memory_id,
        request=request,
    )
    db.commit()
    if storage_key:
        FileStore(settings.media_root).delete(storage_key)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------- relationships between memories ----------


@router.get("/memory-relationships", response_model=list[MemoryRelationshipOut], responses=_ERRORS)
def list_memory_relationships(
    db: DbSessionDep, access: PatientAccess = patient_access(Permission.VIEW_MEMORIES)
) -> list[MemoryRelationship]:
    query = select(MemoryRelationship).where(MemoryRelationship.patient_id == access.patient.id)
    if not access.can(Permission.MANAGE_MEMORIES):
        approved = select(MemoryItem.id).where(MemoryItem.status == MemoryStatus.APPROVED)
        query = query.where(
            MemoryRelationship.from_memory_id.in_(approved),
            MemoryRelationship.to_memory_id.in_(approved),
        )
    return list(db.scalars(query))


@router.post(
    "/memory-relationships",
    response_model=MemoryRelationshipOut,
    status_code=status.HTTP_201_CREATED,
    responses=_ERRORS,
)
def create_memory_relationship(
    body: MemoryRelationshipCreate,
    principal: PrincipalDep,
    db: DbSessionDep,
    request: Request,
    access: PatientAccess = patient_access(Permission.MANAGE_MEMORIES),
) -> MemoryRelationship:
    if body.from_memory_id == body.to_memory_id:
        raise AppError(422, "validation_error", "A memory cannot be linked to itself.")
    for mid in (body.from_memory_id, body.to_memory_id):
        _get_memory(db, access, mid)
    exists = db.scalar(
        select(MemoryRelationship.id).where(
            MemoryRelationship.from_memory_id == body.from_memory_id,
            MemoryRelationship.to_memory_id == body.to_memory_id,
            MemoryRelationship.relation_type == body.relation_type,
        )
    )
    if exists:
        raise conflict("duplicate_relationship", "These memories are already linked this way.")
    rel = MemoryRelationship(
        patient_id=access.patient.id, created_by_id=principal.id, **body.model_dump()
    )
    db.add(rel)
    db.flush()
    log_change(db, SyncEntity.MEMORY_RELATIONSHIP, rel.id, SyncOperation.UPSERT, access.patient.id)
    audit.record(
        db,
        "memory_relationship.create",
        actor_id=principal.id,
        patient_id=access.patient.id,
        target_type="memory_relationship",
        target_id=rel.id,
        request=request,
        details={"relation_type": body.relation_type.value},
    )
    db.commit()
    return rel


@router.delete(
    "/memory-relationships/{relationship_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=_ERRORS,
)
def delete_memory_relationship(
    relationship_id: str,
    principal: PrincipalDep,
    db: DbSessionDep,
    request: Request,
    access: PatientAccess = patient_access(Permission.MANAGE_MEMORIES),
) -> Response:
    rel = db.get(MemoryRelationship, relationship_id)
    if rel is None or rel.patient_id != access.patient.id:
        raise not_found("Memory relationship")
    log_change(db, SyncEntity.MEMORY_RELATIONSHIP, rel.id, SyncOperation.DELETE, access.patient.id)
    db.delete(rel)
    audit.record(
        db,
        "memory_relationship.delete",
        actor_id=principal.id,
        patient_id=access.patient.id,
        target_type="memory_relationship",
        target_id=relationship_id,
        request=request,
    )
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
