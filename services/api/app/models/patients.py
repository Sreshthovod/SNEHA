from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CreatedAtMixin, IdMixin, TimestampMixin
from app.db.types import UTCDateTime, str_enum
from app.models.enums import ConsentGiver, ConsentStatus, ConsentType, Language


class PatientProfile(IdMixin, TimestampMixin, Base):
    """The person using the patient app. Holds the minimum data needed to personalise activities."""

    __tablename__ = "patient_profiles"
    __table_args__ = (
        CheckConstraint(
            "birth_year IS NULL OR birth_year BETWEEN 1900 AND 2100", name="birth_year"
        ),
    )

    # The patient's own login identity, created when a device is paired.
    user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), unique=True
    )
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    preferred_name: Mapped[str | None] = mapped_column(String(60))
    # Year only (data minimisation): enough for age-appropriate content.
    birth_year: Mapped[int | None] = mapped_column(Integer)
    preferred_language: Mapped[Language] = mapped_column(
        str_enum(Language, "language"), nullable=False
    )
    region: Mapped[str | None] = mapped_column(String(80))
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Kolkata", nullable=False)
    # True only for clearly labelled synthetic demo fixtures.
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))


class CaregiverRelationship(IdMixin, TimestampMixin, Base):
    __tablename__ = "caregiver_relationships"
    __table_args__ = (UniqueConstraint("patient_id", "caregiver_id"),)

    patient_id: Mapped[str] = mapped_column(
        ForeignKey("patient_profiles.id", ondelete="CASCADE"), index=True, nullable=False
    )
    caregiver_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    relationship_label: Mapped[str] = mapped_column(String(40), nullable=False)
    # Managers may edit the profile, approve memories, add caregivers and grant clinicians.
    can_manage: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(UTCDateTime)


class ClinicianAccessGrant(IdMixin, TimestampMixin, Base):
    """Time-limited, read-only access for a verified clinician. Valid only while
    not revoked, not expired, and while clinician-sharing consent is granted."""

    __tablename__ = "clinician_access_grants"
    __table_args__ = (
        CheckConstraint("expires_at > starts_at", name="expiry_after_start"),
        Index("ix_clinician_access_grants_lookup", "clinician_id", "patient_id"),
    )

    patient_id: Mapped[str] = mapped_column(
        ForeignKey("patient_profiles.id", ondelete="CASCADE"), index=True, nullable=False
    )
    clinician_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    granted_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    starts_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    purpose: Mapped[str] = mapped_column(String(200), nullable=False)


class ConsentRecord(IdMixin, CreatedAtMixin, Base):
    """Append-only consent ledger. The latest record per (patient, type) is the current state."""

    __tablename__ = "consent_records"
    __table_args__ = (
        Index("ix_consent_records_current", "patient_id", "consent_type", "recorded_at"),
    )

    patient_id: Mapped[str] = mapped_column(
        ForeignKey("patient_profiles.id", ondelete="CASCADE"), nullable=False
    )
    consent_type: Mapped[ConsentType] = mapped_column(
        str_enum(ConsentType, "consent_type"), nullable=False
    )
    status: Mapped[ConsentStatus] = mapped_column(
        str_enum(ConsentStatus, "consent_status"), nullable=False
    )
    given_by: Mapped[ConsentGiver] = mapped_column(
        str_enum(ConsentGiver, "consent_giver"), nullable=False
    )
    policy_version: Mapped[str] = mapped_column(String(20), nullable=False)
    recorded_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    recorded_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)


class DevicePairingCode(IdMixin, CreatedAtMixin, Base):
    """Single-use code a caregiver generates to sign in the patient's phone without a password."""

    __tablename__ = "device_pairing_codes"

    patient_id: Mapped[str] = mapped_column(
        ForeignKey("patient_profiles.id", ondelete="CASCADE"), index=True, nullable=False
    )
    code_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    created_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(UTCDateTime)


class PatientPreferences(TimestampMixin, Base):
    """Caregiver-approved preferences that personalise activity selection.

    Only managing caregivers can change these, so every entry is approved by construction.
    """

    __tablename__ = "patient_preferences"
    __table_args__ = (CheckConstraint("session_minutes BETWEEN 5 AND 60", name="session_minutes"),)

    patient_id: Mapped[str] = mapped_column(
        ForeignKey("patient_profiles.id", ondelete="CASCADE"), primary_key=True
    )
    # Lower-case tags, e.g. ["cooking", "tea", "bihu", "football"].
    interests: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    disliked_activity_slugs: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    session_minutes: Mapped[int] = mapped_column(Integer, default=15, nullable=False)
    updated_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
