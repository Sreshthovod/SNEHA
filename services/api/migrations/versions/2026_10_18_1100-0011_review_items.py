"""review items

`review_items`: an automated review prompt kept for one period with a snapshot of its
evidence, awaiting a caregiver's decision (confirmed | dismissed, with who, when and why).
Clinicians only see confirmed items.

Revision ID: 0011
Revises: 0010
Create Date: 2026-10-18 11:00:00+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011"
down_revision: str | Sequence[str] | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "review_items",
        sa.Column("patient_id", sa.String(36), nullable=False),
        sa.Column("rule_id", sa.String(64), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("numbers", sa.JSON(), nullable=False),
        sa.Column("observation_ids", sa.JSON(), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("method_version", sa.String(40), nullable=False),
        sa.Column("config_version", sa.String(20), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("decided_by_id", sa.String(36), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decision_reason", sa.String(1000), nullable=True),
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "period_end >= period_start", name=op.f("ck_review_items_period_order")
        ),
        sa.CheckConstraint(
            "(status = 'awaiting_review') = (decided_at IS NULL)",
            name=op.f("ck_review_items_decision_recorded"),
        ),
        sa.CheckConstraint(
            "status IN ('awaiting_review', 'confirmed', 'dismissed')",
            name=op.f("ck_review_items_review_item_status"),
        ),
        sa.ForeignKeyConstraint(
            ["patient_id"], ["patient_profiles.id"],
            name=op.f("fk_review_items_patient_id_patient_profiles"), ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["decided_by_id"], ["users.id"],
            name=op.f("fk_review_items_decided_by_id_users"), ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_review_items")),
        sa.UniqueConstraint(
            "patient_id", "rule_id", "period_start", "period_end",
            name=op.f("uq_review_items_patient_id_rule_id_period_start_period_end"),
        ),
    )
    op.create_index("ix_review_items_patient_status", "review_items", ["patient_id", "status"])


def downgrade() -> None:
    op.drop_index("ix_review_items_patient_status", "review_items")
    op.drop_table("review_items")
