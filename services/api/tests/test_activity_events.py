"""Activity events: persisted per answer/hint/pause/decision, synced without duplicates."""

from datetime import timedelta

import pytest

from tests.helpers import PAIRS_ID, Api, iso, new_uuid, now
from tests.test_sync import push, session_mutation


@pytest.fixture
def family(api: Api):
    owner = api.user()
    pid = api.patient(owner)
    device = api.pair_device(owner, pid)
    return owner, pid, device


def event_mutation(session_id: str, seq: int, event_type: str, event_id=None, **data):
    return {
        "mutation_id": new_uuid(),
        "entity_type": "activity_event",
        "data": {
            "id": event_id or new_uuid(),
            "session_id": session_id,
            "activity_id": PAIRS_ID,
            "seq": seq,
            "event_type": event_type,
            "occurred_at": iso(now() - timedelta(minutes=15) + timedelta(seconds=seq)),
            "round_index": 0,
            "data": data,
        },
    }


def test_events_are_stored_in_order_and_replays_are_not_duplicated(api: Api, family) -> None:
    owner, pid, device = family
    s = session_mutation()
    sid = s["data"]["id"]
    events = [
        event_mutation(sid, 0, "activity_started", rounds_planned=4, difficulty=2),
        event_mutation(sid, 1, "attempt", correct=False, latency_ms=4200),
        event_mutation(sid, 2, "attempt", correct=False, latency_ms=5100),
        event_mutation(
            sid, 3, "adaptation", action="show_hint", reason_codes=["REPEATED_ERRORS_IN_ROUND"]
        ),
        event_mutation(sid, 4, "hint_auto", hint_number=1, source="system"),
    ]
    first = push(api, device, s, *events)
    assert [r["status"] for r in first.json()["results"]] == ["applied"] * 6

    # Same mutations again, and the same events under NEW mutation IDs (outbox rebuilt):
    # nothing is stored twice.
    assert {r["status"] for r in push(api, device, *events).json()["results"]} == {"duplicate"}
    renamed = [{**e, "mutation_id": new_uuid()} for e in events]
    assert {r["status"] for r in push(api, device, *renamed).json()["results"]} == {"duplicate"}

    stored = api.client.get(f"/api/v1/patients/{pid}/sessions/{sid}/events", headers=owner.headers)
    assert stored.status_code == 200
    body = stored.json()
    assert [e["seq"] for e in body] == [0, 1, 2, 3, 4]
    assert body[1]["data"] == {"correct": False, "latency_ms": 4200}
    assert body[3]["data"]["action"] == "show_hint"
    assert body[3]["data"]["reason_codes"] == ["REPEATED_ERRORS_IN_ROUND"]


def test_event_for_unknown_session_is_rejected_not_lost_silently(api: Api, family) -> None:
    _, _, device = family
    orphan = event_mutation(new_uuid(), 0, "attempt", correct=True)
    result = push(api, device, orphan).json()["results"][0]
    assert result["status"] == "rejected"
    assert "session" in result["detail"].lower()


def test_event_payload_rejects_free_text_and_unknown_values(api: Api, family) -> None:
    _, _, device = family
    s = session_mutation()
    bad_field = event_mutation(s["data"]["id"], 0, "attempt", note="patient seemed confused")
    assert push(api, device, s, bad_field).status_code == 422
    bad_action = event_mutation(s["data"]["id"], 0, "adaptation", action="diagnose")
    assert push(api, device, s, bad_action).status_code == 422
    bad_type = event_mutation(s["data"]["id"], 0, "mood_score")
    assert push(api, device, s, bad_type).status_code == 422


def test_another_patients_device_cannot_attach_events_or_read_them(api: Api, family) -> None:
    owner, pid, device = family
    s = session_mutation()
    push(api, device, s, event_mutation(s["data"]["id"], 0, "attempt", correct=True))

    other_owner = api.user()
    other_pid = api.patient(other_owner)
    other_device = api.pair_device(other_owner, other_pid)
    stolen = event_mutation(s["data"]["id"], 1, "attempt", correct=True)
    assert push(api, other_device, stolen).json()["results"][0]["status"] == "rejected"

    url = f"/api/v1/patients/{pid}/sessions/{s['data']['id']}/events"
    assert api.client.get(url, headers=other_owner.headers).status_code == 404
    # The other family's patient ID with this session ID also finds nothing.
    cross = f"/api/v1/patients/{other_pid}/sessions/{s['data']['id']}/events"
    assert api.client.get(cross, headers=other_owner.headers).status_code == 404


def test_events_record_which_approved_memories_were_used(api: Api, family) -> None:
    owner, pid, device = family
    mem = api.memory(owner, pid, title="Synthetic tea garden")
    s = session_mutation()
    sid = s["data"]["id"]
    start = event_mutation(
        sid,
        0,
        "activity_started",
        memory_ids=[mem["id"]],
        content_source="personal",
        reason_codes=["PERSONAL_PHOTOS_USED"],
    )
    answer = event_mutation(sid, 1, "attempt", correct=True, memory_id=mem["id"])
    assert [r["status"] for r in push(api, device, s, start, answer).json()["results"]] == [
        "applied"
    ] * 3
    stored = api.client.get(
        f"/api/v1/patients/{pid}/sessions/{sid}/events", headers=owner.headers
    ).json()
    assert stored[0]["data"]["memory_ids"] == [mem["id"]]
    assert stored[0]["data"]["content_source"] == "personal"
    assert stored[1]["data"]["memory_id"] == mem["id"]

    # A memory deleted while the phone was offline is still a valid reference...
    gone = event_mutation(sid, 2, "attempt", correct=True, memory_id=new_uuid())
    assert push(api, device, gone).json()["results"][0]["status"] == "applied"
    # ...but another patient's memory is refused.
    other = api.user()
    foreign = api.memory(other, api.patient(other), title="Synthetic other family")
    bad = event_mutation(sid, 3, "activity_started", memory_ids=[foreign["id"]])
    result = push(api, device, bad).json()["results"][0]
    assert result["status"] == "rejected" and "another patient" in result["detail"]
    bad_source = event_mutation(sid, 4, "activity_started", content_source="invented")
    assert push(api, device, bad_source).status_code == 422
