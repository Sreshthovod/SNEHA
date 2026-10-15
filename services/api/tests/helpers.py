"""Readable helpers for arranging SYNTHETIC test data through the real API.

All names, emails and records here are fictional fixtures, not real people.
"""

import itertools
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.users import User

PASSWORD = "correct horse battery staple"
PHOTO_ID = "4b0c2d0e-5f0e-4c39-9d43-1a6f3f0a0006"  # seeded "photo-recall" activity
PAIRS_ID = "4b0c2d0e-5f0e-4c39-9d43-1a6f3f0a0001"  # seeded "picture-pairs" activity

PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00"
    b"\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\xf8\xff\xff?\x00\x05\xfe\x02\xfe\xa7\x35\x81\x84"
    b"\x00\x00\x00\x00IEND\xaeB`\x82"
)

_counter = itertools.count(1)


def new_uuid() -> str:
    return str(uuid.uuid4())


def now() -> datetime:
    return datetime.now(UTC)


def iso(dt: datetime) -> str:
    return dt.isoformat()


@dataclass
class Actor:
    id: str
    email: str | None
    role: str
    headers: dict[str, str]
    patient_id: str | None = None


class Api:
    def __init__(self, client: TestClient, db: Session) -> None:
        self.client = client
        self.db = db

    # ----- accounts -----

    def user(
        self, role: str = "caregiver", *, verified: bool = True, name: str | None = None
    ) -> Actor:
        n = next(_counter)
        email = f"synthetic.{role}.{n}@example.org"
        response = self.client.post(
            "/api/v1/auth/register",
            json={
                "email": email,
                "password": PASSWORD,
                "full_name": name or f"Synthetic {role.title()} {n}",
                "role": role,
            },
        )
        assert response.status_code == 201, response.text
        user_id = response.json()["id"]
        if role == "clinician" and verified:
            self.set_user(user_id, is_verified=True)
        token = self.login(email)
        return Actor(user_id, email, role, {"Authorization": f"Bearer {token}"})

    def login(self, email: str, password: str = PASSWORD) -> str:
        response = self.client.post(
            "/api/v1/auth/login", json={"email": email, "password": password}
        )
        assert response.status_code == 200, response.text
        return response.json()["access_token"]

    def set_user(self, user_id: str, **fields) -> None:
        user = self.db.get(User, user_id)
        for key, value in fields.items():
            setattr(user, key, value)
        self.db.commit()

    def user_by_email(self, email: str) -> User:
        self.db.expire_all()
        return self.db.scalar(select(User).where(User.email == email))

    # ----- patients -----

    def patient(self, caregiver: Actor, *, consent: bool = True, **fields) -> str:
        body = {
            "display_name": "Synthetic Patient",
            "preferred_language": "as",
            "relationship_label": "daughter",
            **fields,
        }
        response = self.client.post("/api/v1/patients", json=body, headers=caregiver.headers)
        assert response.status_code == 201, response.text
        patient_id = response.json()["id"]
        if consent:
            self.consent(caregiver, patient_id, "data_processing", "granted")
        return patient_id

    def consent(self, caregiver: Actor, patient_id: str, consent_type: str, status: str) -> None:
        response = self.client.post(
            f"/api/v1/patients/{patient_id}/consents",
            json={"consent_type": consent_type, "status": status, "given_by": "patient"},
            headers=caregiver.headers,
        )
        assert response.status_code == 201, response.text

    def add_caregiver(self, manager: Actor, patient_id: str, caregiver: Actor, can_manage=False):
        response = self.client.post(
            f"/api/v1/patients/{patient_id}/caregivers",
            json={"email": caregiver.email, "relationship_label": "son", "can_manage": can_manage},
            headers=manager.headers,
        )
        assert response.status_code == 201, response.text
        return response.json()

    def grant_clinician(self, manager: Actor, patient_id: str, clinician: Actor, days: int = 30):
        self.consent(manager, patient_id, "clinician_sharing", "granted")
        response = self.client.post(
            f"/api/v1/patients/{patient_id}/clinician-grants",
            json={
                "clinician_email": clinician.email,
                "expires_at": iso(now() + timedelta(days=days)),
                "purpose": "Synthetic memory clinic follow-up",
            },
            headers=manager.headers,
        )
        assert response.status_code == 201, response.text
        return response.json()

    def pair_device(self, manager: Actor, patient_id: str) -> Actor:
        code = self.client.post(
            f"/api/v1/patients/{patient_id}/pairing-codes", headers=manager.headers
        )
        assert code.status_code == 201, code.text
        response = self.client.post(
            "/api/v1/auth/device/pair",
            json={"code": code.json()["code"], "device_name": "Test phone"},
        )
        assert response.status_code == 200, response.text
        body = response.json()
        return Actor(
            body["user"]["id"],
            None,
            "patient",
            {"Authorization": f"Bearer {body['access_token']}"},
            patient_id=patient_id,
        )

    # ----- content -----

    def memory(self, actor: Actor, patient_id: str, **fields) -> dict:
        body = {"kind": "person", "title": "Synthetic aunt at the river", **fields}
        response = self.client.post(
            f"/api/v1/patients/{patient_id}/memories", json=body, headers=actor.headers
        )
        assert response.status_code == 201, response.text
        return response.json()

    def session(self, actor: Actor, patient_id: str, started: datetime | None = None) -> dict:
        response = self.client.post(
            f"/api/v1/patients/{patient_id}/sessions",
            json={"id": new_uuid(), "started_at": iso(started or now() - timedelta(minutes=10))},
            headers=actor.headers,
        )
        assert response.status_code == 201, response.text
        return response.json()

    def result_body(self, started: datetime | None = None, **fields) -> dict:
        start = started or now() - timedelta(minutes=5)
        return {
            "id": new_uuid(),
            "activity_id": PAIRS_ID,
            "difficulty_level": 2,
            "started_at": iso(start),
            "completed_at": iso(start + timedelta(minutes=2)),
            "score": 0.75,
            "correct_count": 6,
            "attempt_count": 8,
            "hint_count": 1,
            "duration_ms": 120_000,
            **fields,
        }

    def upload(self, actor: Actor, patient_id: str, data: bytes = PNG_BYTES, name="photo.png"):
        return self.client.post(
            f"/api/v1/patients/{patient_id}/media",
            files={"file": (name, data, "image/png")},
            headers=actor.headers,
        )
