from datetime import datetime
from typing import Annotated
from zoneinfo import available_timezones

from pydantic import EmailStr, Field, StringConstraints, field_validator

from app.models.enums import ConsentGiver, ConsentStatus, ConsentType, Language
from app.schemas.base import Label, RequestModel, ResponseModel, ShortText, UtcDatetime

_TIMEZONES = frozenset(available_timezones())


def _check_timezone(value: str | None) -> str | None:
    if value is not None and value not in _TIMEZONES:
        raise ValueError("Unknown IANA timezone, e.g. 'Asia/Kolkata'")
    return value


class PatientCreate(RequestModel):
    display_name: ShortText
    preferred_name: Annotated[str, StringConstraints(min_length=1, max_length=60)] | None = None
    birth_year: int | None = Field(default=None, ge=1900, le=2100)
    preferred_language: Language
    region: Annotated[str, StringConstraints(min_length=1, max_length=80)] | None = None
    timezone: str = "Asia/Kolkata"
    relationship_label: Label = Field(
        description="How the creating caregiver relates, e.g. 'daughter'."
    )

    _tz = field_validator("timezone")(_check_timezone)


class PatientUpdate(RequestModel):
    display_name: ShortText | None = None
    preferred_name: Annotated[str, StringConstraints(min_length=1, max_length=60)] | None = None
    birth_year: int | None = Field(default=None, ge=1900, le=2100)
    preferred_language: Language | None = None
    region: Annotated[str, StringConstraints(min_length=1, max_length=80)] | None = None
    timezone: str | None = None

    _tz = field_validator("timezone")(_check_timezone)


class PatientErase(RequestModel):
    confirm_display_name: Annotated[str, StringConstraints(min_length=1, max_length=120)]


class PatientOut(ResponseModel):
    id: str
    display_name: str
    preferred_name: str | None
    birth_year: int | None
    preferred_language: Language
    region: str | None
    timezone: str
    is_synthetic: bool
    has_paired_device: bool
    created_at: datetime
    updated_at: datetime


class PairingCodeOut(ResponseModel):
    code: str = Field(description="Show once to the caregiver; enter it on the patient's phone.")
    expires_at: UtcDatetime


class CaregiverAdd(RequestModel):
    email: EmailStr = Field(description="An existing caregiver account.")
    relationship_label: Label
    can_manage: bool = False


class CaregiverOut(ResponseModel):
    id: str
    caregiver_id: str
    caregiver_name: str
    relationship_label: str
    can_manage: bool
    created_at: datetime


class ClinicianGrantCreate(RequestModel):
    clinician_email: EmailStr
    expires_at: UtcDatetime
    purpose: Annotated[str, StringConstraints(min_length=3, max_length=200)]


class ClinicianGrantOut(ResponseModel):
    id: str
    clinician_id: str
    clinician_name: str
    starts_at: datetime
    expires_at: datetime
    revoked_at: datetime | None
    purpose: str


class ConsentCreate(RequestModel):
    consent_type: ConsentType
    status: ConsentStatus
    given_by: ConsentGiver


class ConsentOut(ResponseModel):
    id: str
    consent_type: ConsentType
    status: ConsentStatus
    given_by: ConsentGiver
    policy_version: str
    recorded_at: datetime
    recorded_by_id: str | None


class ConsentSummary(ResponseModel):
    current: dict[ConsentType, ConsentStatus | None]
    history: list[ConsentOut]
