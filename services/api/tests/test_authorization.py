"""Proof that callers cannot read or change patients they are not authorised for.

Every patient-scoped endpoint is exercised by "outsiders" (another caregiver, an
ungranted clinician, another patient's device, an admin). They must get 404 (no
relationship: the patient's existence is not revealed) and nothing may change.
"""

from datetime import timedelta

import pytest
from sqlalchemy import func, select

from app.core.time import utc_now
from app.models.activities import ActivityResult, ActivitySession
from app.models.care import CaregiverObservation
from app.models.memories import MemoryItem
from app.models.patients import ClinicianAccessGrant, PatientProfile
from app.models.sync import AuditEvent
from tests.helpers import Actor, Api, iso, new_uuid, now


@pytest.fixture
def world(api: Api):
    """Two families, each with a synthetic patient; plus outsiders."""
    owner = api.user(name="Synthetic Owner")
    patient_id = api.patient(owner)
    memory = api.memory(owner, patient_id)
    session = api.session(owner, patient_id)
    obs = api.client.post(
        f"/api/v1/patients/{patient_id}/observations",
        json={"observed_at": iso(now()), "category": "mood", "note": "Synthetic note"},
        headers=owner.headers,
    ).json()
    upload = api.upload(owner, patient_id).json()
    report = api.client.post(
        f"/api/v1/patients/{patient_id}/reports",
        json={"period_start": "2026-10-01", "period_end": "2026-10-08"},
        headers=owner.headers,
    ).json()

    other_caregiver = api.user(name="Synthetic Other Family")
    other_patient = api.patient(other_caregiver)
    other_device = api.pair_device(other_caregiver, other_patient)

    clinician = api.user("clinician")
    admin = api.user()
    api.set_user(admin.id, role="admin")

    return {
        "owner": owner,
        "patient_id": patient_id,
        "memory_id": memory["id"],
        "session_id": session["id"],
        "observation_id": obs["id"],
        "file_id": upload["id"],
        "report_id": report["id"],
        "outsiders": {
            "other_caregiver": other_caregiver,
            "ungranted_clinician": clinician,
            "other_patient_device": other_device,
            "admin": admin,
        },
    }


def endpoints(w) -> list[tuple[str, str, dict | None]]:
    p = w["patient_id"]
    base = f"/api/v1/patients/{p}"
    return [
        ("GET", base, None),
        ("PATCH", base, {"display_name": "Hijacked"}),
        ("POST", f"{base}/pairing-codes", None),
        ("POST", f"{base}/devices/revoke", None),
        ("GET", f"{base}/caregivers", None),
        ("POST", f"{base}/caregivers", {"email": "x@example.org", "relationship_label": "x"}),
        ("GET", f"{base}/clinician-grants", None),
        (
            "POST",
            f"{base}/clinician-grants",
            {
                "clinician_email": "x@example.org",
                "expires_at": iso(now() + timedelta(days=5)),
                "purpose": "steal",
            },
        ),
        ("GET", f"{base}/consents", None),
        (
            "POST",
            f"{base}/consents",
            {"consent_type": "cloud_ai", "status": "granted", "given_by": "patient"},
        ),
        ("GET", f"{base}/memories", None),
        ("POST", f"{base}/memories", {"kind": "person", "title": "Injected"}),
        ("GET", f"{base}/memories/{w['memory_id']}", None),
        ("PATCH", f"{base}/memories/{w['memory_id']}", {"expected_version": 1, "title": "X"}),
        ("POST", f"{base}/memories/{w['memory_id']}/approve", {"expected_version": 1}),
        ("POST", f"{base}/memories/{w['memory_id']}/reject", {"expected_version": 1}),
        ("DELETE", f"{base}/memories/{w['memory_id']}", None),
        ("GET", f"{base}/memory-relationships", None),
        ("GET", f"{base}/sessions", None),
        ("POST", f"{base}/sessions", {"started_at": iso(now())}),
        (
            "POST",
            f"{base}/sessions/{w['session_id']}/complete",
            {"ended_at": iso(now()), "end_reason": "completed"},
        ),
        ("GET", f"{base}/sessions/{w['session_id']}/results", None),
        ("POST", f"{base}/sessions/{w['session_id']}/results", "RESULT"),
        ("GET", f"{base}/history?from=2026-10-01&to=2026-10-09", None),
        ("GET", f"{base}/observations", None),
        (
            "POST",
            f"{base}/observations",
            {"observed_at": iso(now()), "category": "mood", "note": "x"},
        ),
        ("DELETE", f"{base}/observations/{w['observation_id']}", None),
        ("GET", f"{base}/routines", None),
        ("POST", f"{base}/routines", {"title": "x", "local_time": "08:00", "days_of_week": 1}),
        ("GET", f"{base}/reports", None),
        ("POST", f"{base}/reports", {"period_start": "2026-10-01", "period_end": "2026-10-08"}),
        ("GET", f"{base}/reports/{w['report_id']}", None),
        ("GET", f"/api/v1/files/{w['file_id']}/content", None),
        ("POST", f"{base}/erase", {"confirm_display_name": "Synthetic Patient"}),
    ]


