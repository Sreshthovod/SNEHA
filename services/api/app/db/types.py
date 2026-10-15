"""Portable column types that behave identically on SQLite and PostgreSQL."""

from datetime import UTC, datetime
from enum import StrEnum

import sqlalchemy as sa
from sqlalchemy.engine import Dialect
from sqlalchemy.types import TypeDecorator


class UTCDateTime(TypeDecorator[datetime]):
    """Timezone-aware datetime, always stored and returned in UTC.

    PostgreSQL keeps the offset (timestamptz). SQLite has no timezone support and
    returns naive values, so we reattach UTC on the way out. Naive values are
    rejected on the way in rather than guessed.
    """

    impl = sa.DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Naive datetime cannot be stored; include a timezone")
        value = value.astimezone(UTC)
        return value.replace(tzinfo=None) if dialect.name == "sqlite" else value

    def process_result_value(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)


def str_enum[E: StrEnum](enum_cls: type[E], name: str) -> sa.Enum:
    """Store a StrEnum as VARCHAR + CHECK constraint (no native PG enum: easier migrations)."""
    return sa.Enum(
        enum_cls,
        name=name,
        native_enum=False,
        create_constraint=True,
        length=32,
        values_callable=lambda members: [m.value for m in members],
        validate_strings=True,
    )


# Big auto-increment integers on PostgreSQL; SQLite only auto-increments INTEGER PRIMARY KEY.
BigIntPK = sa.BigInteger().with_variant(sa.Integer(), "sqlite")
