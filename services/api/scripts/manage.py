"""Administrative commands that deliberately have no HTTP endpoint.

Usage (from services/api):
  uv run python scripts/manage.py verify-clinician <email>
  uv run python scripts/manage.py deactivate-user <email>
  uv run python scripts/manage.py create-admin <email> <full name>   (prompts for password)

Clinician verification is an out-of-band check (e.g. medical registration number)
performed by an operator; it is audited.
"""

import argparse
import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402

from app.core.security import hash_password  # noqa: E402
from app.db.session import get_sessionmaker  # noqa: E402
from app.models.enums import UserRole  # noqa: E402
from app.models.users import User  # noqa: E402
from app.services import audit  # noqa: E402
from app.services.auth import normalise_email  # noqa: E402


def _user(db, email: str) -> User:
    user = db.scalar(select(User).where(User.email == normalise_email(email)))
    if user is None:
        sys.exit(f"No user with email {email}")
    return user


def verify_clinician(email: str) -> None:
    with get_sessionmaker()() as db:
        user = _user(db, email)
        if user.role is not UserRole.CLINICIAN:
            sys.exit(f"{email} is a {user.role.value}, not a clinician")
        user.is_verified = True
        audit.record(db, "admin.verify_clinician", target_type="user", target_id=user.id)
        db.commit()
    print(f"Verified clinician {email}")


def deactivate_user(email: str) -> None:
    with get_sessionmaker()() as db:
        user = _user(db, email)
        user.is_active = False
        audit.record(db, "admin.deactivate_user", target_type="user", target_id=user.id)
        db.commit()
    print(f"Deactivated {email}; existing sessions stop working immediately")


def create_admin(email: str, full_name: str) -> None:
    password = getpass.getpass("Password (min 12 chars): ")
    if len(password) < 12:
        sys.exit("Password too short")
    with get_sessionmaker()() as db:
        user = User(
            email=normalise_email(email),
            password_hash=hash_password(password),
            full_name=full_name,
            role=UserRole.ADMIN,
            is_verified=True,
        )
        db.add(user)
        db.flush()
        audit.record(db, "admin.create_admin", target_type="user", target_id=user.id)
        db.commit()
    print(f"Created admin {email}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("verify-clinician").add_argument("email")
    sub.add_parser("deactivate-user").add_argument("email")
    admin = sub.add_parser("create-admin")
    admin.add_argument("email")
    admin.add_argument("full_name")
    args = parser.parse_args()
    match args.command:
        case "verify-clinician":
            verify_clinician(args.email)
        case "deactivate-user":
            deactivate_user(args.email)
        case "create-admin":
            create_admin(args.email, args.full_name)


if __name__ == "__main__":
    main()
