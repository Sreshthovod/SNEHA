from datetime import datetime
from typing import Annotated, Literal

from pydantic import AwareDatetime, EmailStr, Field, StringConstraints

from app.models.enums import UserRole
from app.schemas.base import RequestModel, ResponseModel

Password = Annotated[str, StringConstraints(min_length=12, max_length=128)]


class RegisterRequest(RequestModel):
    email: EmailStr
    password: Password = Field(description="12–128 characters. Passphrases are encouraged.")
    full_name: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)
    ]
    role: Literal[UserRole.CAREGIVER, UserRole.CLINICIAN] = Field(
        description="Self-registration is limited to caregivers and clinicians. "
        "Clinicians must be verified by an administrator before receiving access grants."
    )


class LoginRequest(RequestModel):
    email: EmailStr
    password: Annotated[str, StringConstraints(min_length=1, max_length=128)]


class DevicePairRequest(RequestModel):
    code: Annotated[str, StringConstraints(strip_whitespace=True, min_length=8, max_length=16)]
    device_name: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)
    ] = "Patient device"


class UserOut(ResponseModel):
    id: str
    email: str | None
    full_name: str
    role: UserRole
    is_verified: bool
    created_at: datetime


class TokenResponse(ResponseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"  # noqa: S105 - not a secret
    expires_at: AwareDatetime
    user: UserOut
    patient_id: str | None = Field(
        default=None, description="Set for device sessions: the paired patient profile."
    )
