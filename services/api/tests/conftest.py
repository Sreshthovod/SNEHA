"""Test fixtures.

By default every test gets a fresh, fully migrated SQLite database. Set
SNEHA_TEST_POSTGRES_URL to run the SAME suite against PostgreSQL instead
(the public schema is dropped and re-migrated per test).
"""

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session

from app.core.config import Environment, Settings, get_settings
from app.core.rate_limit import login_limiter, pairing_limiter
from app.db.migrations import alembic_config
from app.db.session import build_engine, get_engine, get_sessionmaker
from app.main import create_app

POSTGRES_URL = os.environ.get("SNEHA_TEST_POSTGRES_URL")


def _normalise(url: str) -> str:
    return url.replace("postgresql://", "postgresql+psycopg://", 1)


@pytest.fixture
def database_url(tmp_path: Path) -> str:
    if POSTGRES_URL:
        url = _normalise(POSTGRES_URL)
        engine = create_engine(url)
        with engine.begin() as conn:
            conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
            conn.execute(text("CREATE SCHEMA public"))
        engine.dispose()
        return url
    return f"sqlite:///{tmp_path / 'test.db'}"


@pytest.fixture
def settings(database_url: str, tmp_path: Path) -> Settings:
    return Settings(
        _env_file=None,
        environment=Environment.TEST,
        database_url=database_url,
        media_root=tmp_path / "media",
    )


@pytest.fixture
def migrated_engine(database_url: str) -> Iterator[Engine]:
    config = alembic_config(database_url)
    config.attributes["configure_logger"] = False
    command.upgrade(config, "head")
    engine = build_engine(database_url)
    yield engine
    engine.dispose()


@pytest.fixture(autouse=True)
def _reset_rate_limits() -> None:
    login_limiter.reset()
    pairing_limiter.reset()


@pytest.fixture
def app(settings: Settings, migrated_engine: Engine) -> FastAPI:
    from sqlalchemy.orm import sessionmaker

    factory = sessionmaker(bind=migrated_engine, autoflush=False, expire_on_commit=False)

    def _db() -> Iterator[Session]:
        session = factory()
        try:
            yield session
        finally:
            session.close()

    from app.db.session import get_db

    application = create_app(settings)
    application.dependency_overrides[get_settings] = lambda: settings
    application.dependency_overrides[get_engine] = lambda: migrated_engine
    application.dependency_overrides[get_db] = _db
    application.dependency_overrides[get_sessionmaker] = lambda: factory
    return application


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def db(migrated_engine: Engine) -> Iterator[Session]:
    """Direct database access for arranging state the API cannot (e.g. verifying clinicians)."""
    with Session(migrated_engine, expire_on_commit=False) as session:
        yield session


@pytest.fixture
def api(client: TestClient, db: Session):
    from tests.helpers import Api

    return Api(client, db)
