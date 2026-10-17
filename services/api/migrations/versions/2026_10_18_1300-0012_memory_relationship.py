"""memory relationship to the patient

`memory_items.relationship`: for person memories, how the person is related to the
patient, exactly as the caregiver states it ("granddaughter"). Lets activities give a
gentle, caregiver-sourced hint instead of guessing from free text or photos.

Revision ID: 0012
Revises: 0011
Create Date: 2026-10-18 13:00:00+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0012"
down_revision: str | Sequence[str] | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("memory_items") as batch:
        batch.add_column(sa.Column("relationship", sa.String(60), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("memory_items") as batch:
        batch.drop_column("relationship")
