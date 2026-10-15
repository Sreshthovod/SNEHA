import socket
from datetime import timedelta

import pytest

from app.personalization.config import get_activity_specs
from tests.helpers import PNG_BYTES, Api, iso, now

PAIRS = "4b0c2d0e-5f0e-4c39-9d43-1a6f3f0a0001"


@pytest.fixture
def fam(api: Api):
    owner = api.user()
    pid = api.patient(owner)
    device = api.pair_device(owner, pid)
    session = api.session(device, pid, started=now() - timedelta(hours=2))
    return owner, pid, device, session


def nxt(api, actor, pid, **body):
    r = api.client.post(
        "/api/v1/activities/next", json={"patient_id": pid, **body}, headers=actor.headers
    )
    assert r.status_code == 200, r.text
    return r.json()


def play(api, actor, pid, session, rec, *, score=0.9, minutes_ago=60, available=None, **extra):
    start = now() - timedelta(minutes=minutes_ago)
    body = api.result_body(
        start,
        activity_id=rec["activity_id"],
        difficulty_level=rec["difficulty"],
        score=score,
        hint_count=0,
        recommendation_id=rec["id"],
        **extra,
    )
    r = api.client.post(
        "/api/v1/activities/result",
        json={
            "patient_id": pid,
            "session_id": session["id"],
            "result": body,
            "available_slugs": available,
        },
        headers=actor.headers,
    )
    assert r.status_code == 201, r.text
    return r.json()


def test_catalog_has_full_specs_for_every_active_activity(api: Api) -> None:
    caregiver = api.user()
    catalog = api.client.get("/api/v1/activities/catalog", headers=caregiver.headers).json()
    specs = get_activity_specs()
    assert len(catalog) == 10
    for entry in catalog:
        assert entry["slug"] in specs
        levels = [lv["level"] for lv in entry["levels"]]
        assert levels == list(range(entry["min_difficulty"], entry["max_difficulty"] + 1)), entry[
            "slug"
        ]
        assert entry["instructions"] and entry["hint"] and entry["evaluation"] and entry["stop"]
    six = {
        "photo-recall",
        "picture-pairs",
        "familiar-faces",
        "daily-sequence",
        "name-the-object",
        "sort-into-groups",
    }
    assert six <= {e["slug"] for e in catalog}


def test_recommendation_is_explained(api: Api, fam) -> None:
    _, pid, device, _ = fam
    rec = nxt(api, device, pid)
    assert rec["action"] == "activity"
    assert rec["activity_id"] and rec["difficulty"] == 1
    assert rec["reason_codes"]
    assert rec["algorithm_version"] == "1.0.0"
    assert rec["config_version"]
    assert rec["fallback"] == {"used": True, "reason": "no_history"}
    assert rec["level_parameters"] and rec["instructions"]
    assert "medical condition" in rec["disclaimer"]


def test_loop_results_change_later_recommendations(api: Api, fam) -> None:
    """recommendation → activity → result → updated recommendation (difficulty rises)."""
    _, pid, device, session = fam
    rec = nxt(api, device, pid, available_slugs=["picture-pairs"])
    assert (rec["activity_slug"], rec["difficulty"]) == ("picture-pairs", 1)

    levels = []
    for i in range(3):
        out = play(
            api, device, pid, session, rec, minutes_ago=90 - i * 5, available=["picture-pairs"]
        )
        rec = out["next"]
        levels.append(rec["difficulty"])
        assert out["result"]["recommendation_id"] is not None
    assert levels == [1, 1, 2]
    assert "DIFFICULTY_INCREASED_AFTER_COMFORTABLE_SUCCESS" in rec["reason_codes"]
    assert out["personalization"]["current_difficulty"] == 2
    assert any(s["kind"] == "activity_result" for s in rec["supporting"])


def test_results_from_offline_sync_also_affect_recommendations(api: Api, fam) -> None:
    _, pid, device, session = fam
    for i in range(3):
        api.client.post(
            f"/api/v1/patients/{pid}/sessions/{session['id']}/results",
            json=api.result_body(
                now() - timedelta(minutes=80 - i * 5), activity_id=PAIRS, score=0.95, hint_count=0
            ),
            headers=device.headers,
        )
    rec = nxt(api, device, pid, available_slugs=["picture-pairs"])
    assert rec["difficulty"] == 2


def test_fatigue_feedback_changes_next_activity(api: Api, fam) -> None:
    _, pid, device, session = fam
    rec = nxt(api, device, pid, available_slugs=["daily-sequence", "picture-pairs"])
    assert rec["activity_slug"] in {"daily-sequence", "picture-pairs"}
    out = play(api, device, pid, session, rec, score=0.6, minutes_ago=5, fatigue_reported=True)
    assert out["next"]["action"] == "break"
    assert out["next"]["break_minutes"] == 10
    assert out["next"]["activity_slug"] in {"picture-pairs", "story-time", "name-the-object"}
    assert "LOW_EFFORT_FOR_FATIGUE" in out["next"]["reason_codes"]


