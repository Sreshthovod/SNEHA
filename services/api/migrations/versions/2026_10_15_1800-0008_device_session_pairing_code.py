"""device sessions remember their pairing code

auth_sessions.pairing_code_id links a patient-device session to the code it was paired
with, so removing the caregiver who issued that code also signs out that phone.

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-15 18:00:00+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: str | Sequence[str] | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("auth_sessions") as batch:
        batch.add_column(sa.Column("pairing_code_id", sa.String(36), nullable=True))
        batch.create_foreign_key(
            op.f("fk_auth_sessions_pairing_code_id_device_pairing_codes"),
            "device_pairing_codes", ["pairing_code_id"], ["id"], ondelete="SET NULL",
        )
        batch.create_index(op.f("ix_auth_sessions_pairing_code_id"), ["pairing_code_id"])


def downgrade() -> None:
    with op.batch_alter_table("auth_sessions") as batch:
        batch.drop_index(op.f("ix_auth_sessions_pairing_code_id"))
        batch.drop_constraint(
            op.f("fk_auth_sessions_pairing_code_id_device_pairing_codes"), type_="foreignkey"
        )
        batch.drop_column("pairing_code_id")
