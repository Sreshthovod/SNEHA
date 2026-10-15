import json

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.exc import OperationalError

from app.db.session import get_db
from app.models.sync import AuditEvent
from tests.helpers import PASSWORD, Api, iso, now


def test_oversized_json_body_is_413(api: Api, settings) -> None:
    caregiver = api.user()
    payload = {"display_name": "x" * (settings.max_json_body_bytes + 10)}
    response = api.client.post("/api/v1/patients", json=payload, headers=caregiver.headers)
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "content_too_large"


def test_streamed_body_without_content_length_is_limited(api: Api, settings) -> None:
    caregiver = api.user()
    chunk = b"x" * 65536
    total = settings.max_json_body_bytes // len(chunk) + 2

    def body():
        for _ in range(total):
            yield chunk

    response = api.client.post(
        "/api/v1/patients",
        content=body(),
        headers={**caregiver.headers, "Content-Type": "application/json"},
    )
    assert response.status_code == 413


def test_malformed_json_is_422_with_envelope(api: Api) -> None:
    caregiver = api.user()
    response = api.client.post(
        "/api/v1/patients",
        content=b"{not json",
        headers={**caregiver.headers, "Content-Type": "application/json"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_audit_log_never_contains_secrets_or_content(api: Api) -> None:
    owner = api.user()
    pid = api.patient(owner)
    secret_title = "Synthetic very private memory title"
    secret_note = "Synthetic private observation text"
    api.memory(owner, pid, title=secret_title, description="Synthetic secret description")
    api.client.post(
        f"/api/v1/patients/{pid}/observations",
        json={"observed_at": iso(now()), "category": "mood", "note": secret_note},
        headers=owner.headers,
    )
    code = api.client.post(f"/api/v1/patients/{pid}/pairing-codes", headers=owner.headers).json()[
        "code"
    ]
    api.client.post(
        "/api/v1/auth/login", json={"email": owner.email, "password": "wrong password x"}
    )
    token = owner.headers["Authorization"].split()[1]

    api.db.expire_all()
    events = api.db.scalars(select(AuditEvent)).all()
    assert {e.action for e in events} >= {
        "auth.register",
        "auth.login",
        "memory.create",
        "observation.create",
    }
    dump = json.dumps([[e.action, e.details, e.target_id, e.target_type] for e in events])
    for forbidden in [
        PASSWORD,
        "wrong password x",
        secret_title,
        secret_note,
        code,
        token,
        owner.email,
    ]:
        assert forbidden not in dump, forbidden


def test_database_outage_returns_503_envelope(app, api: Api) -> None:
    caregiver = api.user()

    def broken_db():
        class Broken:
            def __getattr__(self, name):
                def fail(*args, **kwargs):
                    raise OperationalError("SELECT 1", {}, Exception("connection refused"))

                return fail

        yield Broken()

    app.dependency_overrides[get_db] = broken_db
    with TestClient(app) as client:
        response = client.get("/api/v1/patients", headers=caregiver.headers)
    assert response.status_code == 503
    body = response.json()["error"]
    assert body["code"] == "database_unavailable"
    assert "connection refused" not in json.dumps(body)
    assert response.headers["Retry-After"] == "5"


def test_unexpected_errors_do_not_leak_internals(app, api: Api) -> None:
    from app.api.deps import get_principal

    def explode():
        raise RuntimeError("secret internal stack detail")

    app.dependency_overrides[get_principal] = explode
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/api/v1/auth/me")
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "internal_error"
    assert "secret internal" not in response.text


def test_cors_rejects_unknown_origins(api: Api) -> None:
    response = api.client.options(
        "/api/v1/auth/login",
        headers={"Origin": "https://evil.example.org", "Access-Control-Request-Method": "POST"},
    )
    assert "access-control-allow-origin" not in response.headers


def test_patient_creation_rejected_for_clinicians_and_devices(api: Api) -> None:
    clinician = api.user("clinician")
    body = {"display_name": "X", "preferred_language": "en", "relationship_label": "x"}
    assert (
        api.client.post("/api/v1/patients", json=body, headers=clinician.headers).status_code == 403
    )
    owner = api.user()
    device = api.pair_device(owner, api.patient(owner))
    assert api.client.post("/api/v1/patients", json=body, headers=device.headers).status_code == 403


def test_patient_profile_validation(api: Api) -> None:
    caregiver = api.user()
    base = {"display_name": "X", "preferred_language": "en", "relationship_label": "x"}
    for bad in [
        {"preferred_language": "klingon"},
        {"timezone": "Mars/Olympus"},
        {"birth_year": 1800},
        {"is_synthetic": True},
        {"display_name": "   "},
    ]:
        response = api.client.post(
            "/api/v1/patients", json={**base, **bad}, headers=caregiver.headers
        )
        assert response.status_code == 422, bad
