"""Reusable FastAPI dependency aliases."""

import uuid
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Path, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.errors import forbidden
from app.db.session import get_db, get_engine
from app.models.enums import UserRole
from app.models.users import AuthSession, User
from app.services.access import PatientAccess, Permission, authorize
from app.services.auth import resolve_token, unauthorized

SettingsDep = Annotated[Settings, Depends(get_settings)]
EngineDep = Annotated[Engine, Depends(get_engine)]
DbSessionDep = Annotated[Session, Depends(get_db)]

_bearer = HTTPBearer(
    auto_error=False, description="Opaque token from /auth/login or /auth/device/pair"
)


@dataclass(frozen=True)
class Principal:
    """The authenticated caller. Role comes from the database, never from the client."""

    user: User
    session: AuthSession

    @property
    def id(self) -> str:
        return self.user.id

    @property
    def role(self) -> UserRole:
        return self.user.role


def get_principal(
    db: DbSessionDep,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> Principal:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise unauthorized()
    user, session = resolve_token(db, credentials.credentials)
    return Principal(user=user, session=session)


PrincipalDep = Annotated[Principal, Depends(get_principal)]


def require_roles(*roles: UserRole):
    def _check(principal: PrincipalDep) -> Principal:
        if principal.role not in roles:
            raise forbidden("Your account type cannot perform this action.")
        return principal

    return Depends(_check)


def patient_access(permission: Permission):
    """Dependency: authorise the caller for `{patient_id}` in the path, or 404/403."""

    def _check(
        patient_id: Annotated[uuid.UUID, Path(description="Patient profile ID")],
        principal: PrincipalDep,
        db: DbSessionDep,
        request: Request,
    ) -> PatientAccess:
        return authorize(db, principal.user, str(patient_id), permission, request=request)

    return Depends(_check)
