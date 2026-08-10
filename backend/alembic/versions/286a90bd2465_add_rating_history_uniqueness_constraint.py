"""add rating history uniqueness constraint

Revision ID: 286a90bd2465
Revises: 914162ea5236
Create Date: 2026-08-09 19:15:52.805989

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.

revision: str = "286a90bd2465"
down_revision: Union[str, Sequence[str], None] = "914162ea5236"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_profile_rating_contest",
        "rating_history",
        ["profile_id", "contest_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_profile_rating_contest",
        "rating_history",
        type_="unique",
    )
