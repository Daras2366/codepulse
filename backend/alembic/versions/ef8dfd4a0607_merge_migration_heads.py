"""merge migration heads

Revision ID: ef8dfd4a0607
Revises: a1b2c3d4e5f6, cc05617a00a4
Create Date: 2026-09-01 10:26:42.883489

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ef8dfd4a0607'
down_revision: Union[str, Sequence[str], None] = ('a1b2c3d4e5f6', 'cc05617a00a4')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
