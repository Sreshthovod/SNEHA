from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CreatedAtMixin, IdMixin
from app.db.types import UTCDateTime, str_enum
from app.models.enums import FilePurpose


class StoredFile(IdMixin, CreatedAtMixin, Base):
    """A protected file (photo, PDF). Bytes live outside the web root under SNEHA_MEDIA_ROOT,
    named by random ID; they are only served through an authorised endpoint."""

    __tablename__ = "stored_files"
    __table_args__ = (CheckConstraint("size_bytes > 0", name="size_positive"),)

    patient_id: Mapped[str] = mapped_column(
        ForeignKey("patient_profiles.id", ondelete="CASCADE"), index=True, nullable=False
    )
    uploaded_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    purpose: Mapped[FilePurpose] = mapped_column(
        str_enum(FilePurpose, "file_purpose"), nullable=False
    )
    content_type: Mapped[str] = mapped_column(String(64), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
