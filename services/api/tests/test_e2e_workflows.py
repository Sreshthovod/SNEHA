"""End-to-end backend workflows (Stage 7), exercised only through the public HTTP API.

All people, memories and notes are SYNTHETIC fixtures.
"""

from datetime import timedelta
from zoneinfo import ZoneInfo

import pytest

from tests.helpers import PNG_BYTES, Api, iso, new_uuid, now

PAIRS = "4b0c2d0e-5f0e-4c39-9d43-1a6f3f0a0001"


@pytest.fixture
def family(api: Api):
    owner = api.user(name="Synthetic Daughter")
    pid = api.patient(owner, display_name="Synthetic Grandmother", timezone="Asia/Kolkata")
    device = api.pair_device(owner, pid)
    return owner, pid, device


def next_rec(api, device, pid, **body):
    r = api.client.post(
        "/api/v1/activities/next", json={"patient_id": pid, **body}, headers=device.headers
    )
    assert r.status_code == 200, r.text
    return r.json()


def submit(api, device, pid, session_id, rec, start, *, score=0.9, available=None, **extra):
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
            "session_id": session_id,
            "result": body,
            "available_slugs": available,
        },
        headers=device.headers,
    )
    assert r.status_code == 201, r.text
    return r.json()


def test_complete_patient_activity_session(api: Api, family) -> None:
    owner, pid, device = family
    start = now() - timedelta(minutes=40)
    session = api.session(device, pid, started=start)
    rec = next_rec(api, device, pid, session_id=session["id"], available_slugs=["picture-pairs"])
    difficulties = []
    for i in range(4):
        out = submit(
            api,
            device,
            pid,
            session["id"],
            rec,
            start + timedelta(minutes=1 + i * 5),
            available=["picture-pairs"],
            engagement="enjoyed",
        )
        rec = out["next"]
        difficulties.append(rec["difficulty"])
    done = api.client.post(
        f"/api/v1/patients/{pid}/sessions/{session['id']}/complete",
        json={"ended_at": iso(now()), "end_reason": "completed"},
        headers=device.headers,
    )
    assert done.json()["status"] == "completed"
    assert difficulties[-1] == 2  # previous results raised the level
    progress = api.client.get(f"/api/v1/patients/{pid}/progress", headers=owner.headers).json()
    pairs = next(a for a in progress["activities"] if a["slug"] == "picture-pairs")
    assert pairs["results"] == 4 and pairs["enjoyed"] == 4


