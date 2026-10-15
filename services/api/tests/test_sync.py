from datetime import timedelta

import pytest

from tests.helpers import PAIRS_ID, Api, iso, new_uuid, now


@pytest.fixture
def family(api: Api):
    owner = api.user()
    pid = api.patient(owner)
    device = api.pair_device(owner, pid)
    return owner, pid, device


def push(api: Api, device, *mutations, install_id=None):
    return api.client.post(
        "/api/v1/sync/push",
        json={"device_install_id": install_id or new_uuid(), "mutations": list(mutations)},
        headers=device.headers,
    )


def session_mutation(session_id=None, **data):
    start = now() - timedelta(minutes=20)
    return {
        "mutation_id": new_uuid(),
        "entity_type": "activity_session",
        "data": {
            "id": session_id or new_uuid(),
            "started_at": iso(start),
            "status": "in_progress",
            **data,
        },
    }


def result_mutation(api: Api, session_id: str, **data):
    return {
        "mutation_id": new_uuid(),
        "entity_type": "activity_result",
        "data": {
            **api.result_body(now() - timedelta(minutes=10)),
            "session_id": session_id,
            **data,
        },
    }


def test_push_session_and_result_then_replay_is_duplicate(api: Api, family) -> None:
    owner, pid, device = family
    s = session_mutation()
    r = result_mutation(api, s["data"]["id"])

    first = push(api, device, s, r)
    assert first.status_code == 200
    assert [x["status"] for x in first.json()["results"]] == ["applied", "applied"]

    replay = push(api, device, s, r)
    assert [x["status"] for x in replay.json()["results"]] == ["duplicate", "duplicate"]

    # Same records under new mutation IDs (e.g. outbox rebuilt) are also not double-counted.
    again = push(api, device, {**s, "mutation_id": new_uuid()}, {**r, "mutation_id": new_uuid()})
    assert [x["status"] for x in again.json()["results"]] == ["duplicate", "duplicate"]

    results = api.client.get(
        f"/api/v1/patients/{pid}/sessions/{s['data']['id']}/results", headers=owner.headers
    ).json()
    assert len(results) == 1


def test_one_bad_mutation_does_not_fail_the_batch(api: Api, family) -> None:
    _, _, device = family
    good = session_mutation()
    orphan = result_mutation(api, new_uuid())
    changed = result_mutation(api, good["data"]["id"])
    response = push(api, device, good, orphan, changed)
    statuses = [x["status"] for x in response.json()["results"]]
    assert statuses == ["applied", "rejected", "applied"]

    conflicting = {**changed, "mutation_id": new_uuid()}
    conflicting["data"] = {**changed["data"], "score": 0.01}
    assert push(api, device, conflicting).json()["results"][0]["status"] == "conflict"


def test_session_completion_via_sync(api: Api, family) -> None:
    owner, pid, device = family
    s = session_mutation()
    push(api, device, s)
    done = session_mutation(
        s["data"]["id"], ended_at=iso(now()), status="completed", end_reason="completed"
    )
    done["data"]["started_at"] = s["data"]["started_at"]
    assert push(api, device, done).json()["results"][0]["status"] == "applied"
    sessions = api.client.get(f"/api/v1/patients/{pid}/sessions", headers=owner.headers).json()
    assert sessions[0]["status"] == "completed"


def test_conversation_metadata_only(api: Api, family) -> None:
    _, _, device = family
    conv = {
        "mutation_id": new_uuid(),
        "entity_type": "conversation",
        "data": {
            "id": new_uuid(),
            "started_at": iso(now() - timedelta(minutes=3)),
            "language": "as",
            "provider": "deterministic",
            "turn_count": 4,
            "intents": ["greeting", "ask_time"],
        },
    }
    assert push(api, device, conv).json()["results"][0]["status"] == "applied"

    with_transcript = {**conv, "mutation_id": new_uuid()}
    with_transcript["data"] = {**conv["data"], "id": new_uuid(), "transcript": "private words"}
    assert push(api, device, with_transcript).status_code == 422

    free_text_intent = {**conv, "mutation_id": new_uuid()}
    free_text_intent["data"] = {**conv["data"], "id": new_uuid(), "intents": ["I miss my son"]}
    assert push(api, device, free_text_intent).status_code == 422


