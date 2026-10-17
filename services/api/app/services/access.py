"""Server-enforced, per-patient authorization.

Every endpoint that touches patient data calls `authorize(...)` with the patient ID
from the URL (or record) and the permission it needs. The caller's role and
relationships are read from the database; nothing the client sends about roles is trusted.

Rules:
- patient     : only their own profile (profile.user_id == user.id).
- caregiver   : patients with an active (non-revoked) caregiver relationship.
                Managing caregivers (can_manage) get the MANAGE_* permissions.
- clinician   : must be verified, hold a valid grant (started, not expired, not revoked),
                and the patient's latest `clinician_sharing` consent must be GRANTED.
                Read-only; no Memory Bank content.
- admin       : no patient-data access by default (least privilege).

If the caller has no relationship to the patient at all, a 404 is returned so that
patient IDs cannot be probed. If they have a relationship but lack the permission, 403.
"""

from dataclasses import dataclass
from enum import StrEnum

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import forbidden, not_found
from app.core.time import utc_now
from app.models.enums import AuditOutcome, ConsentStatus, ConsentType, UserRole
from app.models.patients import (
    CaregiverRelationship,
    ClinicianAccessGrant,
    ConsentRecord,
    PatientProfile,
)
from app.models.users import User
from app.services import audit


class Permission(StrEnum):
    VIEW_PROFILE = "view_profile"
    MANAGE_PATIENT = "manage_patient"  # edit profile, caregivers, grants, consent, pairing
    VIEW_MEMORIES = "view_memories"
    PROPOSE_MEMORY = "propose_memory"
    MANAGE_MEMORIES = "manage_memories"  # approve, reject, correct, delete
    RECORD_ACTIVITY = "record_activity"  # sessions, results, sync push
    VIEW_HISTORY = "view_history"
    WRITE_OBSERVATION = "write_observation"
    VIEW_OBSERVATIONS = "view_observations"
    VIEW_REPORTS = "view_reports"
    REQUEST_REPORT = "request_report"
    UPLOAD_MEDIA = "upload_media"
    VIEW_ROUTINES = "view_routines"
    MANAGE_ROUTINES = "manage_routines"
    VIEW_CONSENT = "view_consent"
    ERASE_PATIENT = "erase_patient"
    VIEW_PROGRESS = "view_progress"
    MANAGE_PREFERENCES = "manage_preferences"
    REVIEW_OBSERVATION = "review_observation"  # review/resolve caregiver observations
    # Review items (migration 0011). Clinicians see only confirmed items.
    VIEW_REVIEW_ITEMS = "view_review_items"
    SCAN_REVIEW_ITEMS = "scan_review_items"  # turn current review prompts into items
    DECIDE_REVIEW_ITEM = "decide_review_item"  # confirm or dismiss, with a reason


P = Permission

_PATIENT_PERMISSIONS = frozenset(
    {
        P.VIEW_PROFILE,
        P.VIEW_MEMORIES,
        P.PROPOSE_MEMORY,
        P.RECORD_ACTIVITY,
        P.VIEW_ROUTINES,
        P.VIEW_CONSENT,
        P.VIEW_PROGRESS,
    }
)
_CAREGIVER_PERMISSIONS = frozenset(
    {
        P.VIEW_PROFILE,
        P.VIEW_MEMORIES,
        P.PROPOSE_MEMORY,
        P.RECORD_ACTIVITY,
        P.VIEW_HISTORY,
        P.WRITE_OBSERVATION,
        P.VIEW_OBSERVATIONS,
        P.VIEW_REPORTS,
        P.REQUEST_REPORT,
        P.UPLOAD_MEDIA,
        P.VIEW_ROUTINES,
        P.VIEW_CONSENT,
        P.VIEW_PROGRESS,
        P.VIEW_REVIEW_ITEMS,
        P.SCAN_REVIEW_ITEMS,
    }
)
_MANAGER_EXTRA = frozenset(
    {
        P.DECIDE_REVIEW_ITEM,
        P.MANAGE_PATIENT,
        P.MANAGE_MEMORIES,
        P.MANAGE_ROUTINES,
        P.ERASE_PATIENT,
        P.REVIEW_OBSERVATION,
        P.MANAGE_PREFERENCES,
    }
)
_CLINICIAN_PERMISSIONS = frozenset(
    {
        P.VIEW_PROFILE,
        P.VIEW_HISTORY,
        P.VIEW_OBSERVATIONS,
        P.VIEW_REPORTS,
        P.REQUEST_REPORT,
        P.VIEW_CONSENT,
        P.VIEW_PROGRESS,
        P.VIEW_REVIEW_ITEMS,
    }
)


