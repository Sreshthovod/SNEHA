from datetime import datetime

from sqlalchemy import BigInteger, Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CreatedAtMixin, IdMixin, TimestampMixin
from app.db.types import UTCDateTime, str_enum
from app.models.enums import AuthSessionKind, EmailTokenPurpose, UserRole


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
    # When the person proved they can read their email (migration 0016). Separate from
    # `is_verified`, which is the administrator's check of a clinician.
    email_verified_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    failed_login_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    locked_until: Mapped[datetime | None] = mapped_column(UTCDateTime)

    @property
    def email_verified(self) -> bool:
        return self.email_verified_at is not None


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
    # Patient devices (migration 0014): the highest change-log seq sent to this device and
    # when, so caregivers can see whether a fatigue note has reached the phone.
    last_pull_seq: Mapped[int | None] = mapped_column(BigInteger)
    last_pull_at: Mapped[datetime | None] = mapped_column(UTCDateTime)


class EmailToken(IdMixin, CreatedAtMixin, Base):
    """A single-use link sent by email (verify email, reset password).

    Only the SHA-256 of the token is stored. Issuing a new token for the same purpose
    retires the older ones.
    """

    __tablename__ = "email_tokens"

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    purpose: Mapped[EmailTokenPurpose] = mapped_column(
        str_enum(EmailTokenPurpose, "email_token_purpose"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
