"""Registration, login, logout and patient-device pairing."""

from fastapi import APIRouter, Request, status
from sqlalchemy import select

from app.api.deps import DbSessionDep, PrincipalDep, SettingsDep
from app.core.errors import AppError, conflict
from app.core.rate_limit import client_key, login_limiter, pairing_limiter
from app.core.security import hash_pairing_code, hash_password
from app.core.time import utc_now
from app.models.enums import AuditOutcome, AuthSessionKind, UserRole
from app.models.patients import DevicePairingCode, PatientProfile
from app.models.users import User
from app.schemas.auth import (
    DevicePairRequest,
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserOut,
)
from app.schemas.common import ErrorResponse
from app.services import audit
from app.services.auth import authenticate_password, issue_session, normalise_email

router = APIRouter(prefix="/auth", tags=["auth"])

_ERRORS = {
    401: {"model": ErrorResponse},
    422: {"model": ErrorResponse},
    429: {"model": ErrorResponse},
}


@router.post(
    "/register",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
    responses={409: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
    summary="Create a caregiver or clinician account",
)
def register(body: RegisterRequest, db: DbSessionDep, request: Request) -> User:
    login_limiter.check(f"register:{client_key(request)}")
    email = normalise_email(body.email)
    if db.scalar(select(User.id).where(User.email == email)) is not None:
        raise conflict("email_taken", "An account with this email already exists.")
    user = User(
        email=email,
        password_hash=hash_password(body.password),
        full_name=body.full_name,
        role=body.role,
        is_verified=False,
    )
    db.add(user)
    db.flush()
    audit.record(
        db,
        "auth.register",
        actor_id=user.id,
        target_type="user",
        target_id=user.id,
        request=request,
        details={"role": user.role.value},
    )
    db.commit()
    return user


@router.post(
    "/login", response_model=TokenResponse, responses={**_ERRORS, 423: {"model": ErrorResponse}}
)
def login(
    body: LoginRequest, db: DbSessionDep, settings: SettingsDep, request: Request
) -> TokenResponse:
    login_limiter.check(f"login:{client_key(request)}")
    try:
        user = authenticate_password(db, body.email, body.password, settings)
    except AppError as error:
        audit.record(
            db,
            "auth.login",
            outcome=AuditOutcome.FAILURE,
            request=request,
            details={"reason": error.code},
            commit=True,
        )
        raise
    issued = issue_session(db, user, settings, kind=AuthSessionKind.PASSWORD)
    audit.record(db, "auth.login", actor_id=user.id, request=request)
    db.commit()
    return TokenResponse(
        access_token=issued.token,
        expires_at=issued.session.expires_at,
        user=UserOut.model_validate(user),
    )


@router.post(
    "/logout", status_code=status.HTTP_204_NO_CONTENT, responses={401: {"model": ErrorResponse}}
)
def logout(principal: PrincipalDep, db: DbSessionDep, request: Request) -> None:
    principal.session.revoked_at = utc_now()
    audit.record(db, "auth.logout", actor_id=principal.id, request=request)
    db.commit()


@router.get("/me", response_model=UserOut, responses={401: {"model": ErrorResponse}})
def me(principal: PrincipalDep) -> User:
    return principal.user


@router.post(
    "/device/pair",
    response_model=TokenResponse,
    responses={**_ERRORS},
    summary="Exchange a caregiver-issued pairing code for a patient device session",
)
def pair_device(
    body: DevicePairRequest, db: DbSessionDep, settings: SettingsDep, request: Request
) -> TokenResponse:
    pairing_limiter.check(f"pair:{client_key(request)}")
    now = utc_now()
    code = db.scalar(
        select(DevicePairingCode).where(
            DevicePairingCode.code_hash == hash_pairing_code(body.code, settings.pairing_secret)
        )
    )
    if code is None or code.used_at is not None or code.expires_at <= now:
        audit.record(
            db,
            "auth.device_pair",
            outcome=AuditOutcome.FAILURE,
            request=request,
            details={"reason": "invalid_code"},
            commit=True,
        )
        raise AppError(
            401, "invalid_pairing_code", "This code is not valid. Ask your caregiver for a new one."
        )

    patient = db.get(PatientProfile, code.patient_id)
    if patient is None:  # unreachable: FK with ON DELETE CASCADE
        raise AppError(401, "invalid_pairing_code", "This code is not valid.")
    code.used_at = now

    user = db.get(User, patient.user_id) if patient.user_id else None
    if user is None:
        user = User(full_name=patient.display_name, role=UserRole.PATIENT, is_verified=True)
        db.add(user)
        db.flush()
        patient.user_id = user.id

    issued = issue_session(
        db, user, settings, kind=AuthSessionKind.DEVICE, device_name=body.device_name
    )
    audit.record(
        db,
        "auth.device_pair",
        actor_id=user.id,
        patient_id=patient.id,
        target_type="patient",
        target_id=patient.id,
        request=request,
    )
    db.commit()
    return TokenResponse(
        access_token=issued.token,
        expires_at=issued.session.expires_at,
        user=UserOut.model_validate(user),
        patient_id=patient.id,
    )
