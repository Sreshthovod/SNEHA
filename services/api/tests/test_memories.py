from app.models.files import StoredFile
from tests.helpers import Api, new_uuid


def base(pid: str) -> str:
    return f"/api/v1/patients/{pid}"


def test_manager_creates_approved_memory(api: Api) -> None:
    owner = api.user()
    pid = api.patient(owner)
    memory = api.memory(owner, pid, tags=["family", "river"], approx_year=1975)
    assert memory["status"] == "approved"
    assert memory["version"] == 1
    assert memory["reviewed_by_id"] == owner.id


def test_memory_requires_data_processing_consent(api: Api) -> None:
    owner = api.user()
    pid = api.patient(owner, consent=False)
    response = api.client.post(
        f"{base(pid)}/memories", json={"kind": "person", "title": "X"}, headers=owner.headers
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "consent_required"


def test_proposal_approval_flow(api: Api) -> None:
    owner, helper = api.user(), api.user()
    pid = api.patient(owner)
    api.add_caregiver(owner, pid, helper)
    proposal = api.memory(helper, pid, title="Synthetic wedding")
    assert proposal["status"] == "pending_approval"

    pending = api.client.get(f"{base(pid)}/memories?status=pending_approval", headers=owner.headers)
    assert [m["id"] for m in pending.json()] == [proposal["id"]]

    approved = api.client.post(
        f"{base(pid)}/memories/{proposal['id']}/approve",
        json={"expected_version": 1, "note": "Confirmed with family"},
        headers=owner.headers,
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"
    assert approved.json()["version"] == 2

    again = api.client.post(
        f"{base(pid)}/memories/{proposal['id']}/approve",
        json={"expected_version": 2},
        headers=owner.headers,
    )
    assert again.status_code == 409
    assert again.json()["error"]["code"] == "not_pending"


def test_reject(api: Api) -> None:
    owner, helper = api.user(), api.user()
    pid = api.patient(owner)
    api.add_caregiver(owner, pid, helper)
    proposal = api.memory(helper, pid)
    response = api.client.post(
        f"{base(pid)}/memories/{proposal['id']}/reject",
        json={"expected_version": 1, "note": "Not accurate"},
        headers=owner.headers,
    )
    assert response.json()["status"] == "rejected"


def test_correction_uses_optimistic_concurrency(api: Api) -> None:
    owner = api.user()
    pid = api.patient(owner)
    memory = api.memory(owner, pid)
    url = f"{base(pid)}/memories/{memory['id']}"

    ok = api.client.patch(
        url,
        json={
            "expected_version": 1,
            "title": "Synthetic aunt at the market",
            "correction_note": "Was the market",
        },
        headers=owner.headers,
    )
    assert ok.status_code == 200
    assert ok.json()["title"] == "Synthetic aunt at the market"
    assert ok.json()["version"] == 2

    stale = api.client.patch(
        url, json={"expected_version": 1, "title": "Stale"}, headers=owner.headers
    )
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "version_conflict"

    null_title = api.client.patch(
        url, json={"expected_version": 2, "title": None}, headers=owner.headers
    )
    assert null_title.status_code == 422


def test_memory_validation(api: Api) -> None:
    owner = api.user()
    pid = api.patient(owner)
    for body in [
        {"kind": "alien", "title": "X"},
        {"kind": "person", "title": ""},
        {"kind": "person", "title": "x" * 121},
        {"kind": "person", "title": "X", "tags": ["t"] * 21},
        {"kind": "person", "title": "X", "approx_year": 1800},
        {"kind": "person", "title": "X", "status": "approved"},  # cannot self-approve via body
        {"kind": "person", "title": "X", "id": "not-a-uuid"},
    ]:
        response = api.client.post(f"{base(pid)}/memories", json=body, headers=owner.headers)
        assert response.status_code == 422, body


def test_duplicate_client_id_is_409(api: Api) -> None:
    owner = api.user()
    pid = api.patient(owner)
    memory_id = new_uuid()
    api.memory(owner, pid, id=memory_id)
    response = api.client.post(
        f"{base(pid)}/memories",
        json={"id": memory_id, "kind": "person", "title": "Again"},
        headers=owner.headers,
    )
    assert response.status_code == 409


def test_delete_removes_memory_media_and_relationships(api: Api, settings) -> None:
    owner = api.user()
    pid = api.patient(owner)
    file_id = api.upload(owner, pid).json()["id"]
    memory = api.memory(owner, pid, media_file_id=file_id)
    other = api.memory(owner, pid, title="Synthetic house")
    link = api.client.post(
        f"{base(pid)}/memory-relationships",
        json={
            "from_memory_id": memory["id"],
            "to_memory_id": other["id"],
            "relation_type": "located_at",
        },
        headers=owner.headers,
    )
    assert link.status_code == 201
    stored = api.db.get(StoredFile, file_id)
    path = settings.media_root / stored.storage_key
    assert path.is_file()

    response = api.client.delete(f"{base(pid)}/memories/{memory['id']}", headers=owner.headers)
    assert response.status_code == 204
    assert (
        api.client.get(f"{base(pid)}/memories/{memory['id']}", headers=owner.headers).status_code
        == 404
    )
    assert not path.exists()
    assert (
        api.client.get(f"/api/v1/files/{file_id}/content", headers=owner.headers).status_code == 404
    )
    rels = api.client.get(f"{base(pid)}/memory-relationships", headers=owner.headers).json()
    assert rels == []


def test_media_from_another_patient_cannot_be_attached(api: Api) -> None:
    owner = api.user()
    pid, pid2 = api.patient(owner), api.patient(owner)
    file_id = api.upload(owner, pid2).json()["id"]
    response = api.client.post(
        f"{base(pid)}/memories",
        json={"kind": "person", "title": "X", "media_file_id": file_id},
        headers=owner.headers,
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_media"


def test_relationship_rules(api: Api) -> None:
    owner = api.user()
    pid = api.patient(owner)
    a, b = api.memory(owner, pid), api.memory(owner, pid, title="B")
    url = f"{base(pid)}/memory-relationships"
    body = {"from_memory_id": a["id"], "to_memory_id": b["id"], "relation_type": "related_to"}
    assert api.client.post(url, json=body, headers=owner.headers).status_code == 201
    dup = api.client.post(url, json=body, headers=owner.headers)
    assert dup.status_code == 409
    self_link = api.client.post(url, json={**body, "to_memory_id": a["id"]}, headers=owner.headers)
    assert self_link.status_code == 422


# ---------------------------------------------------------------- relationship (0012)


def test_relationship_is_for_people_and_reaches_the_phone_only_when_approved(api: Api) -> None:
    owner = api.user()
    pid = api.patient(owner)
    device = api.pair_device(owner, pid)
    base = f"/api/v1/patients/{pid}/memories"
    bad = api.client.post(
        base,
        json={"kind": "place", "title": "Synthetic garden", "relationship": "aunt"},
        headers=owner.headers,
    )
    assert bad.status_code == 422
    person = api.memory(owner, pid, title="Synthetic Mina", relationship="granddaughter")
    assert person["relationship"] == "granddaughter"

    helper = api.user()
    api.add_caregiver(owner, pid, helper)
    pending = api.memory(helper, pid, title="Synthetic cousin", relationship="cousin")
    assert pending["status"] == "pending_approval"

    pulled = api.client.get("/api/v1/sync/pull?since=0", headers=device.headers).json()
    upserts = {
        c["entity_id"]: c["data"]
        for c in pulled["changes"]
        if c["entity_type"] == "memory_item" and c["operation"] == "upsert"
    }
    assert upserts[person["id"]]["relationship"] == "granddaughter"
    assert pending["id"] not in upserts, "unapproved memories never reach the phone"

    # Re-typed as a place: the relationship goes with it; clearing works too.
    url = f"{base}/{person['id']}"
    moved = api.client.patch(
        url, json={"expected_version": 1, "kind": "place"}, headers=owner.headers
    )
    assert moved.json()["relationship"] is None
    wrong = api.client.patch(
        url, json={"expected_version": 2, "relationship": "aunt"}, headers=owner.headers
    )
    assert wrong.status_code == 422