def test_personalization_last_writer_wins_and_is_pulled_back(api: Api, family) -> None:
    _, _, device = family
    t0 = now() - timedelta(hours=1)

    def mutation(ts, difficulty):
        return {
            "mutation_id": new_uuid(),
            "entity_type": "personalization_state",
            "data": {
                "activity_id": PAIRS_ID,
                "current_difficulty": difficulty,
                "rules_version": "1.0.0",
                "state": {"recent_accuracy": 0.8},
                "state_updated_at": iso(ts),
            },
        }

    assert push(api, device, mutation(t0, 3)).json()["results"][0]["status"] == "applied"
    stale = push(api, device, mutation(t0 - timedelta(minutes=5), 1)).json()["results"][0]
    assert stale["status"] == "conflict"

    pulled = api.client.get("/api/v1/sync/pull", headers=device.headers).json()
    states = [c for c in pulled["changes"] if c["entity_type"] == "personalization_state"]
    assert states[-1]["data"]["current_difficulty"] == 3


def test_pull_returns_catalog_and_only_approved_memories(api: Api, family) -> None:
    owner, pid, device = family
    helper = api.user()
    api.add_caregiver(owner, pid, helper)
    approved = api.memory(owner, pid, title="Synthetic approved")
    pending = api.memory(helper, pid, title="Synthetic pending")

    body = api.client.get("/api/v1/sync/pull?since=0", headers=device.headers).json()
    types = {c["entity_type"] for c in body["changes"]}
    assert "activity_definition" in types
    memory_changes = [c for c in body["changes"] if c["entity_type"] == "memory_item"]
    upserts = {c["entity_id"] for c in memory_changes if c["operation"] == "upsert"}
    assert approved["id"] in upserts
    assert pending["id"] not in upserts
    assert all(c["data"] is None for c in memory_changes if c["entity_id"] == pending["id"])

    # Incremental: approve the pending memory, then delete the other one.
    cursor = body["next_since"]
    api.client.post(
        f"/api/v1/patients/{pid}/memories/{pending['id']}/approve",
        json={"expected_version": 1},
        headers=owner.headers,
    )
    api.client.delete(f"/api/v1/patients/{pid}/memories/{approved['id']}", headers=owner.headers)
    delta = api.client.get(f"/api/v1/sync/pull?since={cursor}", headers=device.headers).json()
    ops = [(c["entity_id"], c["operation"]) for c in delta["changes"]]
    assert (pending["id"], "upsert") in ops
    assert (approved["id"], "delete") in ops
    assert delta["next_since"] > cursor


def test_pull_paginates(api: Api, family) -> None:
    _, _, device = family
    page = api.client.get("/api/v1/sync/pull?since=0&limit=2", headers=device.headers).json()
    assert len(page["changes"]) == 2
    assert page["has_more"] is True
    nxt = api.client.get(
        f"/api/v1/sync/pull?since={page['next_since']}&limit=2", headers=device.headers
    ).json()
    assert {c["seq"] for c in nxt["changes"]}.isdisjoint({c["seq"] for c in page["changes"]})


def test_pull_never_leaks_other_patients_changes(api: Api, family) -> None:
    _, pid, device = family
    stranger = api.user()
    other_pid = api.patient(stranger)
    secret = api.memory(stranger, other_pid, title="Synthetic other family secret")
    body = api.client.get("/api/v1/sync/pull?since=0", headers=device.headers).json()
    assert secret["id"] not in {c["entity_id"] for c in body["changes"]}


def test_sync_is_for_patient_devices_only(api: Api, family) -> None:
    owner, _, _ = family
    assert push(api, owner, session_mutation()).status_code == 403
    assert api.client.get("/api/v1/sync/pull", headers=owner.headers).status_code == 403
    assert api.client.get("/api/v1/sync/pull").status_code == 401


def test_push_requires_consent(api: Api, family) -> None:
    owner, pid, device = family
    api.consent(owner, pid, "data_processing", "withdrawn")
    response = push(api, device, session_mutation())
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "consent_required"


def test_push_batch_limits(api: Api, family) -> None:
    _, _, device = family
    assert push(api, device).status_code == 422  # empty
    too_many = [session_mutation() for _ in range(201)]
    assert push(api, device, *too_many).status_code == 422
