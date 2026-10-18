"""email verification and password reset

`users.email_verified_at` (separate from `is_verified`, the administrator's check of a
clinician) and `email_tokens`: single-use links sent by email, stored as SHA-256 only.

Revision ID: 0016
Revises: 0015
Create Date: 2026-10-18 21:00:00+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0016"
down_revision: str | Sequence[str] | None = "0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True))
    op.create_table(
        "email_tokens",
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("purpose", sa.String(32), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "purpose IN ('verify_email', 'reset_password')",
            name=op.f("ck_email_tokens_email_token_purpose"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"],
            name=op.f("fk_email_tokens_user_id_users"), ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_email_tokens")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_email_tokens_token_hash")),
    )
    op.create_index(op.f("ix_email_tokens_user_id"), "email_tokens", ["user_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_email_tokens_user_id"), "email_tokens")
    op.drop_table("email_tokens")
    with op.batch_alter_table("users") as batch:
        batch.drop_column("email_verified_at")
