"""Timezone-aware time helpers. Naive datetimes are never stored or returned."""

from datetime import UTC, datetime


def utc_now() -> datetime:
    return datetime.now(UTC)


def ensure_aware(value: datetime) -> datetime:
    """Reject naive datetimes instead of silently guessing a timezone."""
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(
            "Timestamp must include a timezone offset (e.g. 2026-01-01T10:00:00+05:30)"
        )
    return value.astimezone(UTC)