def test_caregiver_fatigue_observation_changes_selection(api: Api, fam) -> None:
    owner, pid, device, session = fam
    put = api.client.put(
        f"/api/v1/patients/{pid}/preferences",
        json={"interests": ["gardening"]},
        headers=owner.headers,
    )
    assert put.status_code == 200
    before = nxt(api, device, pid)
    assert before["activity_slug"] in {"sort-into-groups", "daily-sequence"}

    obs = api.client.post(
        f"/api/v1/patients/{pid}/observations",
        json={
            "observed_at": iso(now() - timedelta(minutes=30)),
            "category": "fatigue",
            "note": "Synthetic: tired",
        },
        headers=owner.headers,
    ).json()
    after = nxt(api, device, pid)
    assert after["activity_slug"] in {"picture-pairs", "story-time", "name-the-object"}
    assert after["difficulty"] == 1
    assert "RECENT_FATIGUE_OBSERVATION" in after["reason_codes"]
    support = [s for s in after["supporting"] if s["kind"] == "caregiver_observation"]
    assert support[0]["id"] == obs["id"]
    assert "Synthetic: tired" not in str(after)  # note text is never echoed


def test_stop_request_is_respected(api: Api, fam) -> None:
    _, pid, device, session = fam
    stop = nxt(api, device, pid, stop_requested=True, fatigue_reported=True)
    assert stop["action"] == "stop"
    assert stop["activity_id"] is None and stop["difficulty"] is None
    assert stop["reason_codes"] == ["STOP_REQUESTED"]

    rec = nxt(api, device, pid)
    start = now() - timedelta(minutes=10)
    r = api.client.post(
        "/api/v1/activities/result",
        json={
            "patient_id": pid,
            "session_id": session["id"],
            "stop_requested": True,
            "result": api.result_body(start, activity_id=rec["activity_id"], difficulty_level=1),
        },
        headers=device.headers,
    )
    assert r.json()["next"]["action"] == "stop"


def test_approved_interests_influence_selection(api: Api, fam) -> None:
    owner, pid, device, _ = fam
    api.client.put(
        f"/api/v1/patients/{pid}/preferences", json={"interests": ["tools"]}, headers=owner.headers
    )
    rec = nxt(api, device, pid)
    assert rec["activity_slug"] == "name-the-object"
    assert "INTEREST_MATCH" in rec["reason_codes"]


def test_memory_activity_uses_only_approved_memories(api: Api, fam) -> None:
    owner, pid, device, _ = fam
    helper = api.user()
    api.add_caregiver(owner, pid, helper)
    approved = []
    for i in range(3):
        fid = api.upload(owner, pid, PNG_BYTES).json()["id"]
        approved.append(
            api.memory(
                owner, pid, title=f"Synthetic tea garden {i}", tags=["tea"], media_file_id=fid
            )["id"]
        )
    fid = api.upload(owner, pid, PNG_BYTES).json()["id"]
    pending = api.memory(helper, pid, title="Synthetic pending", tags=["tea"], media_file_id=fid)
    api.client.put(
        f"/api/v1/patients/{pid}/preferences", json={"interests": ["tea"]}, headers=owner.headers
    )

    rec = nxt(api, device, pid, available_slugs=["photo-recall"])
    assert rec["activity_slug"] == "photo-recall"
    assert set(rec["content_refs"]["memory_item_ids"]) == set(approved)
    assert pending["id"] not in rec["content_refs"]["memory_item_ids"]
    assert "APPROVED_MEMORIES_USED" in rec["reason_codes"]


def test_memory_activity_unavailable_without_enough_memories(api: Api, fam) -> None:
    _, pid, device, _ = fam
    rec = nxt(api, device, pid, available_slugs=["photo-recall", "familiar-faces"])
    assert rec["action"] == "none"
    assert rec["fallback"]["used"] is True


def test_engine_makes_no_network_calls(api: Api, fam, monkeypatch) -> None:
    """The recommendation path must work with no internet: block all new sockets."""
    _, pid, device, session = fam

    def no_network(*args, **kwargs):
        raise AssertionError("network access attempted")

    monkeypatch.setattr(socket, "create_connection", no_network)
    monkeypatch.setattr(socket.socket, "connect", no_network)
    rec = nxt(api, device, pid)
    out = play(api, device, pid, session, rec)
    assert out["next"]["action"] == "activity"


