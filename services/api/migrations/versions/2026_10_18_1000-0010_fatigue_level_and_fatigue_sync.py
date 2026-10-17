"""fatigue level on observations; fatigue reports sync both ways

`caregiver_observations.fatigue_level` (mild | severe, fatigue observations only) and the
`fatigue_report` sync entity: a caregiver's report made on the phone is pushed and stored
as a fatigue observation; fatigue observations (level and time, never the note) are
pulled by the phone so its engine and a running activity respect them offline.

Revision ID: 0010
Revises: 0009
Create Date: 2026-10-18 10:00:00+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: str | Sequence[str] | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OLD_ENTITIES = [
    "activity_session", "activity_result", "conversation", "personalization_state",
    "memory_item", "memory_relationship", "routine_item", "activity_definition",
    "activity_event",
]
NEW_ENTITIES = [*OLD_ENTITIES, "fatigue_report"]


def _in(column: str, values: list[str]) -> str:
    return f"{column} IN (" + ", ".join(f"'{v}'" for v in values) + ")"


def _sync_entity_check(values: list[str]) -> None:
    for table in ("sync_changes", "sync_mutations"):
        with op.batch_alter_table(table) as batch:
            batch.drop_constraint(op.f(f"ck_{table}_sync_entity"), type_="check")
            batch.create_check_constraint("sync_entity", _in("entity_type", values))


def upgrade() -> None:
    with op.batch_alter_table("caregiver_observations") as batch:
        batch.add_column(sa.Column("fatigue_level", sa.String(32), nullable=True))
        batch.create_check_constraint(
            "fatigue_level", "fatigue_level IS NULL OR fatigue_level IN ('mild', 'severe')"
        )
    _sync_entity_check(NEW_ENTITIES)


def downgrade() -> None:
    for table in ("sync_changes", "sync_mutations"):
        op.execute(f"DELETE FROM {table} WHERE entity_type = 'fatigue_report'")
    _sync_entity_check(OLD_ENTITIES)
    with op.batch_alter_table("caregiver_observations") as batch:
        batch.drop_constraint(op.f("ck_caregiver_observations_fatigue_level"), type_="check")
        batch.drop_column("fatigue_level")
