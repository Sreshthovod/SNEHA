"""Patient profiles, device pairing, caregiver relationships, clinician grants and consent."""

from datetime import timedelta

from fastapi import APIRouter, Request, Response, status
from sqlalchemy import func, select

from app.api.deps import DbSessionDep, PrincipalDep, SettingsDep, patient_access, require_roles
from app.core.errors import AppError, conflict, not_found
from app.core.security import hash_pairing_code, new_pairing_code
from app.core.time import utc_now
from app.models.enums import ConsentStatus, ConsentType, UserRole
from app.models.files import StoredFile
from app.models.patients import (
    CaregiverRelationship,
    ClinicianAccessGrant,
    ConsentRecord,
    DevicePairingCode,
    PatientProfile,
)
from app.models.users import AuthSession, User
from app.schemas.common import ErrorResponse
from app.schemas.patients import (
    CaregiverAdd,
    CaregiverOut,
    ClinicianGrantCreate,
    ClinicianGrantOut,
    ConsentCreate,
    ConsentOut,
    ConsentSummary,
    PairingCodeOut,
    PatientCreate,
    PatientErase,
    PatientOut,
    PatientUpdate,
)
from app.services import audit
from app.services.access import (
    PatientAccess,
    Permission,
    accessible_patient_ids,
    current_consent,
    has_consent,
)
from app.services.auth import normalise_email
from app.services.files import FileStore

router = APIRouter(prefix="/patients", tags=["patients"])

_ERRORS = {
    401: {"model": ErrorResponse},
    403: {"model": ErrorResponse},
    404: {"model": ErrorResponse},
    422: {"model": ErrorResponse},
}


def to_out(patient: PatientProfile) -> PatientOut:
    return PatientOut.model_validate(
        {
            **{c: getattr(patient, c) for c in PatientOut.model_fields if hasattr(patient, c)},
            "has_paired_device": patient.user_id is not None,
        }
    )


# ---------- profiles ----------


@router.get("", response_model=list[PatientOut], responses=_ERRORS)
def list_patients(principal: PrincipalDep, db: DbSessionDep) -> list[PatientOut]:
    """Patients the caller is authorised to see."""
    ids = accessible_patient_ids(db, principal.user)
    if not ids:
        return []
    rows = db.scalars(
        select(PatientProfile)
        .where(PatientProfile.id.in_(ids))
        .order_by(PatientProfile.display_name)
    )
    return [to_out(p) for p in rows]


@router.post(
    "",
    response_model=PatientOut,
    status_code=status.HTTP_201_CREATED,
    responses=_ERRORS,
    dependencies=[require_roles(UserRole.CAREGIVER)],
)
def create_patient(
    body: PatientCreate, principal: PrincipalDep, db: DbSessionDep, request: Request
) -> PatientOut:
    """Create a patient profile. The creating caregiver becomes a managing caregiver."""
    patient = PatientProfile(
        **body.model_dump(exclude={"relationship_label"}), created_by_id=principal.id
    )
    db.add(patient)
    db.flush()
    db.add(
        CaregiverRelationship(
            patient_id=patient.id,
            caregiver_id=principal.id,
            relationship_label=body.relationship_label,
            can_manage=True,
        )
    )
    audit.record(
        db,
        "patient.create",
        actor_id=principal.id,
        patient_id=patient.id,
        target_type="patient",
        target_id=patient.id,
        request=request,
    )
    db.commit()
    return to_out(patient)


@router.get("/{patient_id}", response_model=PatientOut, responses=_ERRORS)
def get_patient(access: PatientAccess = patient_access(Permission.VIEW_PROFILE)) -> PatientOut:
    return to_out(access.patient)


