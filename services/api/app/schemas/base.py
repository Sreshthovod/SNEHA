from datetime import UTC, datetime
from typing import Annotated

from pydantic import AfterValidator, AwareDatetime, BaseModel, ConfigDict, StringConstraints

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


class RequestModel(BaseModel):
    """Rejects unknown fields so typos and mass-assignment attempts fail loudly."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ResponseModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Page[T](BaseModel):
    items: list[T]
    next_cursor: str | None = None
