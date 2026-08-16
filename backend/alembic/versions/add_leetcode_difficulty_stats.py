"""add LeetCode difficulty statistics to platform profiles

Revision ID: add_leetcode_difficulty_stats
Revises: 286a90bd2465
Create Date: 2026-08-15
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "add_leetcode_difficulty_stats"
down_revision: Union[str, Sequence[str], None] = "84f0e122c6c3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "platform_profiles",
        sa.Column(
            "solved_easy",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )

    op.add_column(
        "platform_profiles",
        sa.Column(
            "solved_medium",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )

    op.add_column(
        "platform_profiles",
        sa.Column(
            "solved_hard",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )


def downgrade() -> None:
    op.drop_column("platform_profiles", "solved_hard")
    op.drop_column("platform_profiles", "solved_medium")
    op.drop_column("platform_profiles", "solved_easy")