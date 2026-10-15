"""Helpers for inspecting Alembic migration state at runtime."""

from pathlib import Path

from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import Engine

API_ROOT = Path(__file__).resolve().parents[2]


def alembic_config(database_url: str | None = None) -> Config:
    config = Config(str(API_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(API_ROOT / "migrations"))
    if database_url is not None:
        config.set_main_option("sqlalchemy.url", database_url)
    return config


def migration_status(engine: Engine) -> tuple[set[str], set[str]]:
    """Return (current revisions in the database, head revisions in the code)."""
    heads = set(ScriptDirectory.from_config(alembic_config()).get_heads())
    with engine.connect() as connection:
        current = set(MigrationContext.configure(connection).get_current_heads())
    return current, heads
