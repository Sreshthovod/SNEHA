"""Caregiver observation workflow: create → correct (with history) → review → resolve."""

import pytest
from sqlalchemy import select

from app.models.sync import AuditEvent
from tests.helpers import Api, iso, now


@pytest.fixture
def family(api: Api):
    owner, helper = api.user(name="Synthetic Manager"), api.user(name="Synthetic Helper")
    pid = api.patient(owner)
    api.add_caregiver(owner, pid, helper, can_manage=False)
    return owner, helper, pid


def create(api: Api, actor, pid: str, note="Synthetic: tired after lunch", category="fatigue"):
    response = api.client.post(
        f"/api/v1/patients/{pid}/observations",
        json={"observed_at": iso(now()), "category": category, "note": note},
        headers=actor.headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_create_tracks_source_status_and_actor(api: Api, family) -> None:
    _, helper, pid = family
    obs = create(api, helper, pid)
    assert obs["source"] == "dashboard"
    assert obs["status"] == "open"
    assert obs["version"] == 1
    assert obs["author_id"] == helper.id
    assert obs["created_at"]


def test_correction_keeps_revision_history(api: Api, family) -> None:
    owner, helper, pid = family
    obs = create(api, helper, pid)
    url = f"/api/v1/patients/{pid}/observations/{obs['id']}"

    fixed = api.client.patch(
        url,
        json={
            "expected_version": 1,
            "note": "Synthetic: tired after a long walk",
            "reason": "Wrong cause",
        },
        headers=helper.headers,
    )
    assert fixed.status_code == 200
    assert fixed.json()["version"] == 2
    assert fixed.json()["note"] == "Synthetic: tired after a long walk"
    assert fixed.json()["updated_at"]

    again = api.client.patch(
        url,
        json={"expected_version": 2, "category": "mood", "reason": "Was mood"},
        headers=owner.headers,
    )
    assert again.status_code == 200  # managers may correct others' notes

    revisions = api.client.get(f"{url}/revisions", headers=owner.headers).json()
    assert [r["version"] for r in revisions] == [1, 2]
    assert revisions[0]["note"] == "Synthetic: tired after lunch"
    assert revisions[0]["corrected_by_id"] == helper.id
    assert revisions[0]["correction_reason"] == "Wrong cause"
    assert revisions[1]["category"] == "fatigue"
    assert revisions[1]["corrected_by_id"] == owner.id


def test_correction_rules(api: Api, family) -> None:
    owner, helper, pid = family
    obs = create(api, owner, pid)
    url = f"/api/v1/patients/{pid}/observations/{obs['id']}"
    stale = api.client.patch(
        url, json={"expected_version": 9, "note": "x", "reason": "x"}, headers=owner.headers
    )
    assert stale.status_code == 409 and stale.json()["error"]["code"] == "version_conflict"
    others = api.client.patch(
        url, json={"expected_version": 1, "note": "x", "reason": "x"}, headers=helper.headers
    )
    assert others.status_code == 403  # non-manager cannot correct someone else's note
    empty = api.client.patch(
        url, json={"expected_version": 1, "reason": "x"}, headers=owner.headers
    )
    assert empty.status_code == 422
    no_reason = api.client.patch(
        url, json={"expected_version": 1, "note": "x"}, headers=owner.headers
    )
    assert no_reason.status_code == 422


def test_review_then_resolve(api: Api, family) -> None:
    owner, helper, pid = family
    obs = create(api, helper, pid)
    url = f"/api/v1/patients/{pid}/observations/{obs['id']}"

    assert (
        api.client.post(
            f"{url}/review", json={"expected_version": 1}, headers=helper.headers
        ).status_code
        == 403
    )
    reviewed = api.client.post(
        f"{url}/review",
        json={"expected_version": 1, "note": "Spoke to family"},
        headers=owner.headers,
    )
    assert reviewed.status_code == 200
    body = reviewed.json()
    assert (
        body["status"] == "reviewed" and body["reviewed_by_id"] == owner.id and body["reviewed_at"]
    )
    twice = api.client.post(f"{url}/review", json={"expected_version": 2}, headers=owner.headers)
    assert twice.status_code == 409

    resolved = api.client.post(
        f"{url}/resolve",
        json={"expected_version": 2, "note": "Moved sessions to mornings"},
        headers=owner.headers,
    )
    assert resolved.status_code == 200
    body = resolved.json()
    assert body["status"] == "resolved" and body["resolved_by_id"] == owner.id
    assert body["resolution_note"] == "Moved sessions to mornings"

    locked = api.client.patch(
        url, json={"expected_version": 3, "note": "x", "reason": "x"}, headers=owner.headers
    )
    assert locked.status_code == 409 and locked.json()["error"]["code"] == "observation_resolved"
    assert (
        api.client.post(
            f"{url}/resolve", json={"expected_version": 3, "note": "x"}, headers=owner.headers
        ).status_code
        == 409
    )

    api.db.expire_all()
    actions = set(
        api.db.scalars(select(AuditEvent.action).where(AuditEvent.target_id == obs["id"]))
    )
    assert {
        "observation.create",
        "observation.correct",
        "observation.review",
        "observation.resolve",
    } - actions == {"observation.correct"}


def test_open_observation_can_be_resolved_directly(api: Api, family) -> None:
    owner, _, pid = family
    obs = create(api, owner, pid)
    response = api.client.post(
        f"/api/v1/patients/{pid}/observations/{obs['id']}/resolve",
        json={"expected_version": 1, "note": "No action needed"},
        headers=owner.headers,
    )
    assert response.json()["status"] == "resolved"


def test_status_filter(api: Api, family) -> None:
    owner, _, pid = family
    a, _ = create(api, owner, pid), create(api, owner, pid, category="sleep")
    api.client.post(
        f"/api/v1/patients/{pid}/observations/{a['id']}/resolve",
        json={"expected_version": 1, "note": "done"},
        headers=owner.headers,
    )
    base = f"/api/v1/patients/{pid}/observations"
    assert [
        o["id"] for o in api.client.get(f"{base}?status=resolved", headers=owner.headers).json()
    ] == [a["id"]]
    assert len(api.client.get(f"{base}?status=open", headers=owner.headers).json()) == 1
    assert api.client.get(f"{base}?status=bogus", headers=owner.headers).status_code == 422


def test_clinician_is_read_only_and_outsiders_blocked(api: Api, family) -> None:
    owner, _, pid = family
    obs = create(api, owner, pid)
    url = f"/api/v1/patients/{pid}/observations/{obs['id']}"
    clinician = api.user("clinician")
    api.grant_clinician(owner, pid, clinician)
    assert api.client.get(url, headers=clinician.headers).status_code == 200
    assert api.client.get(f"{url}/revisions", headers=clinician.headers).status_code == 200
    for method, path, body in [
        ("PATCH", url, {"expected_version": 1, "note": "x", "reason": "x"}),
        ("POST", f"{url}/review", {"expected_version": 1}),
        ("POST", f"{url}/resolve", {"expected_version": 1, "note": "x"}),
    ]:
        assert (
            api.client.request(method, path, json=body, headers=clinician.headers).status_code
            == 403
        )

    outsider = api.user()
    for method, path, body in [
        ("GET", url, None),
        ("GET", f"{url}/revisions", None),
        ("PATCH", url, {"expected_version": 1, "note": "x", "reason": "x"}),
        ("POST", f"{url}/review", {"expected_version": 1}),
        ("POST", f"{url}/resolve", {"expected_version": 1, "note": "x"}),
    ]:
        assert (
            api.client.request(method, path, json=body, headers=outsider.headers).status_code == 404
        )

    # An observation of another patient cannot be reached through this patient's URL.
    other_pid = api.patient(owner)
    wrong = api.client.get(
        f"/api/v1/patients/{other_pid}/observations/{obs['id']}", headers=owner.headers
    )
    assert wrong.status_code == 404
