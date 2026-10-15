"""Protected media: upload and authorised download."""

from typing import Annotated

from fastapi import APIRouter, File, Request, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select

from app.api.deps import DbSessionDep, PrincipalDep, SettingsDep, patient_access
from app.core.errors import AppError, not_found
from app.models.enums import FilePurpose, MemoryStatus
from app.models.files import StoredFile
from app.models.memories import MemoryItem
from app.schemas.care import FileOut
from app.schemas.common import ErrorResponse
from app.services import audit
from app.services.access import PatientAccess, Permission, authorize
from app.services.activities import require_data_consent
from app.services.files import FileStore

router = APIRouter(tags=["files"])

UPLOAD_PATH_SUFFIX = "/media"

_ERRORS = {
    401: {"model": ErrorResponse},
    403: {"model": ErrorResponse},
    404: {"model": ErrorResponse},
    413: {"model": ErrorResponse},
    415: {"model": ErrorResponse},
    422: {"model": ErrorResponse},
}


@router.post(
    "/patients/{patient_id}" + UPLOAD_PATH_SUFFIX,
    response_model=FileOut,
    status_code=status.HTTP_201_CREATED,
    responses=_ERRORS,
)
async def upload_media(
    file: Annotated[UploadFile, File(description="JPEG, PNG or WebP image")],
    principal: PrincipalDep,
    db: DbSessionDep,
    settings: SettingsDep,
    request: Request,
    access: PatientAccess = patient_access(Permission.UPLOAD_MEDIA),
) -> StoredFile:
    """Upload a photo for the Memory Bank. Type is detected from the bytes, not the filename."""
    require_data_consent(db, access.patient.id)
    store = FileStore(settings.media_root)
    storage_key, content_type, size, sha256 = await store.save_upload(
        file, settings.max_upload_bytes
    )
    stored = StoredFile(
        patient_id=access.patient.id,
        uploaded_by_id=principal.id,
        purpose=FilePurpose.MEMORY_MEDIA,
        content_type=content_type,
        size_bytes=size,
        sha256=sha256,
        storage_key=storage_key,
    )
    db.add(stored)
    db.flush()
    audit.record(
        db,
        "file.upload",
        actor_id=principal.id,
        patient_id=access.patient.id,
        target_type="file",
        target_id=stored.id,
        request=request,
        details={"content_type": content_type, "size_bytes": size},
    )
    try:
        db.commit()
    except Exception:
        store.delete(storage_key)
        raise
    return stored


@router.get(
    "/files/{file_id}/content",
    response_class=FileResponse,
    responses={200: {"content": {"image/*": {}, "application/pdf": {}}}, **_ERRORS},
)
def download_file(
    file_id: str,
    principal: PrincipalDep,
    db: DbSessionDep,
    settings: SettingsDep,
    request: Request,
) -> FileResponse:
    stored = db.get(StoredFile, file_id)
    if stored is None or stored.deleted_at is not None:
        raise not_found("File")

    needed = (
        Permission.VIEW_REPORTS
        if stored.purpose is FilePurpose.REPORT_PDF
        else Permission.VIEW_MEMORIES
    )
    access = authorize(db, principal.user, stored.patient_id, needed, request=request)
    if stored.purpose is FilePurpose.MEMORY_MEDIA and not access.can(Permission.MANAGE_MEMORIES):
        # Non-managers only see photos attached to approved memories.
        attached = db.scalar(
            select(MemoryItem.id).where(
                MemoryItem.media_file_id == stored.id, MemoryItem.status == MemoryStatus.APPROVED
            )
        )
        if attached is None:
            raise not_found("File")

    path = FileStore(settings.media_root).path_for(stored.storage_key)
    if not path.is_file():
        raise AppError(410, "file_missing", "This file is no longer available.")
    return FileResponse(
        path,
        media_type=stored.content_type,
        headers={
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
            "Content-Disposition": f'inline; filename="{stored.id}"',
            "Content-Security-Policy": "default-src 'none'",
        },
    )