@dataclass(frozen=True)
class PatientAccess:
    patient: PatientProfile
    permissions: frozenset[Permission]
    relationship: CaregiverRelationship | None = None
    grant: ClinicianAccessGrant | None = None

    def can(self, permission: Permission) -> bool:
        return permission in self.permissions

    @property
    def is_clinician(self) -> bool:
        return self.grant is not None


def current_consent(
    db: Session, patient_id: str, consent_type: ConsentType
) -> ConsentStatus | None:
    latest = db.scalar(
        select(ConsentRecord)
        .where(ConsentRecord.patient_id == patient_id, ConsentRecord.consent_type == consent_type)
        .order_by(ConsentRecord.recorded_at.desc(), ConsentRecord.created_at.desc())
        .limit(1)
    )
    return latest.status if latest else None


def has_consent(db: Session, patient_id: str, consent_type: ConsentType) -> bool:
    return current_consent(db, patient_id, consent_type) is ConsentStatus.GRANTED


def active_relationship(db: Session, patient_id: str, user_id: str) -> CaregiverRelationship | None:
    return db.scalar(
        select(CaregiverRelationship).where(
            CaregiverRelationship.patient_id == patient_id,
            CaregiverRelationship.caregiver_id == user_id,
            CaregiverRelationship.revoked_at.is_(None),
        )
    )


def valid_grant(db: Session, patient_id: str, clinician_id: str) -> ClinicianAccessGrant | None:
    now = utc_now()
    return db.scalar(
        select(ClinicianAccessGrant)
        .where(
            ClinicianAccessGrant.patient_id == patient_id,
            ClinicianAccessGrant.clinician_id == clinician_id,
            ClinicianAccessGrant.revoked_at.is_(None),
            ClinicianAccessGrant.starts_at <= now,
            ClinicianAccessGrant.expires_at > now,
        )
        .order_by(ClinicianAccessGrant.expires_at.desc())
        .limit(1)
    )


def resolve_access(db: Session, user: User, patient_id: str) -> PatientAccess | None:
    """Return the caller's access to a patient, or None if they have none."""
    patient = db.get(PatientProfile, patient_id)
    if patient is None:
        return None

    match user.role:
        case UserRole.PATIENT:
            if patient.user_id == user.id:
                return PatientAccess(patient, _PATIENT_PERMISSIONS)
        case UserRole.CAREGIVER:
            rel = active_relationship(db, patient_id, user.id)
            if rel is not None:
                perms = _CAREGIVER_PERMISSIONS | (_MANAGER_EXTRA if rel.can_manage else frozenset())
                return PatientAccess(patient, perms, relationship=rel)
        case UserRole.CLINICIAN:
            if user.is_verified:
                grant = valid_grant(db, patient_id, user.id)
                if grant is not None and has_consent(db, patient_id, ConsentType.CLINICIAN_SHARING):
                    return PatientAccess(patient, _CLINICIAN_PERMISSIONS, grant=grant)
        case UserRole.ADMIN:
            pass
    return None


def authorize(
    db: Session,
    user: User,
    patient_id: str,
    permission: Permission,
    *,
    request: Request | None = None,
) -> PatientAccess:
    access = resolve_access(db, user, patient_id)
    if access is None or not access.can(permission):
        audit.record(
            db,
            "access.denied",
            outcome=AuditOutcome.DENIED,
            actor_id=user.id,
            patient_id=patient_id if access is not None else None,
            target_type="patient",
            target_id=patient_id,
            request=request,
            details={"reason": permission.value, "role": user.role.value},
            commit=True,
        )
        if access is None:
            raise not_found("Patient")
        raise forbidden()
    return access


def accessible_patient_ids(db: Session, user: User) -> list[str]:
    """IDs of every patient the caller can at least VIEW_PROFILE."""
    match user.role:
        case UserRole.PATIENT:
            ids = db.scalars(select(PatientProfile.id).where(PatientProfile.user_id == user.id))
        case UserRole.CAREGIVER:
            ids = db.scalars(
                select(CaregiverRelationship.patient_id).where(
                    CaregiverRelationship.caregiver_id == user.id,
                    CaregiverRelationship.revoked_at.is_(None),
                )
            )
        case UserRole.CLINICIAN:
            if not user.is_verified:
                return []
            now = utc_now()
            candidates = db.scalars(
                select(ClinicianAccessGrant.patient_id)
                .where(
                    ClinicianAccessGrant.clinician_id == user.id,
                    ClinicianAccessGrant.revoked_at.is_(None),
                    ClinicianAccessGrant.starts_at <= now,
                    ClinicianAccessGrant.expires_at > now,
                )
                .distinct()
            )
            return [
                pid for pid in candidates if has_consent(db, pid, ConsentType.CLINICIAN_SHARING)
            ]
        case _:
            return []
    return list(ids)
