import uuid
from datetime import UTC, datetime, timedelta, timezone

import pytest

from app.core.ids import new_id
from app.core.time import ensure_aware, utc_now


def test_utc_now_is_timezone_aware() -> None:
    assert utc_now().tzinfo is UTC


def test_ensure_aware_converts_offsets_to_utc() -> None:
    ist = timezone(timedelta(hours=5, minutes=30))
    value = ensure_aware(datetime(2026, 1, 1, 10, 0, tzinfo=ist))
    assert value == datetime(2026, 1, 1, 4, 30, tzinfo=UTC)


def test_ensure_aware_rejects_naive_datetimes() -> None:
    with pytest.raises(ValueError, match="timezone offset"):
        ensure_aware(datetime(2026, 1, 1, 10, 0))  # noqa: DTZ001


def test_new_id_is_uuid4() -> None:
    assert uuid.UUID(new_id()).version == 4
