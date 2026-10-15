"""seed activity catalog

The initial catalog of offline-capable activities. These are product content
(not patient data). IDs are fixed so every environment and every device agree.
The activity content itself (pictures, word lists) ships inside the patient app.

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-15 06:40:00+00:00
"""

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | Sequence[str] | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SEEDED_AT = datetime(2026, 10, 15, tzinfo=UTC)

ACTIVITIES = [
    {
        "id": "4b0c2d0e-5f0e-4c39-9d43-1a6f3f0a0001",
        "slug": "picture-pairs",
        "title": "Matching pairs",
        "description": "Turn over cards to find pairs of matching everyday pictures.",
        "activity_type": "picture_matching",
        "cognitive_domains": ["visual_memory", "attention"],
        "min_difficulty": 1,
        "max_difficulty": 5,
        "default_duration_seconds": 300,
        "uses_memory_bank": False,
    },
    {
        "id": "4b0c2d0e-5f0e-4c39-9d43-1a6f3f0a0002",
        "slug": "word-partners",
        "title": "Word partners",
        "description": "Choose the word that goes with another, using familiar regional words.",
        "activity_type": "word_association",
        "cognitive_domains": ["language", "semantic_memory"],
        "min_difficulty": 1,
        "max_difficulty": 5,
        "default_duration_seconds": 240,
        "uses_memory_bank": False,
    },
    {
        "id": "4b0c2d0e-5f0e-4c39-9d43-1a6f3f0a0003",
        "slug": "daily-sequence",
        "title": "Put in order",
        "description": "Arrange the steps of an everyday task, such as making tea, in order.",
        "activity_type": "sequencing",
        "cognitive_domains": ["executive_function"],
        "min_difficulty": 1,
        "max_difficulty": 5,
        "default_duration_seconds": 240,
        "uses_memory_bank": False,
    },
    {
        "id": "4b0c2d0e-5f0e-4c39-9d43-1a6f3f0a0004",
        "slug": "spot-the-different",
        "title": "Find the different one",
        "description": "Find the picture that is different from the others.",
        "activity_type": "attention",
        "cognitive_domains": ["attention", "processing_speed"],
        "min_difficulty": 1,
        "max_difficulty": 5,
        "default_duration_seconds": 180,
        "uses_memory_bank": False,
    },
    {
        "id": "4b0c2d0e-5f0e-4c39-9d43-1a6f3f0a0005",
        "slug": "today-together",
        "title": "Today together",
        "description": "Gentle questions about the day, season and place, always showing the answer.",
        "activity_type": "orientation",
        "cognitive_domains": ["orientation"],
        "min_difficulty": 1,
        "max_difficulty": 3,
        "default_duration_seconds": 120,
        "uses_memory_bank": False,
    },
    {
        "id": "4b0c2d0e-5f0e-4c39-9d43-1a6f3f0a0006",
        "slug": "photo-recall",
        "title": "Remember with photos",
        "description": "Recall people and places from caregiver-approved Memory Bank photos.",
        "activity_type": "memory_recall",
        "cognitive_domains": ["episodic_memory"],
        "min_difficulty": 1,
        "max_difficulty": 5,
        "default_duration_seconds": 300,
        "uses_memory_bank": True,
    },
    {
        "id": "4b0c2d0e-5f0e-4c39-9d43-1a6f3f0a0007",
        "slug": "story-time",
        "title": "Story time",
        "description": "Talk about an approved memory. Not scored; for enjoyment and connection.",
        "activity_type": "reminiscence",
        "cognitive_domains": ["autobiographical_memory", "language"],
        "min_difficulty": 1,
        "max_difficulty": 1,
        "default_duration_seconds": 600,
        "uses_memory_bank": True,
    },
]

activity_table = sa.table(
    "activity_definitions",
    sa.column("id", sa.String),
    sa.column("slug", sa.String),
    sa.column("version", sa.Integer),
    sa.column("title", sa.String),
    sa.column("description", sa.Text),
    sa.column("activity_type", sa.String),
    sa.column("cognitive_domains", sa.JSON),
    sa.column("min_difficulty", sa.Integer),
    sa.column("max_difficulty", sa.Integer),
    sa.column("default_duration_seconds", sa.Integer),
    sa.column("supports_offline", sa.Boolean),
    sa.column("uses_memory_bank", sa.Boolean),
    sa.column("is_active", sa.Boolean),
    sa.column("created_at", sa.DateTime(timezone=True)),
    sa.column("updated_at", sa.DateTime(timezone=True)),
)

changes_table = sa.table(
    "sync_changes",
    sa.column("patient_id", sa.String),
    sa.column("entity_type", sa.String),
    sa.column("entity_id", sa.String),
    sa.column("operation", sa.String),
    sa.column("changed_at", sa.DateTime(timezone=True)),
)


def _ts(bind) -> datetime:
    # SQLite stores naive UTC (see app.db.types.UTCDateTime).
    return SEEDED_AT.replace(tzinfo=None) if bind.dialect.name == "sqlite" else SEEDED_AT


def upgrade() -> None:
    ts = _ts(op.get_bind())
    op.bulk_insert(
        activity_table,
        [
            {
                **a,
                "version": 1,
                "supports_offline": True,
                "is_active": True,
                "created_at": ts,
                "updated_at": ts,
            }
            for a in ACTIVITIES
        ],
    )
    # Global change-log entries (patient_id NULL) so devices pull the catalog.
    op.bulk_insert(
        changes_table,
        [
            {
                "patient_id": None,
                "entity_type": "activity_definition",
                "entity_id": a["id"],
                "operation": "upsert",
                "changed_at": ts,
            }
            for a in ACTIVITIES
        ],
    )


def downgrade() -> None:
    ids = [a["id"] for a in ACTIVITIES]
    op.execute(changes_table.delete().where(changes_table.c.entity_id.in_(ids)))
    op.execute(activity_table.delete().where(activity_table.c.id.in_(ids)))
