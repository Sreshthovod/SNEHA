import re
from datetime import UTC, datetime
from typing import Annotated, Any

from pydantic import (
    AfterValidator,
    AwareDatetime,
    BaseModel,
    ConfigDict,
    StringConstraints,
    model_validator,
)

UUID_PATTERN = r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"

RecordId = Annotated[str, StringConstraints(pattern=UUID_PATTERN, to_lower=True)]
ShortText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
Label = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=40)]
Tag = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=40)]


def _to_utc(value: datetime) -> datetime:
    return value.astimezone(UTC)


# Timezone REQUIRED on input (naive values are a 422), normalised to UTC so responses
# are consistent no matter which offset the client sent.
UtcDatetime = Annotated[AwareDatetime, AfterValidator(_to_utc)]


# C0 control characters other than tab, newline and carriage return, plus DEL. NUL in
# particular cannot be stored in PostgreSQL text columns.
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def _has_control_chars(value: Any) -> bool:
    if isinstance(value, str):
        return _CONTROL_CHARS.search(value) is not None
    if isinstance(value, dict):
        return any(_has_control_chars(k) or _has_control_chars(v) for k, v in value.items())
    if isinstance(value, list | tuple):
        return any(_has_control_chars(v) for v in value)
    return False


class RequestModel(BaseModel):
    """Rejects unknown fields so typos and mass-assignment attempts fail loudly."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    @model_validator(mode="before")
    @classmethod
    def _reject_control_characters(cls, data: Any) -> Any:
        if _has_control_chars(data):
            raise ValueError("Text must not contain control characters")
        return data


class ResponseModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Page[T](BaseModel):
    items: list[T]
    next_cursor: str | None = None