@router.patch("/{patient_id}", response_model=PatientOut, responses=_ERRORS)
def update_patient(
    body: PatientUpdate,
    principal: PrincipalDep,
    db: DbSessionDep,
    request: Request,
    access: PatientAccess = patient_access(Permission.MANAGE_PATIENT),
) -> PatientOut:
    changes = body.model_dump(exclude_unset=True)
    for required in ("display_name", "preferred_language", "timezone"):
        if required in changes and changes[required] is None:
            raise AppError(422, "validation_error", f"{required} cannot be null.")
    for field, value in changes.items():
        setattr(access.patient, field, value)
    audit.record(
        db,
        "patient.update",
        actor_id=principal.id,
        patient_id=access.patient.id,
        target_type="patient",
        target_id=access.patient.id,
        request=request,
    )
    db.commit()
    return to_out(access.patient)


# ---------- device pairing ----------


@router.post(
    "/{patient_id}/pairing-codes",
    response_model=PairingCodeOut,
    status_code=status.HTTP_201_CREATED,
    responses=_ERRORS,
)
def create_pairing_code(
    principal: PrincipalDep,
    db: DbSessionDep,
    settings: SettingsDep,
    request: Request,
    access: PatientAccess = patient_access(Permission.MANAGE_PATIENT),
) -> PairingCodeOut:
    """Issue a single-use code to sign in the patient's phone.

    Older unused codes are invalidated.
    """
    now = utc_now()
    for old in db.scalars(
        select(DevicePairingCode).where(
            DevicePairingCode.patient_id == access.patient.id, DevicePairingCode.used_at.is_(None)
        )
    ):
        old.used_at = now
    code = new_pairing_code()
    expires_at = now + timedelta(minutes=settings.pairing_code_ttl_minutes)
    db.add(
        DevicePairingCode(
            patient_id=access.patient.id,
            code_hash=hash_pairing_code(code, settings.pairing_secret),
            created_by_id=principal.id,
            expires_at=expires_at,
        )
    )
    audit.record(
        db,
        "patient.pairing_code.create",
        actor_id=principal.id,
        patient_id=access.patient.id,
        request=request,
    )
    db.commit()
    return PairingCodeOut(code=f"{code[:4]}-{code[4:]}", expires_at=expires_at)


@router.post(
    "/{patient_id}/devices/revoke", status_code=status.HTTP_204_NO_CONTENT, responses=_ERRORS
)
def revoke_devices(
    principal: PrincipalDep,
    db: DbSessionDep,
    request: Request,
    access: PatientAccess = patient_access(Permission.MANAGE_PATIENT),
) -> Response:
    """Sign out every paired patient device (e.g. a lost phone).

    Unused pairing codes are cancelled too, so a code issued just before cannot be
    redeemed afterwards.
    """
    now = utc_now()
    _cancel_pairing_codes(db, access.patient.id, now)
    if access.patient.user_id:
        for session in db.scalars(
            select(AuthSession).where(
                AuthSession.user_id == access.patient.user_id, AuthSession.revoked_at.is_(None)
            )
        ):
            session.revoked_at = now
    audit.record(
        db,
        "patient.devices.revoke",
        actor_id=principal.id,
        patient_id=access.patient.id,
        request=request,
    )
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------- caregivers ----------


def _caregiver_out(db, rel: CaregiverRelationship) -> CaregiverOut:
    user = db.get(User, rel.caregiver_id)
    return CaregiverOut(
        id=rel.id,
        caregiver_id=rel.caregiver_id,
        caregiver_name=user.full_name if user else "Unknown",
        relationship_label=rel.relationship_label,
        can_manage=rel.can_manage,
        created_at=rel.created_at,
    )


@router.get("/{patient_id}/caregivers", response_model=list[CaregiverOut], responses=_ERRORS)
def list_caregivers(
    db: DbSessionDep, access: PatientAccess = patient_access(Permission.VIEW_OBSERVATIONS)
) -> list[CaregiverOut]:
    rels = db.scalars(
        select(CaregiverRelationship).where(
            CaregiverRelationship.patient_id == access.patient.id,
            CaregiverRelationship.revoked_at.is_(None),
        )
    )
    return [_caregiver_out(db, r) for r in rels]


