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