def _counts(db) -> tuple:
    db.expire_all()
    return tuple(
        db.scalar(select(func.count()).select_from(m))
        for m in (
            MemoryItem,
            ActivitySession,
            ActivityResult,
            CaregiverObservation,
            ClinicianAccessGrant,
        )
    )


@pytest.mark.parametrize(
    "outsider", ["other_caregiver", "ungranted_clinician", "other_patient_device", "admin"]
)
def test_outsiders_get_404_everywhere_and_change_nothing(api: Api, world, outsider: str) -> None:
    actor: Actor = world["outsiders"][outsider]
    before = _counts(api.db)

    for method, url, body in endpoints(world):
        if body == "RESULT":
            body = api.result_body()
        response = api.client.request(method, url, json=body, headers=actor.headers)
        assert response.status_code == 404, f"{outsider} {method} {url} -> {response.status_code}"
        assert response.json()["error"]["code"] == "not_found"

    assert _counts(api.db) == before
    api.db.expire_all()
    patient = api.db.get(PatientProfile, world["patient_id"])
    assert patient.display_name == "Synthetic Patient"
    memory = api.db.get(MemoryItem, world["memory_id"])
    assert memory.title == "Synthetic aunt at the river"


def test_outsider_patient_list_excludes_other_patients(api: Api, world) -> None:
    for actor in world["outsiders"].values():
        ids = [p["id"] for p in api.client.get("/api/v1/patients", headers=actor.headers).json()]
        assert world["patient_id"] not in ids


def test_unauthenticated_requests_are_401(api: Api, world) -> None:
    for method, url, body in endpoints(world):
        if body == "RESULT":
            body = api.result_body()
        response = api.client.request(method, url, json=body)
        assert response.status_code == 401, f"{method} {url}"


def test_denials_are_audited_without_content(api: Api, world) -> None:
    actor = world["outsiders"]["other_caregiver"]
    api.client.get(f"/api/v1/patients/{world['patient_id']}/memories", headers=actor.headers)
    api.db.expire_all()
    event = api.db.scalars(
        select(AuditEvent)
        .where(AuditEvent.action == "access.denied", AuditEvent.actor_user_id == actor.id)
        .order_by(AuditEvent.id.desc())
    ).first()
    assert event is not None
    assert event.outcome == "denied"
    assert event.details == {"reason": "view_memories", "role": "caregiver"}


def test_non_managing_caregiver_is_403_for_management(api: Api, world) -> None:
    helper = api.user(name="Synthetic Helper")
    api.add_caregiver(world["owner"], world["patient_id"], helper, can_manage=False)
    base = f"/api/v1/patients/{world['patient_id']}"

    # Allowed: read, propose, observe.
    assert api.client.get(base, headers=helper.headers).status_code == 200
    proposal = api.client.post(
        f"{base}/memories", json={"kind": "place", "title": "Proposed"}, headers=helper.headers
    )
    assert proposal.status_code == 201
    assert proposal.json()["status"] == "pending_approval"

    # Forbidden: management actions.
    for method, url, body in [
        ("PATCH", base, {"display_name": "X"}),
        ("POST", f"{base}/memories/{proposal.json()['id']}/approve", {"expected_version": 1}),
        ("DELETE", f"{base}/memories/{world['memory_id']}", None),
        ("POST", f"{base}/pairing-codes", None),
        ("GET", f"{base}/clinician-grants", None),
        ("POST", f"{base}/routines", {"title": "x", "local_time": "08:00", "days_of_week": 1}),
    ]:
        response = api.client.request(method, url, json=body, headers=helper.headers)
        assert response.status_code == 403, f"{method} {url} -> {response.status_code}"