@router.post(
    "/{patient_id}/caregivers",
    response_model=CaregiverOut,
    status_code=status.HTTP_201_CREATED,
    responses={**_ERRORS, 409: {"model": ErrorResponse}},
)
def add_caregiver(
    body: CaregiverAdd,
    principal: PrincipalDep,
    db: DbSessionDep,
    request: Request,
    access: PatientAccess = patient_access(Permission.MANAGE_PATIENT),
) -> CaregiverOut:
    user = db.scalar(select(User).where(User.email == normalise_email(body.email)))
    if user is None or user.role is not UserRole.CAREGIVER or not user.is_active:
        raise AppError(
            422, "caregiver_not_found", "No active caregiver account exists with that email."
        )
    rel = db.scalar(
        select(CaregiverRelationship).where(
            CaregiverRelationship.patient_id == access.patient.id,
            CaregiverRelationship.caregiver_id == user.id,
        )
    )
    if rel is not None and rel.revoked_at is None:
        raise conflict("already_caregiver", "This person is already a caregiver for the patient.")
    if rel is None:
        rel = CaregiverRelationship(patient_id=access.patient.id, caregiver_id=user.id)
        db.add(rel)
    rel.relationship_label = body.relationship_label
    rel.can_manage = body.can_manage
    rel.revoked_at = None
    db.flush()
    audit.record(
        db,
        "patient.caregiver.add",
        actor_id=principal.id,
        patient_id=access.patient.id,
        target_type="user",
        target_id=user.id,
        request=request,
        details={"can_manage": body.can_manage},
    )
    db.commit()
    return _caregiver_out(db, rel)


@router.delete(
    "/{patient_id}/caregivers/{relationship_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={**_ERRORS, 409: {"model": ErrorResponse}},
)
def remove_caregiver(
    relationship_id: str,
    principal: PrincipalDep,
    db: DbSessionDep,
    request: Request,
    access: PatientAccess = patient_access(Permission.MANAGE_PATIENT),
) -> Response:
    rel = db.get(CaregiverRelationship, relationship_id)
    if rel is None or rel.patient_id != access.patient.id or rel.revoked_at is not None:
        raise not_found("Caregiver relationship")
    if rel.can_manage:
        managers = db.scalar(
            select(func.count())
            .select_from(CaregiverRelationship)
            .where(
                CaregiverRelationship.patient_id == access.patient.id,
                CaregiverRelationship.can_manage.is_(True),
                CaregiverRelationship.revoked_at.is_(None),
            )
        )
        if managers <= 1:
            raise conflict(
                "last_manager", "Add another managing caregiver before removing the last one."
            )
    now = utc_now()
    rel.revoked_at = now
    # Phones this caregiver paired, and codes they issued, must not outlive their access.
    _cancel_pairing_codes(db, access.patient.id, now, created_by_id=rel.caregiver_id)
    signed_out = 0
    if access.patient.user_id:
        sessions = db.scalars(
            select(AuthSession)
            .join(DevicePairingCode, AuthSession.pairing_code_id == DevicePairingCode.id)
            .where(
                AuthSession.user_id == access.patient.user_id,
                AuthSession.revoked_at.is_(None),
                DevicePairingCode.created_by_id == rel.caregiver_id,
            )
        ).all()
        for session in sessions:
            session.revoked_at = now
        signed_out = len(sessions)
    audit.record(
        db,
        "patient.caregiver.remove",
        actor_id=principal.id,
        patient_id=access.patient.id,
        target_type="user",
        target_id=rel.caregiver_id,
        request=request,
        details={"count": signed_out},
    )
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _cancel_pairing_codes(db, patient_id: str, now, *, created_by_id: str | None = None) -> None:
    query = select(DevicePairingCode).where(
        DevicePairingCode.patient_id == patient_id,
        DevicePairingCode.used_at.is_(None),
        DevicePairingCode.expires_at > now,
    )
    if created_by_id is not None:
        query = query.where(DevicePairingCode.created_by_id == created_by_id)
    for code in db.scalars(query):
        # Marking the code used is how pairing codes are invalidated elsewhere too.
        code.used_at = now


