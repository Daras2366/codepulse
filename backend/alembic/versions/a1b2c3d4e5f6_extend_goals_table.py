"""Extend goals table for full Goals system.

Revision ID: a1b2c3d4e5f6
Revises: 84f0e122c6c3
Create Date: 2026-09-01 09:38:00

Changes:
  - Drop old goaltype enum (DAILY/WEEKLY/MONTHLY) and recreate with 6 types
  - Drop old goalstatus enum (ACTIVE/COMPLETED/FAILED) and recreate with new statuses
  - Add new columns: platform, topic_slug, topic_name, difficulty_filter,
                     start_value, start_date, deadline, completed_at
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "84f0e122c6c3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# New enum values
NEW_GOALTYPE_VALUES = ("rating", "problems", "topic", "consistency", "contest", "placement")
NEW_GOALSTATUS_VALUES = ("active", "completed", "overdue", "paused")


def _is_postgresql(bind) -> bool:
    return bind.dialect.name == "postgresql"


def upgrade() -> None:
    bind = op.get_bind()

    if _is_postgresql(bind):
        # ----------------------------------------------------------------
        # 1. Handle goaltype enum
        # ----------------------------------------------------------------
        # Drop old default first, then alter column type
        # The old enum had uppercase values (DAILY/WEEKLY/MONTHLY) or
        # lowercase depending on the migration history.

        # Convert goals.goal_type column to text temporarily
        op.execute(
            "ALTER TABLE goals ALTER COLUMN goal_type TYPE VARCHAR(30) "
            "USING goal_type::text"
        )

        # Drop old goaltype enum type if it exists
        op.execute("DROP TYPE IF EXISTS goaltype")

        # Create new goaltype enum
        op.execute(
            "CREATE TYPE goaltype AS ENUM "
            "('rating', 'problems', 'topic', 'consistency', 'contest', 'placement')"
        )

        # Convert column back to enum, defaulting unknown old values to 'problems'
        op.execute(
            """
            ALTER TABLE goals ALTER COLUMN goal_type TYPE goaltype
            USING CASE
                WHEN lower(goal_type) IN ('rating','problems','topic','consistency','contest','placement')
                THEN lower(goal_type)::goaltype
                ELSE 'problems'::goaltype
            END
            """
        )

        # ----------------------------------------------------------------
        # 2. Handle goalstatus enum
        # ----------------------------------------------------------------
        op.execute(
            "ALTER TABLE goals ALTER COLUMN status TYPE VARCHAR(30) "
            "USING status::text"
        )

        op.execute("DROP TYPE IF EXISTS goalstatus")

        op.execute(
            "CREATE TYPE goalstatus AS ENUM "
            "('active', 'completed', 'overdue', 'paused')"
        )

        op.execute(
            """
            ALTER TABLE goals ALTER COLUMN status TYPE goalstatus
            USING CASE
                WHEN lower(status) IN ('active','completed','overdue','paused')
                THEN lower(status)::goalstatus
                WHEN lower(status) = 'failed' THEN 'overdue'::goalstatus
                ELSE 'active'::goalstatus
            END
            """
        )

    else:
        # SQLite: just update existing rows (enums stored as strings)
        bind.execute(sa.text(
            "UPDATE goals SET goal_type = 'problems' "
            "WHERE goal_type NOT IN ('rating','problems','topic','consistency','contest','placement')"
        ))
        bind.execute(sa.text(
            "UPDATE goals SET status = 'active' "
            "WHERE status NOT IN ('active','completed','overdue','paused')"
        ))

    # ----------------------------------------------------------------
    # 3. Add new columns to goals table
    # ----------------------------------------------------------------
    op.add_column("goals", sa.Column("platform", sa.String(30), nullable=True))
    op.add_column("goals", sa.Column("topic_slug", sa.String(150), nullable=True))
    op.add_column("goals", sa.Column("topic_name", sa.String(100), nullable=True))
    op.add_column("goals", sa.Column("difficulty_filter", sa.String(20), nullable=True))
    op.add_column("goals", sa.Column("start_value", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("goals", sa.Column("start_date", sa.Date(), nullable=True))
    op.add_column("goals", sa.Column("deadline", sa.Date(), nullable=True))
    op.add_column("goals", sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()

    # Remove new columns
    op.drop_column("goals", "completed_at")
    op.drop_column("goals", "deadline")
    op.drop_column("goals", "start_date")
    op.drop_column("goals", "start_value")
    op.drop_column("goals", "difficulty_filter")
    op.drop_column("goals", "topic_name")
    op.drop_column("goals", "topic_slug")
    op.drop_column("goals", "platform")

    if _is_postgresql(bind):
        # Restore old enums
        op.execute(
            "ALTER TABLE goals ALTER COLUMN goal_type TYPE VARCHAR(30) "
            "USING goal_type::text"
        )
        op.execute("DROP TYPE IF EXISTS goaltype")
        op.execute(
            "CREATE TYPE goaltype AS ENUM ('DAILY', 'WEEKLY', 'MONTHLY')"
        )
        op.execute(
            "ALTER TABLE goals ALTER COLUMN goal_type TYPE goaltype "
            "USING 'DAILY'::goaltype"
        )

        op.execute(
            "ALTER TABLE goals ALTER COLUMN status TYPE VARCHAR(30) "
            "USING status::text"
        )
        op.execute("DROP TYPE IF EXISTS goalstatus")
        op.execute(
            "CREATE TYPE goalstatus AS ENUM ('ACTIVE', 'COMPLETED', 'FAILED')"
        )
        op.execute(
            "ALTER TABLE goals ALTER COLUMN status TYPE goalstatus "
            "USING 'ACTIVE'::goalstatus"
        )
