"""Email verification and password reset. SYNTHETIC accounts; emails are captured, not sent."""

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from app.core.config import EmailBackend, Environment, Settings, SmtpSecurity
from app.core.time import utc_now
from app.models.users import EmailToken
from tests.conftest import Outbox
from tests.helpers import PASSWORD, Api

NEW_PASSWORD = "a brand new synthetic passphrase"


def register(client: TestClient, email: str = "synthetic.mail@example.org") -> dict:
    r = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": PASSWORD,
            "full_name": "Synthetic Mail Carer",
            "role": "caregiver",
        },
    )
    assert r.status_code == 201, r.text
    return r.json()


def login(client: TestClient, email: str, password: str = PASSWORD):
    return client.post("/api/v1/auth/login", json={"email": email, "password": password})


@pytest.fixture
def required(settings: Settings) -> Settings:
    settings.require_email_verification = True
    return settings


# ---------------------------------------------------------------- verification


def test_registering_sends_a_confirmation_link(client: TestClient, outbox: Outbox) -> None:
    user = register(client)
    assert user["email_verified"] is False
    assert len(outbox) == 1
    mail = outbox[0]
    assert mail.to == "synthetic.mail@example.org"
    assert "http://localhost:5173/verify-email?token=" in mail.text
    verified = client.post("/api/v1/auth/verify-email", json={"token": outbox.link()})
    assert verified.status_code == 200 and verified.json()["email_verified"] is True
    # Single use.
    again = client.post("/api/v1/auth/verify-email", json={"token": outbox.link()})
    assert again.status_code == 400 and again.json()["error"]["code"] == "invalid_link"


def test_email_confirmation_is_not_the_clinician_check(client: TestClient, outbox: Outbox) -> None:
    r = client.post(
        "/api/v1/auth/register",
        json={
            "email": "synthetic.doc@example.org",
            "password": PASSWORD,
            "full_name": "Synthetic Doctor",
            "role": "clinician",
        },
    )
    body = client.post("/api/v1/auth/verify-email", json={"token": outbox.link()}).json()
    assert r.json()["is_verified"] is False
    assert body["email_verified"] is True and body["is_verified"] is False


def test_sign_in_waits_for_confirmation_only_when_required(
    client: TestClient, outbox: Outbox, required: Settings
) -> None:
    register(client)
    blocked = login(client, "synthetic.mail@example.org")
    assert blocked.status_code == 403
    assert blocked.json()["error"]["code"] == "email_not_verified"
    # A wrong password still says "wrong password", never "not verified".
    wrong = login(client, "synthetic.mail@example.org", "not the synthetic password")
    assert wrong.status_code == 401
    client.post("/api/v1/auth/verify-email", json={"token": outbox.link()})
    assert login(client, "synthetic.mail@example.org").status_code == 200


def test_sign_in_is_not_blocked_when_verification_is_not_required(
    client: TestClient, outbox: Outbox
) -> None:
    register(client)
    assert login(client, "synthetic.mail@example.org").status_code == 200


def test_resending_replaces_the_old_link_and_never_reveals_accounts(
    client: TestClient, outbox: Outbox
) -> None:
    register(client)
    first = outbox.link()
    r = client.post(
        "/api/v1/auth/resend-verification", json={"email": "Synthetic.Mail@example.org"}
    )
    assert r.status_code == 202 and len(outbox) == 2
    assert client.post("/api/v1/auth/verify-email", json={"token": first}).status_code == 400
    assert (
        client.post("/api/v1/auth/verify-email", json={"token": outbox.link()}).status_code == 200
    )
    # Already confirmed, or no such account: same answer, no email.
    for email in ("synthetic.mail@example.org", "nobody@example.org"):
        r = client.post("/api/v1/auth/resend-verification", json={"email": email})
        assert r.status_code == 202
    assert len(outbox) == 2


def test_expired_link_does_not_work(api: Api, client: TestClient, outbox: Outbox) -> None:
    register(client)
    token = api.db.query(EmailToken).one()
    token.expires_at = utc_now() - timedelta(minutes=1)
    api.db.commit()
    r = client.post("/api/v1/auth/verify-email", json={"token": outbox.link()})
    assert r.status_code == 400


# ---------------------------------------------------------------- password reset


