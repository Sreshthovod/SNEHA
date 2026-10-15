from datetime import datetime
from typing import Annotated

from pydantic import Field, StringConstraints

from app.models.enums import MemoryKind, MemoryRelationType, MemoryStatus, RecordSource
from app.schemas.base import RecordId, RequestModel, ResponseModel, ShortText, Tag

Description = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)
]
Note = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]


class MemoryCreate(RequestModel):
    id: RecordId | None = Field(default=None, description="Optional client-generated UUID.")
    kind: MemoryKind
    title: ShortText
    description: Description | None = None
    approx_year: int | None = Field(default=None, ge=1900, le=2100)
    tags: list[Tag] = Field(default_factory=list, max_length=20)
    media_file_id: RecordId | None = None


class MemoryCorrection(RequestModel):
    """Correct a memory. `expected_version` must match the current version (409 otherwise)."""

    expected_version: int = Field(ge=1)
    kind: MemoryKind | None = None
    title: ShortText | None = None
    description: Description | None = None
    approx_year: int | None = Field(default=None, ge=1900, le=2100)
    tags: list[Tag] | None = Field(default=None, max_length=20)
    media_file_id: RecordId | None = None
    correction_note: Note | None = None


class MemoryReview(RequestModel):
    expected_version: int = Field(ge=1)
    note: Note | None = None


class MemoryOut(ResponseModel):
    id: str
    patient_id: str
    kind: MemoryKind
    title: str
    description: str | None
    approx_year: int | None
    tags: list[str]
    media_file_id: str | None
    status: MemoryStatus
    source: RecordSource
    version: int
    created_by_id: str | None
    reviewed_by_id: str | None
    reviewed_at: datetime | None
    review_note: str | None
    created_at: datetime
    updated_at: datetime


class MemoryRelationshipCreate(RequestModel):
    from_memory_id: RecordId
    to_memory_id: RecordId
    relation_type: MemoryRelationType


class MemoryRelationshipOut(ResponseModel):
    id: str
    from_memory_id: str
    to_memory_id: str
    relation_type: MemoryRelationType
    created_at: datetime