def test_conversation_based_activity_suggestion(api: Api, family) -> None:
    owner, pid, device = family
    approved = []
    for i in range(3):
        fid = api.upload(owner, pid, PNG_BYTES).json()["id"]
        approved.append(
            api.memory(
                owner,
                pid,
                kind="place",
                title=f"Synthetic tea garden {i}",
                tags=["tea"],
                media_file_id=fid,
            )["id"]
        )
    r = api.client.post(
        "/api/v1/conversation/analyze",
        json={
            "patient_id": pid,
            "text": "I keep thinking about the tea garden today",
            "language": "en",
            "available_slugs": ["photo-recall", "picture-pairs"],
        },
        headers=device.headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["provider"] == "deterministic"  # no cloud consent → offline-safe engine
    assert "tea" in body["understanding"]["topic_tags"]
    suggestion = body["suggestion"]
    assert suggestion["action"] == "activity"
    assert suggestion["activity_slug"] == "photo-recall"
    assert set(suggestion["content_refs"]["memory_item_ids"]) <= set(approved)
    assert {m["id"] for m in body["memories"]} <= set(approved)
    assert "{" not in body["reply"]  # never raw model JSON


def test_caregiver_memory_approval_reaches_device(api: Api, family) -> None:
    owner, pid, device = family
    proposal = api.client.post(
        f"/api/v1/patients/{pid}/memories",
        json={"kind": "event", "title": "Synthetic Bihu dance in 1975", "tags": ["bihu"]},
        headers=device.headers,
    ).json()
    assert proposal["status"] == "pending_approval"
    pulled = api.client.get("/api/v1/sync/pull?since=0", headers=device.headers).json()
    assert proposal["id"] not in {
        c["entity_id"] for c in pulled["changes"] if c["operation"] == "upsert"
    }

    pending = api.client.get(
        f"/api/v1/patients/{pid}/memories?status=pending_approval", headers=owner.headers
    ).json()
    assert [m["id"] for m in pending] == [proposal["id"]]
    approved = api.client.post(
        f"/api/v1/patients/{pid}/memories/{proposal['id']}/approve",
        json={"expected_version": 1, "note": "Synthetic: confirmed"},
        headers=owner.headers,
    )
    assert approved.json()["status"] == "approved"
    delta = api.client.get(
        f"/api/v1/sync/pull?since={pulled['next_since']}", headers=device.headers
    ).json()
    assert (proposal["id"], "upsert") in {
        (c["entity_id"], c["operation"]) for c in delta["changes"]
    }
    story = next_rec(api, device, pid, available_slugs=["story-time"])
    assert story["activity_slug"] == "story-time"
    assert proposal["id"] in story["content_refs"]["memory_item_ids"]


def test_fatigue_driven_adaptation(api: Api, family) -> None:
    owner, pid, device = family
    start = now() - timedelta(minutes=30)
    session = api.session(device, pid, started=start)
    rec = next_rec(api, device, pid, available_slugs=["daily-sequence"])
    out = submit(
        api,
        device,
        pid,
        session["id"],
        rec,
        start + timedelta(minutes=1),
        score=0.6,
        fatigue_reported=True,
    )
    assert out["next"]["action"] == "break"
    assert "LOW_EFFORT_FOR_FATIGUE" in out["next"]["reason_codes"]

    # Later, a caregiver notes tiredness: the next suggestion is low-effort at the easiest level.
    api.client.post(
        f"/api/v1/patients/{pid}/observations",
        json={
            "observed_at": iso(now() - timedelta(minutes=5)),
            "category": "fatigue",
            "note": "Synthetic: sleepy",
        },
        headers=owner.headers,
    )
    after = next_rec(api, device, pid)
    assert after["activity_slug"] in {"picture-pairs", "story-time", "name-the-object"}
    assert after["difficulty"] == 1
    assert "RECENT_FATIGUE_OBSERVATION" in after["reason_codes"]


def test_offline_recording_then_synchronisation(api: Api, family) -> None:
    owner, pid, device = family
    # Recorded on the phone while offline (client IDs, past timestamps), pushed later.
    sid = new_uuid()
    t0 = now() - timedelta(hours=5)
    mutations = [
        {
            "mutation_id": new_uuid(),
            "entity_type": "activity_session",
            "data": {
                "id": sid,
                "started_at": iso(t0),
                "ended_at": iso(t0 + timedelta(minutes=20)),
                "status": "completed",
                "end_reason": "completed",
            },
        },
    ]
    for i in range(3):
        mutations.append(
            {
                "mutation_id": new_uuid(),
                "entity_type": "activity_result",
                "data": {
                    **api.result_body(
                        t0 + timedelta(minutes=1 + i * 5),
                        activity_id=PAIRS,
                        score=0.95,
                        hint_count=0,
                    ),
                    "session_id": sid,
                },
            }
        )
    body = {"device_install_id": new_uuid(), "mutations": mutations}
    first = api.client.post("/api/v1/sync/push", json=body, headers=device.headers).json()
    assert [r["status"] for r in first["results"]] == ["applied"] * 4
    retry = api.client.post(
        "/api/v1/sync/push", json=body, headers=device.headers
    ).json()  # lost response
    assert [r["status"] for r in retry["results"]] == ["duplicate"] * 4

    rec = next_rec(api, device, pid, available_slugs=["picture-pairs"])
    assert rec["difficulty"] == 2  # offline results shape later recommendations
    # The patient's own date (Asia/Kolkata), not UTC: otherwise this failed between
    # 18:30 and 24:00 UTC, when India is already on the next day.
    today = now().astimezone(ZoneInfo("Asia/Kolkata")).date()
    analytics = api.client.get(
        f"/api/v1/patients/{pid}/analytics?from={today - timedelta(days=8)}&to={today}",
        headers=owner.headers,
    ).json()
    assert analytics["totals"]["results"] == 3


def test_clinician_report_download(api: Api, family) -> None:
    owner, pid, device = family
    start = now() - timedelta(hours=3)
    session = api.session(device, pid, started=start)
    rec = next_rec(api, device, pid)
    submit(api, device, pid, session["id"], rec, start + timedelta(minutes=2))
    clinician = api.user("clinician", name="Synthetic Dr Clinician")
    api.grant_clinician(owner, pid, clinician)

    today = now().date()
    report = api.client.post(
        f"/api/v1/patients/{pid}/reports",
        json={"period_start": str(today - timedelta(days=7)), "period_end": str(today)},
        headers=clinician.headers,
    )
    assert report.status_code == 201, report.text
    assert report.json()["status"] == "ready" and report.json()["file_id"]
    pdf = api.client.get(
        f"/api/v1/files/{report.json()['file_id']}/content", headers=clinician.headers
    )
    assert pdf.status_code == 200
    assert pdf.headers["content-type"] == "application/pdf"
    assert pdf.content.startswith(b"%PDF")

    outsider = api.user()
    blocked = api.client.get(
        f"/api/v1/files/{report.json()['file_id']}/content", headers=outsider.headers
    )
    assert blocked.status_code == 404
    device_dl = api.client.get(
        f"/api/v1/files/{report.json()['file_id']}/content", headers=device.headers
    )
    assert device_dl.status_code == 403  # patients do not see clinical-style reports
