import pytest
from pydantic import ValidationError

from app.core.config import ConversationProvider, Environment, Settings

STRONG_SECRET = "x" * 40
PG_URL = "postgresql://sneha:pw@db.internal:5432/sneha"


def make(**kwargs) -> Settings:
    return Settings(_env_file=None, **kwargs)


def test_development_defaults_are_safe() -> None:
    settings = make()
    assert settings.environment is Environment.DEVELOPMENT
    assert settings.is_sqlite
    assert settings.conversation_provider is ConversationProvider.DETERMINISTIC
    assert not settings.gemini_configured


def test_postgres_url_is_normalised_to_psycopg_driver() -> None:
    settings = make(database_url=PG_URL)
    assert settings.database_url.startswith("postgresql+psycopg://")
    assert not settings.is_sqlite


def test_unsupported_database_scheme_is_rejected() -> None:
    with pytest.raises(ValidationError, match="SNEHA_DATABASE_URL must start with"):
        make(database_url="mysql://root@localhost/sneha")


def test_production_rejects_sqlite_and_missing_secret() -> None:
    with pytest.raises(ValidationError) as excinfo:
        make(environment="production")
    message = str(excinfo.value)
    assert "must point to PostgreSQL" in message
    assert "SNEHA_SECRET_KEY" in message


def test_production_accepts_complete_configuration() -> None:
    settings = make(
        environment="production",
        database_url=PG_URL,
        secret_key=STRONG_SECRET,
        cors_allowed_origins="https://dash.example.org",
        dashboard_url="https://dash.example.org",
        email_backend="disabled",
    )
    assert settings.environment is Environment.PRODUCTION


def test_production_rejects_wildcard_cors() -> None:
    with pytest.raises(ValidationError, match="must not contain"):
        make(
            environment="production",
            database_url=PG_URL,
            secret_key=STRONG_SECRET,
            cors_allowed_origins="*",
        )


def test_production_requires_https_origins() -> None:
    with pytest.raises(ValidationError, match="must all use https"):
        make(
            environment="production",
            database_url=PG_URL,
            secret_key=STRONG_SECRET,
            cors_allowed_origins="http://dash.example.org",
        )


def test_cors_origins_parse_from_comma_separated_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SNEHA_CORS_ALLOWED_ORIGINS", "http://a.test, http://b.test")
    assert make().cors_allowed_origins == ["http://a.test", "http://b.test"]


def test_secrets_are_not_exposed_in_repr() -> None:
    settings = make(gemini_api_key="super-secret-value")
    assert settings.gemini_configured
    assert "super-secret-value" not in repr(settings)


def test_production_rejects_sql_echo() -> None:
    with pytest.raises(ValidationError, match="SNEHA_DATABASE_ECHO"):
        make(
            environment="production",
            database_url=PG_URL,
            secret_key=STRONG_SECRET,
            cors_allowed_origins="https://dash.example.org",
            database_echo=True,
        )


def test_production_hides_interactive_docs() -> None:
    from fastapi.testclient import TestClient

    from app.main import create_app

    settings = make(
        environment="production",
        database_url=PG_URL,
        secret_key=STRONG_SECRET,
        cors_allowed_origins="https://dash.example.org",
        dashboard_url="https://dash.example.org",
        email_backend="disabled",
    )
    client = TestClient(create_app(settings))
    for path in ("/docs", "/redoc", "/openapi.json"):
        assert client.get(path).status_code == 404
    assert make().environment is Environment.DEVELOPMENT
    dev = TestClient(create_app(make()))
    assert dev.get("/openapi.json").status_code == 200
