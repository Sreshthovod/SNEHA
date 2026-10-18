"""Single-use email links (verify email, reset password). Only token hashes are stored."""

from datetime import timedelta

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.security import hash_token, new_token
from app.core.time import utc_now
from app.models.enums import EmailTokenPurpose
from app.models.users import EmailToken, User


def issue(db: Session, user: User, purpose: EmailTokenPurpose, ttl: timedelta) -> str:
    """Create a new link token; older unused tokens for the same purpose stop working."""
    now = utc_now()
    db.execute(
        update(EmailToken)
        .where(
            EmailToken.user_id == user.id,
            EmailToken.purpose == purpose,
            EmailToken.used_at.is_(None),
        )
        .values(used_at=now)
        .execution_options(synchronize_session=False)
    )
    token = new_token()
    db.add(
        EmailToken(
            user_id=user.id,
            purpose=purpose,
            token_hash=hash_token(token),
            expires_at=now + ttl,
        )
    )
    return token


def consume(db: Session, token: str, purpose: EmailTokenPurpose) -> User | None:
    """Redeem a token once. A conditional UPDATE makes concurrent redemption impossible."""
    now = utc_now()
    row = db.scalar(
        select(EmailToken).where(
            EmailToken.token_hash == hash_token(token), EmailToken.purpose == purpose
        )
    )
    if row is None:
        return None
    claimed = db.execute(
        update(EmailToken)
        .where(
            EmailToken.id == row.id,
            EmailToken.used_at.is_(None),
            EmailToken.expires_at > now,
        )
        .values(used_at=now)
        .execution_options(synchronize_session=False)
    ).rowcount
    if claimed != 1:
        return None
    user = db.get(User, row.user_id)
    if user is None or not user.is_active:
        return None
    return user
