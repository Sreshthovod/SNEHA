"""local conversation provider

Allows conversation_records.provider = 'local' (optional self-hosted model). Rows that
earlier stored the real provider in extra.model_provider are corrected.

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-15 14:00:00+00:00
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0007"
down_revision: str | Sequence[str] | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OLD = ["deterministic", "gemini"]
NEW = [*OLD, "local"]


def _check(values: list[str]) -> None:
    with op.batch_alter_table("conversation_records") as batch:
        batch.drop_constraint(op.f("ck_conversation_records_conversation_provider"), type_="check")
        batch.create_check_constraint(
            "conversation_provider", "provider IN (" + ", ".join(f"'{v}'" for v in values) + ")"
        )


def upgrade() -> None:
    _check(NEW)


def downgrade() -> None:
    op.execute("UPDATE conversation_records SET provider = 'deterministic' WHERE provider = 'local'")
    _check(OLD)