def test_revoked_caregiver_loses_access(api: Api, world) -> None:
    helper = api.user()
    rel = api.add_caregiver(world["owner"], world["patient_id"], helper)
    base = f"/api/v1/patients/{world['patient_id']}"
    assert api.client.get(base, headers=helper.headers).status_code == 200

    removed = api.client.delete(f"{base}/caregivers/{rel['id']}", headers=world["owner"].headers)
    assert removed.status_code == 204
    assert api.client.get(base, headers=helper.headers).status_code == 404


def test_cannot_remove_last_managing_caregiver(api: Api, world) -> None:
    base = f"/api/v1/patients/{world['patient_id']}"
    rels = api.client.get(f"{base}/caregivers", headers=world["owner"].headers).json()
    response = api.client.delete(
        f"{base}/caregivers/{rels[0]['id']}", headers=world["owner"].headers
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "last_manager"


# ---------- clinicians ----------


def test_clinician_with_grant_has_read_only_access_without_memories(api: Api, world) -> None:
    clinician = world["outsiders"]["ungranted_clinician"]
    api.grant_clinician(world["owner"], world["patient_id"], clinician)
    base = f"/api/v1/patients/{world['patient_id']}"

    for url in [
        base,
        f"{base}/history?from=2026-10-01&to=2026-10-09",
        f"{base}/observations",
        f"{base}/reports",
        f"{base}/sessions",
    ]:
        assert api.client.get(url, headers=clinician.headers).status_code == 200, url

    ids = [p["id"] for p in api.client.get("/api/v1/patients", headers=clinician.headers).json()]
    assert ids == [world["patient_id"]]

    for method, url, body in [
        ("GET", f"{base}/memories", None),
        ("GET", f"/api/v1/files/{world['file_id']}/content", None),
        ("PATCH", base, {"display_name": "X"}),
        (
            "POST",
            f"{base}/observations",
            {"observed_at": iso(now()), "category": "mood", "note": "x"},
        ),
        ("POST", f"{base}/sessions", {"started_at": iso(now())}),
        (
            "POST",
            f"{base}/consents",
            {"consent_type": "cloud_ai", "status": "granted", "given_by": "patient"},
        ),
    ]:
        response = api.client.request(method, url, json=body, headers=clinician.headers)
        assert response.status_code == 403, f"{method} {url} -> {response.status_code}"


def test_clinician_grant_requires_sharing_consent(api: Api, world) -> None:
    clinician = world["outsiders"]["ungranted_clinician"]
    response = api.client.post(
        f"/api/v1/patients/{world['patient_id']}/clinician-grants",
        json={
            "clinician_email": clinician.email,
            "expires_at": iso(now() + timedelta(days=5)),
            "purpose": "Synthetic review",
        },
        headers=world["owner"].headers,
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "consent_required"


def test_unverified_clinician_cannot_be_granted(api: Api, world) -> None:
    unverified = api.user("clinician", verified=False)
    api.consent(world["owner"], world["patient_id"], "clinician_sharing", "granted")
    response = api.client.post(
        f"/api/v1/patients/{world['patient_id']}/clinician-grants",
        json={
            "clinician_email": unverified.email,
            "expires_at": iso(now() + timedelta(days=5)),
            "purpose": "Synthetic review",
        },
        headers=world["owner"].headers,
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "clinician_not_verified"


def test_grant_duration_is_capped(api: Api, world) -> None:
    clinician = world["outsiders"]["ungranted_clinician"]
    api.consent(world["owner"], world["patient_id"], "clinician_sharing", "granted")
    response = api.client.post(
        f"/api/v1/patients/{world['patient_id']}/clinician-grants",
        json={
            "clinician_email": clinician.email,
            "expires_at": iso(now() + timedelta(days=400)),
            "purpose": "Synthetic review",
        },
        headers=world["owner"].headers,
    )
    assert response.status_code == 422


@pytest.mark.parametrize("how", ["expired", "revoked", "consent_withdrawn", "unverified_later"])
def test_clinician_access_ends(api: Api, world, how: str) -> None:
    clinician = world["outsiders"]["ungranted_clinician"]
    grant = api.grant_clinician(world["owner"], world["patient_id"], clinician)
    url = f"/api/v1/patients/{world['patient_id']}"
    assert api.client.get(url, headers=clinician.headers).status_code == 200

    if how == "expired":
        row = api.db.get(ClinicianAccessGrant, grant["id"])
        row.starts_at = utc_now() - timedelta(days=10)
        row.expires_at = utc_now() - timedelta(seconds=1)
        api.db.commit()
    elif how == "revoked":
        response = api.client.delete(
            f"{url}/clinician-grants/{grant['id']}", headers=world["owner"].headers
        )
        assert response.status_code == 204
    elif how == "consent_withdrawn":
        api.consent(world["owner"], world["patient_id"], "clinician_sharing", "withdrawn")
    else:
        api.set_user(clinician.id, is_verified=False)

    assert api.client.get(url, headers=clinician.headers).status_code == 404
    assert api.client.get("/api/v1/patients", headers=clinician.headers).json() == []


# ---------- patient devices ----------


def test_patient_device_sees_only_own_approved_memories(api: Api, world) -> None:
    owner, patient_id = world["owner"], world["patient_id"]
    helper = api.user()
    api.add_caregiver(owner, patient_id, helper)
    pending = api.memory(helper, patient_id, title="Pending synthetic memory")
    device = api.pair_device(owner, patient_id)

    memories = api.client.get(f"/api/v1/patients/{patient_id}/memories", headers=device.headers)
    titles = [m["title"] for m in memories.json()]
    assert titles == ["Synthetic aunt at the river"]
    hidden = api.client.get(
        f"/api/v1/patients/{patient_id}/memories/{pending['id']}", headers=device.headers
    )
    assert hidden.status_code == 404


def test_patient_device_cannot_read_history_or_observations(api: Api, world) -> None:
    device = api.pair_device(world["owner"], world["patient_id"])
    base = f"/api/v1/patients/{world['patient_id']}"
    for url in [
        f"{base}/observations",
        f"{base}/history?from=2026-10-01&to=2026-10-02",
        f"{base}/reports",
    ]:
        assert api.client.get(url, headers=device.headers).status_code == 403, url


def test_result_cannot_be_attached_to_another_patients_session(api: Api, world) -> None:
    """Patient IDs in URLs are checked against the record, not trusted."""
    other = world["outsiders"]["other_caregiver"]
    other_patient = api.client.get("/api/v1/patients", headers=other.headers).json()[0]["id"]
    response = api.client.post(
        f"/api/v1/patients/{other_patient}/sessions/{world['session_id']}/results",
        json=api.result_body(),
        headers=other.headers,
    )
    assert response.status_code == 404
    assert response.json()["error"]["message"] == "Session not found."


def test_client_supplied_session_id_cannot_hijack_existing_session(api: Api, world) -> None:
    other = world["outsiders"]["other_caregiver"]
    other_patient = api.client.get("/api/v1/patients", headers=other.headers).json()[0]["id"]
    response = api.client.post(
        f"/api/v1/patients/{other_patient}/sessions",
        json={"id": world["session_id"], "started_at": iso(now())},
        headers=other.headers,
    )
    assert response.status_code == 409
    api.db.expire_all()
    assert api.db.get(ActivitySession, world["session_id"]).patient_id == world["patient_id"]


def test_malformed_patient_id_is_rejected(api: Api, world) -> None:
    response = api.client.get("/api/v1/patients/../../etc", headers=world["owner"].headers)
    assert response.status_code in (404, 422)
    response = api.client.get("/api/v1/patients/not-a-uuid", headers=world["owner"].headers)
    assert response.status_code == 422
    unknown = api.client.get(f"/api/v1/patients/{new_uuid()}", headers=world["owner"].headers)
    assert unknown.status_code == 404


def test_positive_control_owner_can_read_every_endpoint(api: Api, world) -> None:
    """Guards against the outsider test passing vacuously (e.g. every URL being wrong)."""
    for method, url, _ in endpoints(world):
        if method != "GET":
            continue
        response = api.client.get(url, headers=world["owner"].headers)
        assert response.status_code == 200, f"owner GET {url} -> {response.status_code}"
