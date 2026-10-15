"""Authentication: password login, device pairing, bearer-token validation."""

from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import AppError
from app.core.security import (
    hash_password,
    hash_token,
    new_token,
    password_needs_rehash,
    verify_password,
)
from app.core.time import utc_now
from app.models.enums import AuthSessionKind
from app.models.users import AuthSession, User


@dataclass(frozen=True)
class IssuedToken:
    token: str
    session: AuthSession


def unauthorized(message: str = "Authentication required.") -> AppError:
    return AppError(401, "unauthorized", message, headers={"WWW-Authenticate": "Bearer"})


def normalise_email(email: str) -> str:
    return email.strip().lower()


def issue_session(
    db: Session,
    user: User,
    settings: Settings,
    *,
    kind: AuthSessionKind,
    device_name: str | None = None,
) -> IssuedToken:
    ttl = (
        timedelta(days=settings.device_session_ttl_days)
        if kind is AuthSessionKind.DEVICE
        else timedelta(hours=settings.session_ttl_hours)
    )
    token = new_token()
    session = AuthSession(
        user_id=user.id,
        token_hash=hash_token(token),
        kind=kind,
        device_name=device_name,
        expires_at=utc_now() + ttl,
    )
    db.add(session)
    db.flush()
    return IssuedToken(token=token, session=session)


def authenticate_password(db: Session, email: str, password: str, settings: Settings) -> User:
    """Verify credentials with lockout. Error messages never reveal whether the email exists."""
    user = db.scalar(select(User).where(User.email == normalise_email(email)))
    now = utc_now()
    invalid = unauthorized("Email or password is incorrect.")

    if user is not None and user.locked_until is not None and user.locked_until > now:
        verify_password(None, password)  # keep timing similar
        raise AppError(
            423,
            "account_locked",
            "Too many failed attempts. Try again later or reset your password.",
        )

    if not verify_password(user.password_hash if user else None, password):
        if user is not None:
            user.failed_login_attempts += 1
            if user.failed_login_attempts >= settings.max_failed_logins:
                user.locked_until = now + timedelta(minutes=settings.lockout_minutes)
                user.failed_login_attempts = 0
            db.commit()
        raise invalid

    if not user or not user.is_active:
        raise invalid

    user.failed_login_attempts = 0
    user.locked_until = None
    if user.password_hash and password_needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)
    return user


def resolve_token(db: Session, token: str) -> tuple[User, AuthSession]:
    session = db.scalar(select(AuthSession).where(AuthSession.token_hash == hash_token(token)))
    now = utc_now()
    if session is None or session.revoked_at is not None or session.expires_at <= now:
        raise unauthorized("Your session has expired. Please sign in again.")
    user = db.get(User, session.user_id)
    if user is None or not user.is_active:
        raise unauthorized("Your session has expired. Please sign in again.")
    # Throttle writes: only record usage every few minutes.
    if session.last_used_at is None or now - session.last_used_at > timedelta(minutes=5):
        session.last_used_at = now
        db.commit()
    return user, session
