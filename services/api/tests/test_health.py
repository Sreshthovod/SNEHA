from datetime import datetime

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.db.session import build_engine, get_engine
from app.main import create_app


def test_health_reports_service_metadata(client: TestClient) -> None:
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "SNEHA API"
    assert body["environment"] == "test"
    assert body["version"]
    assert datetime.fromisoformat(body["server_time"]).tzinfo is not None


def test_readiness_ok_when_database_migrated(client: TestClient) -> None:
    response = client.get("/api/v1/health/ready")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert {c["name"]: c["status"] for c in body["checks"]} == {
        "database": "ok",
        "migrations": "ok",
    }


def test_readiness_503_when_migrations_missing(settings: Settings, tmp_path) -> None:
    unmigrated = build_engine(f"sqlite:///{tmp_path / 'empty.db'}")
    app = create_app(settings)
    app.dependency_overrides[get_engine] = lambda: unmigrated

    with TestClient(app) as client:
        response = client.get("/api/v1/health/ready")

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "not_ready"
    migrations = next(c for c in body["checks"] if c["name"] == "migrations")
    assert migrations["status"] == "error"
    assert "alembic upgrade head" in migrations["detail"]


def test_readiness_503_when_database_unreachable(settings: Settings, tmp_path) -> None:
    # A path inside a non-existent directory cannot be opened by SQLite.
    broken = build_engine(f"sqlite:///{tmp_path / 'missing-dir' / 'db.sqlite'}")
    app = create_app(settings)
    app.dependency_overrides[get_engine] = lambda: broken

    with TestClient(app) as client:
        response = client.get("/api/v1/health/ready")

    assert response.status_code == 503
    assert response.json()["checks"] == [
        {"name": "database", "status": "error", "detail": "Database is unreachable"}
    ]


def test_request_id_is_echoed_or_generated(app: FastAPI) -> None:
    with TestClient(app) as client:
        echoed = client.get("/api/v1/health", headers={"X-Request-ID": "abc-123"})
        generated = client.get("/api/v1/health", headers={"X-Request-ID": "bad id!"})

    assert echoed.headers["X-Request-ID"] == "abc-123"
    assert generated.headers["X-Request-ID"] not in ("", "bad id!")


def test_cors_allows_configured_dashboard_origin(client: TestClient) -> None:
    response = client.options(
        "/api/v1/health",
        headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET"},
    )
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
