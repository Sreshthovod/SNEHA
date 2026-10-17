"""instructions_repeated activity event

Allows `activity_events.event_type = 'instructions_repeated'`: the person pressed "Read
aloud" to hear the question again. Engine 1.2.0 uses the count to read questions first.

Revision ID: 0013
Revises: 0012
Create Date: 2026-10-18 15:00:00+00:00
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0013"
down_revision: str | Sequence[str] | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OLD = [
    "activity_started", "attempt", "hint_requested", "hint_auto", "round_solved",
    "round_skipped", "paused", "resumed", "fatigue_reported", "stop_requested",
    "adaptation", "break_taken", "break_declined", "activity_ended",
]
NEW = [*OLD, "instructions_repeated"]


def _check(values: list[str]) -> None:
    with op.batch_alter_table("activity_events") as batch:
        batch.drop_constraint(op.f("ck_activity_events_activity_event_type"), type_="check")
        batch.create_check_constraint(
            "activity_event_type", "event_type IN (" + ", ".join(f"'{v}'" for v in values) + ")"
        )


def upgrade() -> None:
    _check(NEW)


def downgrade() -> None:
    op.execute("DELETE FROM activity_events WHERE event_type = 'instructions_repeated'")
    _check(OLD)
