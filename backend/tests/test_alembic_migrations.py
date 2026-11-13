"""Tests for the Alembic migration chain.

Covers revision d4e5f6a7b8c9 (coach observability and feedback tables):
- the script directory resolves to exactly one head
- upgrade -> downgrade -> upgrade round-trips cleanly

Note: the full migration chain cannot run on SQLite because earlier
revisions (e.g. 286a90bd2465) use Postgres-only DDL such as
``create_unique_constraint``. This test therefore exercises the
d4e5f6a7b8c9 revision in isolation on SQLite. The Postgres-specific part of
the downgrade — dropping the ``coachfeedbackaction`` enum type — is a no-op
on SQLite and remains untested here.
"""

from pathlib import Path

from sqlalchemy import create_engine, inspect

from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory

BACKEND_DIR = Path(__file__).resolve().parent.parent
ALEMBIC_INI = BACKEND_DIR / "alembic.ini"
COACH_REVISION = "d4e5f6a7b8c9"
COACH_TABLES = {"coach_runs", "coach_recommendations", "coach_feedback"}


def _script_directory() -> ScriptDirectory:
    return ScriptDirectory.from_config(Config(str(ALEMBIC_INI)))


def test_migration_chain_has_single_head():
    heads = _script_directory().get_heads()
    assert len(heads) == 1
    assert heads[0] == COACH_REVISION


def test_coach_migration_upgrade_downgrade_upgrade():
    revision = _script_directory().get_revision(COACH_REVISION)
    assert revision is not None

    engine = create_engine("sqlite://")
    with engine.connect() as conn:
        with Operations.context(MigrationContext.configure(conn)):
            revision.module.upgrade()
            assert set(inspect(conn).get_table_names()) == COACH_TABLES

            revision.module.downgrade()
            assert set(inspect(conn).get_table_names()) == set()

            revision.module.upgrade()
            assert set(inspect(conn).get_table_names()) == COACH_TABLES
