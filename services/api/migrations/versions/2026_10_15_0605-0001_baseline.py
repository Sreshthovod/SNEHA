"""baseline: empty starting revision.

Establishes the migration chain. Domain tables (users, patients, sessions, sync records)
are added from Stage 1 onwards; each lands in its own reviewed migration.


Revision ID: 0001
Revises: 
Create Date: 2026-10-15 06:05:26.519518+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0001'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