# ---------- clinician access grants ----------


def _grant_out(db, grant: ClinicianAccessGrant) -> ClinicianGrantOut:
    user = db.get(User, grant.clinician_id)
    return ClinicianGrantOut(
        id=grant.id,
        clinician_id=grant.clinician_id,
        clinician_name=user.full_name if user else "Unknown",
        starts_at=grant.starts_at,
        expires_at=grant.expires_at,
        revoked_at=grant.revoked_at,
        purpose=grant.purpose,
    )


@router.get(
    "/{patient_id}/clinician-grants", response_model=list[ClinicianGrantOut], responses=_ERRORS
)
def list_grants(
    db: DbSessionDep, access: PatientAccess = patient_access(Permission.MANAGE_PATIENT)
) -> list[ClinicianGrantOut]:
    grants = db.scalars(
        select(ClinicianAccessGrant)
        .where(ClinicianAccessGrant.patient_id == access.patient.id)
        .order_by(ClinicianAccessGrant.created_at.desc())
    )
    return [_grant_out(db, g) for g in grants]


@router.post(
    "/{patient_id}/clinician-grants",
    response_model=ClinicianGrantOut,
    status_code=status.HTTP_201_CREATED,
    responses={**_ERRORS, 409: {"model": ErrorResponse}},
)
def create_grant(
    body: ClinicianGrantCreate,
    principal: PrincipalDep,
    db: DbSessionDep,
    settings: SettingsDep,
    request: Request,
    access: PatientAccess = patient_access(Permission.MANAGE_PATIENT),
) -> ClinicianGrantOut:
    if not has_consent(db, access.patient.id, ConsentType.CLINICIAN_SHARING):
        raise AppError(
            409, "consent_required", "Record clinician-sharing consent before granting access."
        )
    clinician = db.scalar(select(User).where(User.email == normalise_email(body.clinician_email)))
    if clinician is None or clinician.role is not UserRole.CLINICIAN or not clinician.is_active:
        raise AppError(
            422, "clinician_not_found", "No active clinician account exists with that email."
        )
    if not clinician.is_verified:
        raise AppError(
            409, "clinician_not_verified", "This clinician account has not been verified yet."
        )
    now = utc_now()
    if body.expires_at <= now:
        raise AppError(422, "validation_error", "expires_at must be in the future.")
    if body.expires_at > now + timedelta(days=settings.max_clinician_grant_days):
        raise AppError(
            422,
            "validation_error",
            f"Access can be granted for at most {settings.max_clinician_grant_days} days.",
        )
    grant = ClinicianAccessGrant(
        patient_id=access.patient.id,
        clinician_id=clinician.id,
        granted_by_id=principal.id,
        starts_at=now,
        expires_at=body.expires_at,
        purpose=body.purpose,
    )
    db.add(grant)
    db.flush()
    audit.record(
        db,
        "patient.clinician_grant.create",
        actor_id=principal.id,
        patient_id=access.patient.id,
        target_type="user",
        target_id=clinician.id,
        request=request,
        details={"expires_at": body.expires_at.isoformat()},
    )
    db.commit()
    return _grant_out(db, grant)


@router.delete(
    "/{patient_id}/clinician-grants/{grant_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=_ERRORS,
)
def revoke_grant(
    grant_id: str,
    principal: PrincipalDep,
    db: DbSessionDep,
    request: Request,
    access: PatientAccess = patient_access(Permission.MANAGE_PATIENT),
) -> Response:
    grant = db.get(ClinicianAccessGrant, grant_id)
    if grant is None or grant.patient_id != access.patient.id:
        raise not_found("Clinician access grant")
    if grant.revoked_at is None:
        grant.revoked_at = utc_now()
        audit.record(
            db,
            "patient.clinician_grant.revoke",
            actor_id=principal.id,
            patient_id=access.patient.id,
            target_type="user",
            target_id=grant.clinician_id,
            request=request,
        )
        db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------- consent ----------


