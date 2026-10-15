from datetime import UTC, datetime, timedelta

from tests.helpers import PAIRS_ID, PHOTO_ID, Api, iso, new_uuid, now


def test_catalog_lists_seeded_activities(api: Api) -> None:
    caregiver = api.user()
    response = api.client.get("/api/v1/activities", headers=caregiver.headers)
    assert response.status_code == 200
    slugs = {a["slug"] for a in response.json()}
    assert {"picture-pairs", "photo-recall", "story-time"} <= slugs
    assert all(a["supports_offline"] for a in response.json())
    assert api.client.get("/api/v1/activities").status_code == 401


def test_session_creation_is_idempotent_by_client_id(api: Api) -> None:
    owner = api.user()
    pid = api.patient(owner)
    body = {"id": new_uuid(), "started_at": iso(now())}
    first = api.client.post(f"/api/v1/patients/{pid}/sessions", json=body, headers=owner.headers)
    second = api.client.post(f"/api/v1/patients/{pid}/sessions", json=body, headers=owner.headers)
    assert (first.status_code, second.status_code) == (201, 200)
    assert first.json()["id"] == second.json()["id"]


def test_sessions_need_consent(api: Api) -> None:
    owner = api.user()
    pid = api.patient(owner, consent=False)
    response = api.client.post(
        f"/api/v1/patients/{pid}/sessions", json={"started_at": iso(now())}, headers=owner.headers
    )
    assert response.status_code == 409


def test_naive_and_future_timestamps_are_rejected(api: Api) -> None:
    owner = api.user()
    pid = api.patient(owner)
    url = f"/api/v1/patients/{pid}/sessions"
    naive = api.client.post(url, json={"started_at": "2026-10-01T10:00:00"}, headers=owner.headers)
    assert naive.status_code == 422
    future = api.client.post(
        url, json={"started_at": iso(now() + timedelta(days=1))}, headers=owner.headers
    )
    assert future.status_code == 422


def test_result_submission_is_idempotent_and_immutable(api: Api) -> None:
    device_owner = api.user()
    pid = api.patient(device_owner)
    device = api.pair_device(device_owner, pid)
    session = api.session(device, pid, started=now() - timedelta(minutes=30))
    url = f"/api/v1/patients/{pid}/sessions/{session['id']}/results"
    body = api.result_body()

    first = api.client.post(url, json=body, headers=device.headers)
    replay = api.client.post(url, json=body, headers=device.headers)
    changed = api.client.post(url, json={**body, "score": 0.1}, headers=device.headers)

    assert first.status_code == 201
    assert first.json()["activity_version"] == 1
    assert replay.status_code == 200
    assert replay.json() == first.json()
    assert changed.status_code == 409
    assert changed.json()["error"]["code"] == "result_conflict"
    listed = api.client.get(url, headers=device_owner.headers).json()
    assert len(listed) == 1


def test_result_validation(api: Api) -> None:
    owner = api.user()
    pid = api.patient(owner)
    session = api.session(owner, pid, started=now() - timedelta(hours=1))
    url = f"/api/v1/patients/{pid}/sessions/{session['id']}/results"
    start = now() - timedelta(minutes=10)
    cases = [
        ({"score": 1.5}, 422),
        ({"correct_count": 9, "attempt_count": 8}, 422),
        ({"completed_at": iso(start - timedelta(minutes=1))}, 422),
        ({"difficulty_level": 0}, 422),
        ({"difficulty_level": 4, "activity_id": "4b0c2d0e-5f0e-4c39-9d43-1a6f3f0a0007"}, 422),
        ({"activity_id": new_uuid()}, 422),
        ({"metrics": {"Bad Key": 1}}, 422),
        ({"metrics": {f"m{i}": i for i in range(21)}}, 422),
        ({"metrics": {"note": "free text is not allowed"}}, 422),
        ({"transcript": "should never be accepted"}, 422),
        ({"started_at": iso(now() - timedelta(hours=2)), "completed_at": iso(now())}, 422),
    ]
    for overrides, expected in cases:
        response = api.client.post(
            url, json=api.result_body(start, **overrides), headers=owner.headers
        )
        assert response.status_code == expected, (overrides, response.text)