def test_preferences_permissions_and_validation(api: Api, fam) -> None:
    owner, pid, device, _ = fam
    helper, outsider = api.user(), api.user()
    api.add_caregiver(owner, pid, helper)
    url = f"/api/v1/patients/{pid}/preferences"
    body = {
        "interests": ["Tea", " bihu ", "tea"],
        "disliked_activity_slugs": ["picture-pairs"],
        "session_minutes": 20,
    }
    out = api.client.put(url, json=body, headers=owner.headers)
    assert out.status_code == 200
    assert out.json()["interests"] == ["bihu", "tea"]
    assert api.client.get(url, headers=device.headers).status_code == 200
    assert api.client.put(url, json=body, headers=helper.headers).status_code == 403
    assert api.client.put(url, json=body, headers=device.headers).status_code == 403
    assert api.client.get(url, headers=outsider.headers).status_code == 404
    bad = api.client.put(
        url, json={"disliked_activity_slugs": ["no-such-game"]}, headers=owner.headers
    )
    assert bad.status_code == 422
    assert (
        api.client.put(url, json={"session_minutes": 2}, headers=owner.headers).status_code == 422
    )

    rec = nxt(api, device, pid)
    assert rec["activity_slug"] != "picture-pairs"


def test_progress_reflects_results(api: Api, fam) -> None:
    owner, pid, device, session = fam
    rec = nxt(api, device, pid, available_slugs=["picture-pairs"])
    for i in range(3):
        rec = play(
            api,
            device,
            pid,
            session,
            rec,
            minutes_ago=50 - i,
            engagement="enjoyed",
            available=["picture-pairs"],
        )["next"]
    progress = api.client.get(f"/api/v1/patients/{pid}/progress", headers=owner.headers).json()
    pairs = next(a for a in progress["activities"] if a["slug"] == "picture-pairs")
    assert (pairs["results"], pairs["enjoyed"], pairs["current_difficulty"]) == (3, 3, 2)
    assert progress["recent_recommendations"]
    assert "medical condition" in progress["disclaimer"]
    clinician = api.user("clinician")
    api.grant_clinician(owner, pid, clinician)
    assert (
        api.client.get(f"/api/v1/patients/{pid}/progress", headers=clinician.headers).status_code
        == 200
    )
    assert (
        api.client.get(f"/api/v1/patients/{pid}/progress", headers=device.headers).status_code
        == 200
    )


def test_outsiders_cannot_get_or_submit(api: Api, fam) -> None:
    _, pid, _, session = fam
    outsider = api.user()
    clinician = api.user("clinician")
    for actor in (outsider, clinician):
        r = api.client.post(
            "/api/v1/activities/next", json={"patient_id": pid}, headers=actor.headers
        )
        assert r.status_code == 404
        r = api.client.post(
            "/api/v1/activities/result",
            json={"patient_id": pid, "session_id": session["id"], "result": api.result_body()},
            headers=actor.headers,
        )
        assert r.status_code == 404
    other_pid = api.patient(outsider)
    r = api.client.post(
        "/api/v1/activities/next",
        json={"patient_id": other_pid, "session_id": session["id"]},
        headers=outsider.headers,
    )
    assert r.status_code == 404  # session belongs to a different patient


def test_foreign_recommendation_id_is_rejected(api: Api, fam) -> None:
    _, pid, device, session = fam
    stranger = api.user()
    other = api.patient(stranger)
    foreign = nxt(api, stranger, other)
    body = api.result_body(recommendation_id=foreign["id"])
    r = api.client.post(
        f"/api/v1/patients/{pid}/sessions/{session['id']}/results",
        json=body,
        headers=device.headers,
    )
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "unknown_recommendation"


def test_duplicate_result_submission(api: Api, fam) -> None:
    _, pid, device, session = fam
    rec = nxt(api, device, pid)
    body = {
        "patient_id": pid,
        "session_id": session["id"],
        "result": api.result_body(
            activity_id=rec["activity_id"], difficulty_level=1, recommendation_id=rec["id"]
        ),
    }
    first = api.client.post("/api/v1/activities/result", json=body, headers=device.headers)
    second = api.client.post("/api/v1/activities/result", json=body, headers=device.headers)
    assert (first.status_code, second.status_code) == (201, 200)
    assert second.json()["duplicate"] is True


def test_memory_retrieval_endpoint(api: Api, fam) -> None:
    owner, pid, device, _ = fam
    tea = api.memory(owner, pid, title="Synthetic tea estate", tags=["tea", "Assam"])
    house = api.memory(owner, pid, title="Synthetic old house", kind="place", tags=["home"])
    api.client.post(
        f"/api/v1/patients/{pid}/memory-relationships",
        json={
            "from_memory_id": tea["id"],
            "to_memory_id": house["id"],
            "relation_type": "located_at",
        },
        headers=owner.headers,
    )
    r = api.client.get(
        f"/api/v1/patients/{pid}/memories-retrieve?tags=tea", headers=device.headers
    ).json()
    assert [m["memory"]["id"] for m in r[:2]] == [tea["id"], house["id"]]
    assert r[0]["matched_tags"] == ["tea"]
    assert r[1]["via_relationship_to"] == [tea["id"]]
    assert all(m["basis"] == "stored_fact" for m in r)
