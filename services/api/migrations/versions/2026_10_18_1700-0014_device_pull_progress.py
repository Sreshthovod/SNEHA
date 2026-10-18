"""device pull progress

`auth_sessions.last_pull_seq` / `last_pull_at`: for patient devices, how far the change log
has been sent to the phone and when. Lets caregivers see honestly whether a tiredness note
has reached the phone (GET /patients/{id}/fatigue-delivery).

Revision ID: 0014
Revises: 0013
Create Date: 2026-10-18 17:00:00+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0014"
down_revision: str | Sequence[str] | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("auth_sessions") as batch:
        batch.add_column(sa.Column("last_pull_seq", sa.BigInteger(), nullable=True))
        batch.add_column(sa.Column("last_pull_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("auth_sessions") as batch:
        batch.drop_column("last_pull_at")
        batch.drop_column("last_pull_seq")