@router.get("/{patient_id}/consents", response_model=ConsentSummary, responses=_ERRORS)
def get_consents(
    db: DbSessionDep, access: PatientAccess = patient_access(Permission.VIEW_CONSENT)
) -> ConsentSummary:
    history = db.scalars(
        select(ConsentRecord)
        .where(ConsentRecord.patient_id == access.patient.id)
        .order_by(ConsentRecord.recorded_at.desc())
    )
    return ConsentSummary(
        current={t: current_consent(db, access.patient.id, t) for t in ConsentType},
        history=[ConsentOut.model_validate(r) for r in history],
    )


@router.post(
    "/{patient_id}/consents",
    response_model=ConsentOut,
    status_code=status.HTTP_201_CREATED,
    responses=_ERRORS,
)
def record_consent(
    body: ConsentCreate,
    principal: PrincipalDep,
    db: DbSessionDep,
    settings: SettingsDep,
    request: Request,
    access: PatientAccess = patient_access(Permission.MANAGE_PATIENT),
) -> ConsentRecord:
    """Append a consent decision.

    Withdrawing clinician sharing revokes every active clinician grant, so granting it
    again later does not silently restore access for clinicians who were cut off.
    """
    now = utc_now()
    if (
        body.consent_type == ConsentType.CLINICIAN_SHARING
        and body.status == ConsentStatus.WITHDRAWN
    ):
        grants = db.scalars(
            select(ClinicianAccessGrant).where(
                ClinicianAccessGrant.patient_id == access.patient.id,
                ClinicianAccessGrant.revoked_at.is_(None),
            )
        ).all()
        for grant in grants:
            grant.revoked_at = now
            audit.record(
                db,
                "patient.clinician_grant.revoke",
                actor_id=principal.id,
                patient_id=access.patient.id,
                target_type="user",
                target_id=grant.clinician_id,
                request=request,
                details={"reason": "consent_withdrawn"},
            )
    record = ConsentRecord(
        patient_id=access.patient.id,
        consent_type=body.consent_type,
        status=body.status,
        given_by=body.given_by,
        policy_version=settings.consent_policy_version,
        recorded_by_id=principal.id,
        recorded_at=now,
    )
    db.add(record)
    audit.record(
        db,
        "patient.consent.record",
        actor_id=principal.id,
        patient_id=access.patient.id,
        request=request,
        details={"consent_type": body.consent_type.value, "status": body.status.value},
    )
    db.commit()
    return record


# ---------- erasure ----------


@router.post(
    "/{patient_id}/erase",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={**_ERRORS, 409: {"model": ErrorResponse}},
)
def erase_patient(
    body: PatientErase,
    principal: PrincipalDep,
    db: DbSessionDep,
    settings: SettingsDep,
    request: Request,
    access: PatientAccess = patient_access(Permission.ERASE_PATIENT),
) -> Response:
    """Permanently erase the patient and ALL their data: profile, memories, photos, activity
    history, observations, reports, consents, sync records and the patient's device login.

    `confirm_display_name` must match the profile exactly. Only the audit trail entry
    (IDs, no content) remains. This cannot be undone.
    """
    patient = access.patient
    if body.confirm_display_name != patient.display_name:
        raise AppError(
            409, "confirmation_mismatch", "Type the patient's name exactly to confirm erasure."
        )
    storage_keys = list(
        db.scalars(select(StoredFile.storage_key).where(StoredFile.patient_id == patient.id))
    )
    patient_user = db.get(User, patient.user_id) if patient.user_id else None
    patient_id = patient.id
    db.delete(patient)  # ON DELETE CASCADE removes every patient-scoped row
    db.flush()
    if patient_user is not None:
        db.delete(patient_user)
    audit.record(
        db,
        "patient.erase",
        actor_id=principal.id,
        patient_id=patient_id,
        target_type="patient",
        target_id=patient_id,
        request=request,
        details={"count": len(storage_keys)},
    )
    db.commit()
    store = FileStore(settings.media_root)
    for key in storage_keys:
        store.delete(key)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
