from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin, TimestampMixin
from app.db.types import UTCDateTime, str_enum
from app.models.enums import AuthSessionKind, UserRole


class User(IdMixin, TimestampMixin, Base):
    __tablename__ = "users"

    # Patient users created by device pairing have no email or password.
    email: Mapped[str | None] = mapped_column(String(254), unique=True)
    password_hash: Mapped[str | None] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    role: Mapped[UserRole] = mapped_column(str_enum(UserRole, "user_role"), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # Clinicians must be verified out of band (scripts/manage.py) before receiving grants.
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    failed_login_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    locked_until: Mapped[datetime | None] = mapped_column(UTCDateTime)


class AuthSession(IdMixin, TimestampMixin, Base):
    """An opaque bearer token. Only the SHA-256 of the token is stored."""

    __tablename__ = "auth_sessions"

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    kind: Mapped[AuthSessionKind] = mapped_column(
        str_enum(AuthSessionKind, "auth_session_kind"), nullable=False
    )
    device_name: Mapped[str | None] = mapped_column(String(80))
    # The code a patient device was paired with; it records which caregiver let it in.
    pairing_code_id: Mapped[str | None] = mapped_column(
        ForeignKey("device_pairing_codes.id", ondelete="SET NULL"), index=True
    )
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    last_used_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
