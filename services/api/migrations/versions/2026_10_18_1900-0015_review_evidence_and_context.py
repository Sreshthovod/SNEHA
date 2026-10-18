"""review item evidence and caregiver context

`review_items.evidence` (the stored records a prompt is based on, days without data, checks
that could not be made) and `review_items.context_notes` (append-only caregiver context that
never changes the decision).

Revision ID: 0015
Revises: 0014
Create Date: 2026-10-18 19:00:00+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0015"
down_revision: str | Sequence[str] | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("review_items") as batch:
        batch.add_column(sa.Column("evidence", sa.JSON(), nullable=False, server_default="{}"))
        batch.add_column(
            sa.Column("context_notes", sa.JSON(), nullable=False, server_default="[]")
        )


def downgrade() -> None:
    with op.batch_alter_table("review_items") as batch:
        batch.drop_column("context_notes")
        batch.drop_column("evidence")
