"""reconcile schema differences

Revision ID: 84f0e122c6c3
Revises: 286a90bd2465
Create Date: 2026-08-09 23:40:41.432046

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "84f0e122c6c3"
down_revision: Union[str, Sequence[str], None] = "286a90bd2465"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


PLATFORM_ENUM_NAME = "platform"
PLATFORM_VALUES = ("leetcode", "codeforces", "codechef", "atcoder")
LEGACY_PLATFORM_VALUES = ("LEETCODE", "CODEFORCES", "CODECHEF", "ATCODER")


def _platform_enum_values(bind) -> tuple[str, ...] | None:
    values = bind.execute(
        sa.text(
            """
            SELECT enumlabel
            FROM pg_enum
            WHERE enumtypid = to_regtype('platform')
            ORDER BY enumsortorder
            """
        )
    ).scalars().all()
    return tuple(values) if values else None


def upgrade() -> None:
    """Reconcile database objects with the current SQLAlchemy metadata."""
    bind = op.get_bind()

    # The initial migration created the shared enum with member names. Rename
    # those labels in place so existing enum columns and the new contests
    # column consistently store the Python enum's lowercase values.
    enum_values = _platform_enum_values(bind)
    if enum_values is None:
        postgresql.ENUM(*PLATFORM_VALUES, name=PLATFORM_ENUM_NAME).create(bind)
    elif enum_values == LEGACY_PLATFORM_VALUES:
        for legacy_value, value in zip(LEGACY_PLATFORM_VALUES, PLATFORM_VALUES):
            op.execute(
                sa.text(
                    "ALTER TYPE platform RENAME VALUE "
                    f"'{legacy_value}' TO '{value}'"
                )
            )
    elif enum_values != PLATFORM_VALUES:
        raise RuntimeError(
            "The PostgreSQL platform enum has unexpected labels: "
            f"{enum_values!r}"
        )

    # PostgreSQL cannot implicitly cast VARCHAR values to an enum. The
    # explicit text cast preserves existing lowercase contest platform values.
    op.execute(
        "ALTER TABLE contests "
        "ALTER COLUMN platform TYPE platform "
        "USING platform::text::platform"
    )

    op.alter_column(
        "problems",
        "problem_url",
        existing_type=sa.String(length=255),
        type_=sa.String(length=500),
        existing_nullable=False,
    )

    op.create_index(
        "ix_contest_participations_contest_id",
        "contest_participations",
        ["contest_id"],
        unique=False,
    )
    op.create_index("ix_goals_user_id", "goals", ["user_id"], unique=False)
    op.create_index(
        "ix_platform_profiles_user_id",
        "platform_profiles",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_problem_topics_problem_id",
        "problem_topics",
        ["problem_id"],
        unique=False,
    )
    op.create_index(
        "ix_submissions_contest_id",
        "submissions",
        ["contest_id"],
        unique=False,
    )
    op.create_index(
        "ix_submissions_problem_id",
        "submissions",
        ["problem_id"],
        unique=False,
    )
    op.create_index(
        "ix_user_achievements_user_id",
        "user_achievements",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    """Reverse the schema reconciliation."""
    op.drop_index("ix_user_achievements_user_id", table_name="user_achievements")
    op.drop_index("ix_submissions_problem_id", table_name="submissions")
    op.drop_index("ix_submissions_contest_id", table_name="submissions")
    op.drop_index("ix_problem_topics_problem_id", table_name="problem_topics")
    op.drop_index("ix_platform_profiles_user_id", table_name="platform_profiles")
    op.drop_index("ix_goals_user_id", table_name="goals")
    op.drop_index(
        "ix_contest_participations_contest_id",
        table_name="contest_participations",
    )

    op.alter_column(
        "problems",
        "problem_url",
        existing_type=sa.String(length=500),
        type_=sa.String(length=255),
        existing_nullable=False,
    )

    op.execute(
        "ALTER TABLE contests "
        "ALTER COLUMN platform TYPE VARCHAR(30) "
        "USING platform::text"
    )

    bind = op.get_bind()
    enum_values = _platform_enum_values(bind)
    if enum_values == PLATFORM_VALUES:
        for value, legacy_value in zip(PLATFORM_VALUES, LEGACY_PLATFORM_VALUES):
            op.execute(
                sa.text(
                    "ALTER TYPE platform RENAME VALUE "
                    f"'{value}' TO '{legacy_value}'"
                )
            )
