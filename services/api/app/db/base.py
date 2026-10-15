"""SQLAlchemy declarative base and shared column conventions."""

from datetime import datetime

from sqlalchemy import MetaData, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.core.ids import new_id
from app.core.time import utc_now
from app.db.types import UTCDateTime

# Deterministic constraint names keep Alembic migrations identical on SQLite and PostgreSQL.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class IdMixin:
    """UUID string primary key, assignable by the client for offline-created records."""

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)


class CreatedAtMixin:
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utc_now, nullable=False)


class TimestampMixin(CreatedAtMixin):
    """Timezone-aware audit timestamps, always stored in UTC."""

    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime, default=utc_now, onupdate=utc_now, nullable=False
    )
