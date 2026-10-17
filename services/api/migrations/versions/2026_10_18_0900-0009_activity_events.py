"""activity events

Adds `activity_events`: what happened inside an activity run (answers with latency,
hints, pauses, tiredness reports, stop requests and in-session adaptation decisions),
pushed by the device through sync as the new `activity_event` entity.

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-18 09:00:00+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: str | Sequence[str] | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OLD_ENTITIES = [
    "activity_session", "activity_result", "conversation", "personalization_state",
    "memory_item", "memory_relationship", "routine_item", "activity_definition",
]
NEW_ENTITIES = [*OLD_ENTITIES, "activity_event"]
EVENT_TYPES = [
    "activity_started", "attempt", "hint_requested", "hint_auto", "round_solved",
    "round_skipped", "paused", "resumed", "fatigue_reported", "stop_requested",
    "adaptation", "break_taken", "break_declined", "activity_ended",
]


def _in(column: str, values: list[str]) -> str:
    return f"{column} IN (" + ", ".join(f"'{v}'" for v in values) + ")"


def _sync_entity_check(values: list[str]) -> None:
    for table in ("sync_changes", "sync_mutations"):
        with op.batch_alter_table(table) as batch:
            batch.drop_constraint(op.f(f"ck_{table}_sync_entity"), type_="check")
            batch.create_check_constraint("sync_entity", _in("entity_type", values))


def upgrade() -> None:
    op.create_table(
        "activity_events",
        sa.Column("patient_id", sa.String(36), nullable=False),
        sa.Column("session_id", sa.String(36), nullable=False),
        sa.Column("activity_id", sa.String(36), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(32), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("round_index", sa.Integer(), nullable=True),
        sa.Column("data", sa.JSON(), nullable=False),
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("seq >= 0", name=op.f("ck_activity_events_seq_non_negative")),
        sa.CheckConstraint(
            "round_index IS NULL OR round_index >= 0",
            name=op.f("ck_activity_events_round_non_negative"),
        ),
        sa.CheckConstraint(
            _in("event_type", EVENT_TYPES), name=op.f("ck_activity_events_activity_event_type")
        ),
        sa.ForeignKeyConstraint(
            ["patient_id"], ["patient_profiles.id"],
            name=op.f("fk_activity_events_patient_id_patient_profiles"), ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["session_id"], ["activity_sessions.id"],
            name=op.f("fk_activity_events_session_id_activity_sessions"), ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["activity_id"], ["activity_definitions.id"],
            name=op.f("fk_activity_events_activity_id_activity_definitions"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_activity_events")),
    )
    op.create_index("ix_activity_events_session_seq", "activity_events", ["session_id", "seq"])
    op.create_index(
        "ix_activity_events_patient_occurred", "activity_events", ["patient_id", "occurred_at"]
    )
    _sync_entity_check(NEW_ENTITIES)


def downgrade() -> None:
    for table in ("sync_changes", "sync_mutations"):
        op.execute(f"DELETE FROM {table} WHERE entity_type = 'activity_event'")
    _sync_entity_check(OLD_ENTITIES)
    op.drop_index("ix_activity_events_patient_occurred", "activity_events")
    op.drop_index("ix_activity_events_session_seq", "activity_events")
    op.drop_table("activity_events")
