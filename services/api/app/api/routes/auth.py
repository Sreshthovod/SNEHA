"""Registration, login, logout, email verification, password reset and device pairing."""

from datetime import timedelta

from fastapi import APIRouter, BackgroundTasks, Request, status
from sqlalchemy import select, update

from app.api.deps import DbSessionDep, PrincipalDep, SettingsDep
from app.core.config import Settings
from app.core.errors import AppError, conflict
from app.core.rate_limit import client_key, email_limiter, login_limiter, pairing_limiter
from app.core.security import hash_pairing_code, hash_password
from app.core.time import utc_now
from app.models.enums import AuditOutcome, AuthSessionKind, EmailTokenPurpose, UserRole
from app.models.patients import DevicePairingCode, PatientProfile
from app.models.users import AuthSession, User
from app.schemas.auth import (
    DevicePairRequest,
    EmailRequest,
    LoginRequest,
    RegisterRequest,
    ResetPasswordRequest,
    TokenResponse,
    UserOut,
    VerifyEmailRequest,
)
from app.schemas.common import ErrorResponse
from app.services import audit, email_tokens
from app.services.auth import authenticate_password, issue_session, normalise_email
from app.services.email import (
    EmailSender,
    EmailSenderDep,
    deliver,
    password_reset_email,
    verification_email,
)

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
def register(
    body: RegisterRequest,
    db: DbSessionDep,
    settings: SettingsDep,
    sender: EmailSenderDep,
    background: BackgroundTasks,
    request: Request,
) -> User:
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
    _send_verification(db, user, settings, sender, background)
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
    if settings.require_email_verification and not user.email_verified:
        # Checked after the password, so this never reveals whether an account exists.
        audit.record(
            db,
            "auth.login",
            outcome=AuditOutcome.FAILURE,
            actor_id=user.id,
            request=request,
            details={"reason": "email_not_verified"},
            commit=True,
        )
        raise AppError(
            403,
            "email_not_verified",
            "Please confirm your email first. We sent you a link when you registered.",
        )
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


def _send_verification(
    db: DbSessionDep,
    user: User,
    settings: Settings,
    sender: EmailSender,
    background: BackgroundTasks,
) -> None:
    if not user.email:
        return
    hours = settings.email_verification_ttl_hours
    token = email_tokens.issue(db, user, EmailTokenPurpose.VERIFY_EMAIL, timedelta(hours=hours))
    link = f"{settings.dashboard_url}/verify-email?token={token}"
    background.add_task(
        deliver, sender, verification_email(user.email, user.full_name, link, hours)
    )


def _limit_email(request: Request, email: str) -> None:
    login_limiter.check(f"email:{client_key(request)}")
    email_limiter.check(f"email:{email}")


_ACCEPTED = {
    status.HTTP_202_ACCEPTED: {
        "description": "Accepted. The same answer whether or not an "
        "account exists for this address."
    },
    422: {"model": ErrorResponse},
    429: {"model": ErrorResponse},
}


@router.post(
    "/verify-email",
    response_model=UserOut,
    responses={400: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
    summary="Confirm an email address with the link sent by email",
)
def verify_email(body: VerifyEmailRequest, db: DbSessionDep, request: Request) -> User:
    login_limiter.check(f"verify:{client_key(request)}")
    user = email_tokens.consume(db, body.token, EmailTokenPurpose.VERIFY_EMAIL)
    if user is None:
        db.rollback()
        raise AppError(
            400,
            "invalid_link",
            "This link has expired or was already used. Ask for a new one from the sign-in page.",
        )
    if user.email_verified_at is None:
        user.email_verified_at = utc_now()
    audit.record(
        db,
        "auth.email_verified",
        actor_id=user.id,
        target_type="user",
        target_id=user.id,
        request=request,
    )
    db.commit()
    return user


@router.post(
    "/resend-verification",
    status_code=status.HTTP_202_ACCEPTED,
    responses=_ACCEPTED,
    summary="Send a new email confirmation link",
)
def resend_verification(
    body: EmailRequest,
    db: DbSessionDep,
    settings: SettingsDep,
    sender: EmailSenderDep,
    background: BackgroundTasks,
    request: Request,
) -> None:
    email = normalise_email(body.email)
    _limit_email(request, email)
    user = db.scalar(select(User).where(User.email == email))
    if user is not None and user.is_active and not user.email_verified:
        _send_verification(db, user, settings, sender, background)
        db.commit()


@router.post(
    "/forgot-password",
    status_code=status.HTTP_202_ACCEPTED,
    responses=_ACCEPTED,
    summary="Email a password reset link",
)
def forgot_password(
    body: EmailRequest,
    db: DbSessionDep,
    settings: SettingsDep,
    sender: EmailSenderDep,
    background: BackgroundTasks,
    request: Request,
) -> None:
    email = normalise_email(body.email)
    _limit_email(request, email)
    user = db.scalar(select(User).where(User.email == email))
    if user is None or not user.is_active or user.password_hash is None:
        return
    minutes = settings.password_reset_ttl_minutes
    token = email_tokens.issue(
        db, user, EmailTokenPurpose.RESET_PASSWORD, timedelta(minutes=minutes)
    )
    audit.record(
        db,
        "auth.password_reset_requested",
        actor_id=user.id,
        target_type="user",
        target_id=user.id,
        request=request,
    )
    db.commit()
    link = f"{settings.dashboard_url}/reset-password?token={token}"
    background.add_task(deliver, sender, password_reset_email(email, user.full_name, link, minutes))


@router.post(
    "/reset-password",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={400: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
    summary="Choose a new password with the link sent by email; signs out everywhere",
)
def reset_password(body: ResetPasswordRequest, db: DbSessionDep, request: Request) -> None:
    login_limiter.check(f"reset:{client_key(request)}")
    user = email_tokens.consume(db, body.token, EmailTokenPurpose.RESET_PASSWORD)
    if user is None:
        db.rollback()
        raise AppError(
            400,
            "invalid_link",
            "This link has expired or was already used. Ask for a new one.",
        )
    now = utc_now()
    user.password_hash = hash_password(body.password)
    user.failed_login_attempts = 0
    user.locked_until = None
    # Opening the emailed link proves the address belongs to this person.
    if user.email_verified_at is None:
        user.email_verified_at = now
    db.execute(
        update(AuthSession)
        .where(AuthSession.user_id == user.id, AuthSession.revoked_at.is_(None))
        .values(revoked_at=now)
        .execution_options(synchronize_session=False)
    )
    audit.record(
        db,
        "auth.password_reset",
        actor_id=user.id,
        target_type="user",
        target_id=user.id,
        request=request,
    )
    db.commit()


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
    # Claim the code with one conditional UPDATE so two concurrent requests cannot both
    # redeem it: only the request whose UPDATE matched a row may continue.
    claimed = (
        code is not None
        and db.execute(
            update(DevicePairingCode)
            .where(
                DevicePairingCode.id == code.id,
                DevicePairingCode.used_at.is_(None),
                DevicePairingCode.expires_at > now,
            )
            .values(used_at=now)
            .execution_options(synchronize_session=False)
        ).rowcount
        == 1
    )
    if not claimed:
        db.rollback()
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
        db,
        user,
        settings,
        kind=AuthSessionKind.DEVICE,
        device_name=body.device_name,
        pairing_code_id=code.id,
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
