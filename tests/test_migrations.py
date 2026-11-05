"""The hand-written migrations produce exactly the schema the models describe."""

from alembic.autogenerate import compare_metadata
from alembic.runtime.migration import MigrationContext
from sqlalchemy import Engine, inspect

from credence.db import Base


def test_head_migration_matches_the_models(migrated_engine: Engine) -> None:
    with migrated_engine.connect() as conn:
        context = MigrationContext.configure(conn)
        diff = compare_metadata(context, Base.metadata)
    assert diff == [], f"models and migrations disagree: {diff}"


def test_downgrade_removed_everything_before_upgrade(migrated_engine: Engine) -> None:
    # The session fixture downgraded to base first; only the two tables and
    # Alembic's own bookkeeping may exist afterwards.
    assert set(inspect(migrated_engine).get_table_names()) == {
        "alembic_version",
        "documents",
        "extractions",
    }
