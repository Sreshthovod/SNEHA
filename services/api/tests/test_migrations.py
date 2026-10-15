import os

import pytest
from alembic import command
from alembic.script import ScriptDirectory
from sqlalchemy import inspect

from app.db.migrations import alembic_config
from app.db.session import build_engine


def _config(url: str):
    config = alembic_config(url)
    config.attributes["configure_logger"] = False
    return config


def test_single_migration_head() -> None:
    heads = ScriptDirectory.from_config(alembic_config()).get_heads()
    assert len(heads) == 1, f"Multiple Alembic heads, merge them: {heads}"


def test_upgrade_and_downgrade_on_sqlite(database_url: str) -> None:
    config = _config(database_url)
    command.upgrade(config, "head")
    engine = build_engine(database_url)
    assert "alembic_version" in inspect(engine).get_table_names()
    command.downgrade(config, "base")
    engine.dispose()


@pytest.mark.postgres
@pytest.mark.skipif(
    not os.environ.get("SNEHA_TEST_POSTGRES_URL"),
    reason="Set SNEHA_TEST_POSTGRES_URL to run migrations against PostgreSQL",
)
def test_upgrade_and_downgrade_on_postgres() -> None:
    url = os.environ["SNEHA_TEST_POSTGRES_URL"].replace("postgresql://", "postgresql+psycopg://", 1)
    config = _config(url)
    command.upgrade(config, "head")
    command.downgrade(config, "base")


def _schema_drift(url: str) -> list:
    from alembic.autogenerate import compare_metadata
    from alembic.runtime.migration import MigrationContext

    import app.models  # noqa: F401  (registers every table)
    from app.db.base import Base

    command.upgrade(_config(url), "head")
    engine = build_engine(url)
    try:
        with engine.connect() as conn:
            context = MigrationContext.configure(conn, opts={"compare_type": False})
            return compare_metadata(context, Base.metadata)
    finally:
        engine.dispose()


def test_migrations_match_the_models_on_sqlite(database_url: str) -> None:
    assert _schema_drift(database_url) == []


@pytest.mark.postgres
@pytest.mark.skipif(
    not os.environ.get("SNEHA_TEST_POSTGRES_URL"),
    reason="Set SNEHA_TEST_POSTGRES_URL to compare migrations with models on PostgreSQL",
)
def test_migrations_match_the_models_on_postgres() -> None:
    url = os.environ["SNEHA_TEST_POSTGRES_URL"].replace("postgresql://", "postgresql+psycopg://", 1)
    try:
        assert _schema_drift(url) == []
    finally:
        command.downgrade(_config(url), "base")