def test_forgot_password_resets_and_signs_out_everywhere(
    api: Api, client: TestClient, outbox: Outbox
) -> None:
    carer = api.user()
    outbox.clear()
    assert client.get("/api/v1/auth/me", headers=carer.headers).status_code == 200
    r = client.post("/api/v1/auth/forgot-password", json={"email": carer.email})
    assert r.status_code == 202 and len(outbox) == 1
    assert "/reset-password?token=" in outbox[0].text
    assert outbox[0].to == carer.email

    done = client.post(
        "/api/v1/auth/reset-password", json={"token": outbox.link(), "password": NEW_PASSWORD}
    )
    assert done.status_code == 204
    assert client.get("/api/v1/auth/me", headers=carer.headers).status_code == 401
    assert login(client, carer.email).status_code == 401
    assert login(client, carer.email, NEW_PASSWORD).status_code == 200
    reused = client.post(
        "/api/v1/auth/reset-password", json={"token": outbox.link(), "password": NEW_PASSWORD}
    )
    assert reused.status_code == 400


def test_reset_unlocks_a_locked_account_and_confirms_the_email(
    api: Api, client: TestClient, outbox: Outbox, required: Settings
) -> None:
    register(client)
    for _ in range(5):
        login(client, "synthetic.mail@example.org", "wrong synthetic password")
    assert login(client, "synthetic.mail@example.org").status_code == 423
    client.post("/api/v1/auth/forgot-password", json={"email": "synthetic.mail@example.org"})
    client.post(
        "/api/v1/auth/reset-password", json={"token": outbox.link(), "password": NEW_PASSWORD}
    )
    assert login(client, "synthetic.mail@example.org", NEW_PASSWORD).status_code == 200


def test_forgot_password_does_not_reveal_accounts(client: TestClient, outbox: Outbox) -> None:
    r = client.post("/api/v1/auth/forgot-password", json={"email": "nobody@example.org"})
    assert r.status_code == 202 and outbox == []


def test_a_verification_link_cannot_reset_a_password(client: TestClient, outbox: Outbox) -> None:
    register(client)
    r = client.post(
        "/api/v1/auth/reset-password", json={"token": outbox.link(), "password": NEW_PASSWORD}
    )
    assert r.status_code == 400


def test_short_new_password_is_refused(api: Api, client: TestClient, outbox: Outbox) -> None:
    carer = api.user()
    client.post("/api/v1/auth/forgot-password", json={"email": carer.email})
    r = client.post(
        "/api/v1/auth/reset-password", json={"token": outbox.link(), "password": "short"}
    )
    assert r.status_code == 422


def test_one_inbox_cannot_be_flooded(client: TestClient, outbox: Outbox) -> None:
    register(client)
    outbox.clear()
    codes = [
        client.post(
            "/api/v1/auth/forgot-password", json={"email": "synthetic.mail@example.org"}
        ).status_code
        for _ in range(4)
    ]
    assert codes == [202, 202, 202, 429]
    assert len(outbox) == 3


def test_emails_and_audit_hold_no_secrets(api: Api, client: TestClient, outbox: Outbox) -> None:
    register(client)
    token = outbox.link()
    stored = api.db.query(EmailToken).one()
    assert token not in stored.token_hash and len(stored.token_hash) == 64
    assert PASSWORD not in outbox[0].text


# ---------------------------------------------------------------- configuration


def deployed(**overrides) -> Settings:
    values = {
        "environment": Environment.PRODUCTION,
        "database_url": "postgresql://synthetic:synthetic@db/sneha",
        "secret_key": "s" * 40,
        "cors_allowed_origins": ["https://dashboard.example.org"],
        "dashboard_url": "https://dashboard.example.org",
        "email_backend": EmailBackend.DISABLED,
    }
    return Settings(_env_file=None, **{**values, **overrides})


def test_deployed_settings_refuse_unsafe_email_configuration() -> None:
    assert deployed().email_backend == EmailBackend.DISABLED
    with pytest.raises(ValueError, match="SNEHA_EMAIL_BACKEND"):
        deployed(email_backend=EmailBackend.LOG)
    with pytest.raises(ValueError, match="SNEHA_SMTP_HOST"):
        deployed(email_backend=EmailBackend.SMTP)
    with pytest.raises(ValueError, match="SNEHA_SMTP_SECURITY"):
        deployed(
            email_backend=EmailBackend.SMTP,
            smtp_host="smtp.example.org",
            smtp_security=SmtpSecurity.NONE,
        )
    with pytest.raises(ValueError, match="SNEHA_DASHBOARD_URL"):
        deployed(dashboard_url="http://dashboard.example.org")
    with pytest.raises(ValueError, match="SNEHA_REQUIRE_EMAIL_VERIFICATION"):
        deployed(require_email_verification=True)
    ok = deployed(
        email_backend=EmailBackend.SMTP,
        smtp_host="smtp.example.org",
        require_email_verification=True,
        dashboard_url="https://dashboard.example.org/",
    )
    assert ok.dashboard_url == "https://dashboard.example.org"
