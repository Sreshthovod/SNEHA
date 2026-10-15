from datetime import timedelta

import pytest
from sqlalchemy import select

from app.core.security import hash_token
from app.core.time import utc_now
from app.models.users import AuthSession, User
from tests.helpers import PASSWORD, Api


def register(api: Api, **overrides):
    body = {
        "email": "synthetic.new@example.org",
        "password": PASSWORD,
        "full_name": "Synthetic New",
        "role": "caregiver",
        **overrides,
    }
    return api.client.post("/api/v1/auth/register", json=body)


def test_register_hashes_password_and_normalises_email(api: Api) -> None:
    response = register(api, email="  Synthetic.New@Example.ORG ")
    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "synthetic.new@example.org"
    assert "password" not in str(body)

    user = api.db.get(User, body["id"])
    assert user.password_hash.startswith("$argon2id$")
    assert PASSWORD not in user.password_hash


def test_register_duplicate_email_is_409(api: Api) -> None:
    assert register(api).status_code == 201
    response = register(api, email="SYNTHETIC.NEW@example.org")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "email_taken"


@pytest.mark.parametrize("role", ["admin", "patient", "superuser"])
def test_cannot_self_register_privileged_roles(api: Api, role: str) -> None:
    response = register(api, role=role)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


@pytest.mark.parametrize(
    "overrides",
    [
        {"password": "short"},
        {"email": "not-an-email"},
        {"full_name": ""},
        {"is_verified": True},  # unknown fields are rejected (no mass assignment)
    ],
)
def test_register_validates_input(api: Api, overrides) -> None:
    assert register(api, **overrides).status_code == 422


def test_login_returns_opaque_token_stored_only_as_hash(api: Api) -> None:
    register(api)
    response = api.client.post(
        "/api/v1/auth/login", json={"email": "synthetic.new@example.org", "password": PASSWORD}
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    assert len(token) >= 40

    stored = api.db.scalars(select(AuthSession.token_hash)).all()
    assert hash_token(token) in stored
    assert token not in stored


def test_login_errors_do_not_reveal_whether_account_exists(api: Api) -> None:
    register(api)
    wrong_password = api.client.post(
        "/api/v1/auth/login", json={"email": "synthetic.new@example.org", "password": "x" * 12}
    )
    unknown = api.client.post(
        "/api/v1/auth/login", json={"email": "nobody@example.org", "password": "x" * 12}
    )
    assert wrong_password.status_code == unknown.status_code == 401
    assert wrong_password.json()["error"]["message"] == unknown.json()["error"]["message"]


def test_account_locks_after_repeated_failures(api: Api) -> None:
    register(api)
    creds = {"email": "synthetic.new@example.org", "password": "wrong password!"}
    for _ in range(5):
        assert api.client.post("/api/v1/auth/login", json=creds).status_code == 401

    locked = api.client.post(
        "/api/v1/auth/login", json={"email": creds["email"], "password": PASSWORD}
    )
    assert locked.status_code == 423
    assert locked.json()["error"]["code"] == "account_locked"


def test_login_rate_limited_per_client(api: Api) -> None:
    creds = {"email": "nobody@example.org", "password": "x" * 12}
    statuses = [api.client.post("/api/v1/auth/login", json=creds).status_code for _ in range(11)]
    assert statuses[:10] == [401] * 10
    assert statuses[10] == 429


def test_me_requires_valid_bearer_token(api: Api) -> None:
    caregiver = api.user()
    assert api.client.get("/api/v1/auth/me").status_code == 401
    bad = api.client.get("/api/v1/auth/me", headers={"Authorization": "Bearer not-a-token"})
    assert bad.status_code == 401
    assert bad.headers["WWW-Authenticate"] == "Bearer"

    me = api.client.get("/api/v1/auth/me", headers=caregiver.headers)
    assert me.status_code == 200
    assert me.json()["role"] == "caregiver"


def test_logout_revokes_the_token(api: Api) -> None:
    caregiver = api.user()
    assert api.client.post("/api/v1/auth/logout", headers=caregiver.headers).status_code == 204
    assert api.client.get("/api/v1/auth/me", headers=caregiver.headers).status_code == 401


def test_expired_session_is_rejected(api: Api) -> None:
    caregiver = api.user()
    for session in api.db.scalars(select(AuthSession).where(AuthSession.user_id == caregiver.id)):
        session.expires_at = utc_now() - timedelta(seconds=1)
    api.db.commit()
    assert api.client.get("/api/v1/auth/me", headers=caregiver.headers).status_code == 401


def test_deactivated_user_cannot_use_existing_token(api: Api) -> None:
    caregiver = api.user()
    api.set_user(caregiver.id, is_active=False)
    assert api.client.get("/api/v1/auth/me", headers=caregiver.headers).status_code == 401


def test_device_pairing_issues_patient_session(api: Api) -> None:
    caregiver = api.user()
    patient_id = api.patient(caregiver)
    device = api.pair_device(caregiver, patient_id)

    me = api.client.get("/api/v1/auth/me", headers=device.headers).json()
    assert me["role"] == "patient"
    assert me["email"] is None
    profile = api.client.get(f"/api/v1/patients/{patient_id}", headers=device.headers)
    assert profile.status_code == 200
    assert profile.json()["has_paired_device"] is True


def test_pairing_code_is_single_use_and_expires(api: Api) -> None:
    caregiver = api.user()
    patient_id = api.patient(caregiver)
    code = api.client.post(
        f"/api/v1/patients/{patient_id}/pairing-codes", headers=caregiver.headers
    ).json()["code"]

    first = api.client.post("/api/v1/auth/device/pair", json={"code": code})
    second = api.client.post("/api/v1/auth/device/pair", json={"code": code})
    assert first.status_code == 200
    assert second.status_code == 401
    assert second.json()["error"]["code"] == "invalid_pairing_code"

    from app.models.patients import DevicePairingCode

    code2 = api.client.post(
        f"/api/v1/patients/{patient_id}/pairing-codes", headers=caregiver.headers
    ).json()["code"]
    for row in api.db.scalars(select(DevicePairingCode)):
        row.expires_at = utc_now() - timedelta(seconds=1)
    api.db.commit()
    assert api.client.post("/api/v1/auth/device/pair", json={"code": code2}).status_code == 401


def test_pairing_codes_are_stored_hashed(api: Api) -> None:
    from app.models.patients import DevicePairingCode

    caregiver = api.user()
    patient_id = api.patient(caregiver)
    code = api.client.post(
        f"/api/v1/patients/{patient_id}/pairing-codes", headers=caregiver.headers
    ).json()["code"]
    hashes = api.db.scalars(select(DevicePairingCode.code_hash)).all()
    assert all(code.replace("-", "") not in h for h in hashes)


def test_revoking_devices_signs_out_patient_phone(api: Api) -> None:
    caregiver = api.user()
    patient_id = api.patient(caregiver)
    device = api.pair_device(caregiver, patient_id)
    response = api.client.post(
        f"/api/v1/patients/{patient_id}/devices/revoke", headers=caregiver.headers
    )
    assert response.status_code == 204
    assert api.client.get("/api/v1/auth/me", headers=device.headers).status_code == 401
