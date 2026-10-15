"""more activity types, fatigue observations

Adds activity types `object_recognition` and `categorization`, the observation category
`fatigue`, and three catalog entries used by the Stage 1 patient app.

Enum CHECK constraints are replaced by name. On SQLite this runs in batch mode (table
copy); the other named CHECK constraints are preserved because SQLAlchemy reflects them.

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-15 09:00:00+00:00
"""

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | Sequence[str] | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OLD_ACTIVITY_TYPES = [
    "memory_recall", "picture_matching", "word_association", "sequencing",
    "attention", "orientation", "reminiscence",
]
NEW_ACTIVITY_TYPES = [*OLD_ACTIVITY_TYPES, "object_recognition", "categorization"]
OLD_OBSERVATION = ["mood", "sleep", "appetite", "orientation", "behaviour", "physical", "other"]
NEW_OBSERVATION = [*OLD_OBSERVATION, "fatigue"]

SEEDED_AT = datetime(2026, 10, 15, 9, tzinfo=UTC)
ACTIVITIES = [
    {
        "id": "4b0c2d0e-5f0e-4c39-9d43-1a6f3f0a0008",
        "slug": "familiar-faces",
        "title": "Familiar faces",
        "description": "Match a name to the photo of a familiar person from the Memory Bank.",
        "activity_type": "memory_recall",
        "cognitive_domains": ["episodic_memory", "face_recognition"],
        "min_difficulty": 1, "max_difficulty": 3, "default_duration_seconds": 240,
        "uses_memory_bank": True,
    },
    {
        "id": "4b0c2d0e-5f0e-4c39-9d43-1a6f3f0a0009",
        "slug": "name-the-object",
        "title": "Name the object",
        "description": "Look at a picture of an everyday object and choose its name.",
        "activity_type": "object_recognition",
        "cognitive_domains": ["language", "semantic_memory"],
        "min_difficulty": 1, "max_difficulty": 3, "default_duration_seconds": 180,
        "uses_memory_bank": False,
    },
    {
        "id": "4b0c2d0e-5f0e-4c39-9d43-1a6f3f0a0010",
        "slug": "sort-into-groups",
        "title": "Sort into groups",
        "description": "Put everyday things into simple groups, such as food and clothing.",
        "activity_type": "categorization",
        "cognitive_domains": ["executive_function", "semantic_memory"],
        "min_difficulty": 1, "max_difficulty": 3, "default_duration_seconds": 180,
        "uses_memory_bank": False,
    },
]


def _in(column: str, values: list[str]) -> str:
    return f"{column} IN (" + ", ".join(f"'{v}'" for v in values) + ")"


def _replace_check(table: str, name: str, column: str, values: list[str]) -> None:
    with op.batch_alter_table(table) as batch:
        batch.drop_constraint(op.f(f"ck_{table}_{name}"), type_="check")
        batch.create_check_constraint(name, _in(column, values))


activity_table = sa.table(
    "activity_definitions",
    *(sa.column(c) for c in [
        "id", "slug", "version", "title", "description", "activity_type", "cognitive_domains",
        "min_difficulty", "max_difficulty", "default_duration_seconds", "supports_offline",
        "uses_memory_bank", "is_active", "created_at", "updated_at",
    ]),
)
activity_table.c.cognitive_domains.type = sa.JSON()
activity_table.c.created_at.type = sa.DateTime(timezone=True)
activity_table.c.updated_at.type = sa.DateTime(timezone=True)
changes_table = sa.table(
    "sync_changes",
    *(sa.column(c) for c in ["patient_id", "entity_type", "entity_id", "operation"]),
    sa.column("changed_at", sa.DateTime(timezone=True)),
)


def upgrade() -> None:
    _replace_check("activity_definitions", "activity_type", "activity_type", NEW_ACTIVITY_TYPES)
    _replace_check("caregiver_observations", "observation_category", "category", NEW_OBSERVATION)

    bind = op.get_bind()
    ts = SEEDED_AT.replace(tzinfo=None) if bind.dialect.name == "sqlite" else SEEDED_AT
    op.bulk_insert(
        activity_table,
        [{**a, "version": 1, "supports_offline": True, "is_active": True,
          "created_at": ts, "updated_at": ts} for a in ACTIVITIES],
    )
    op.bulk_insert(
        changes_table,
        [{"patient_id": None, "entity_type": "activity_definition", "entity_id": a["id"],
          "operation": "upsert", "changed_at": ts} for a in ACTIVITIES],
    )


def downgrade() -> None:
    ids = [a["id"] for a in ACTIVITIES]
    op.execute(changes_table.delete().where(changes_table.c.entity_id.in_(ids)))
    op.execute(activity_table.delete().where(activity_table.c.id.in_(ids)))
    op.execute("DELETE FROM caregiver_observations WHERE category = 'fatigue'")
    _replace_check("caregiver_observations", "observation_category", "category", OLD_OBSERVATION)
    _replace_check("activity_definitions", "activity_type", "activity_type", OLD_ACTIVITY_TYPES)