def test_complete_session(api: Api) -> None:
    owner = api.user()
    pid = api.patient(owner)
    session = api.session(owner, pid)
    url = f"/api/v1/patients/{pid}/sessions/{session['id']}/complete"
    body = {"ended_at": iso(now()), "end_reason": "fatigue_detected"}
    done = api.client.post(url, json=body, headers=owner.headers)
    assert done.status_code == 200
    assert done.json()["status"] == "abandoned"
    assert api.client.post(url, json=body, headers=owner.headers).status_code == 200  # idempotent
    other = api.client.post(url, json={**body, "end_reason": "completed"}, headers=owner.headers)
    assert other.status_code == 409


def test_history_groups_by_patient_local_day(api: Api) -> None:
    owner = api.user()
    pid = api.patient(owner, timezone="Asia/Kolkata")
    # 2026-10-05 20:00 UTC is 2026-10-06 01:30 IST: must count on the 6th.
    late = datetime(2026, 10, 5, 20, 0, tzinfo=UTC)
    early = datetime(2026, 10, 5, 5, 0, tzinfo=UTC)
    s = api.session(owner, pid, started=early - timedelta(minutes=1))
    url = f"/api/v1/patients/{pid}/sessions/{s['id']}/results"
    for start, score in [(early, 0.5), (early + timedelta(minutes=5), 1.0), (late, 0.25)]:
        r = api.client.post(url, json=api.result_body(start, score=score), headers=owner.headers)
        assert r.status_code == 201, r.text
    api.client.post(
        url,
        json=api.result_body(late, activity_id=PHOTO_ID, abandoned=True, score=None),
        headers=owner.headers,
    )

    history = api.client.get(
        f"/api/v1/patients/{pid}/history?from=2026-10-01&to=2026-10-09", headers=owner.headers
    ).json()
    by_day = {(d["day"], d["activity_slug"]): d for d in history["days"]}
    assert by_day[("2026-10-05", "picture-pairs")]["results"] == 2
    assert by_day[("2026-10-05", "picture-pairs")]["mean_score"] == 0.75
    assert by_day[("2026-10-06", "picture-pairs")]["mean_score"] == 0.25
    assert by_day[("2026-10-06", "photo-recall")]["abandoned"] == 1
    assert by_day[("2026-10-06", "photo-recall")]["mean_score"] is None
    assert "not a medical assessment" in history["disclaimer"]


def test_history_range_validation(api: Api) -> None:
    owner = api.user()
    pid = api.patient(owner)
    url = f"/api/v1/patients/{pid}/history"
    assert (
        api.client.get(f"{url}?from=2026-10-09&to=2026-10-01", headers=owner.headers).status_code
        == 422
    )
    assert (
        api.client.get(f"{url}?from=2020-01-01&to=2026-10-01", headers=owner.headers).status_code
        == 422
    )
    assert api.client.get(url, headers=owner.headers).status_code == 422


def test_unused_constant_is_valid() -> None:
    assert PAIRS_ID != PHOTO_ID


def test_history_reports_missing_days_up_to_today(api: Api) -> None:
    from zoneinfo import ZoneInfo

    owner = api.user()
    pid = api.patient(owner)
    today = datetime.now(ZoneInfo("Asia/Kolkata")).date()
    start = today - timedelta(days=4)
    s = api.session(owner, pid, started=now() - timedelta(hours=1))
    api.client.post(
        f"/api/v1/patients/{pid}/sessions/{s['id']}/results",
        json=api.result_body(now() - timedelta(minutes=30)),
        headers=owner.headers,
    )
    h = api.client.get(
        f"/api/v1/patients/{pid}/history?from={start}&to={today + timedelta(days=3)}",
        headers=owner.headers,
    ).json()
    assert h["days_elapsed"] == 5  # future days are not "missing"
    assert h["days_with_activity"] == 1
    assert len(h["missing_days"]) == 4
    assert str(today) not in h["missing_days"]
    assert h["total_results"] == 1


def test_new_stage1_catalog_entries(api: Api) -> None:
    caregiver = api.user()
    slugs = {
        a["slug"]: a for a in api.client.get("/api/v1/activities", headers=caregiver.headers).json()
    }
    assert slugs["name-the-object"]["activity_type"] == "object_recognition"
    assert slugs["sort-into-groups"]["activity_type"] == "categorization"
    assert slugs["familiar-faces"]["uses_memory_bank"] is True
