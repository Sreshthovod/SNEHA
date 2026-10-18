"""Caregiver fatigue: a level that changes what happens next, synced to and from the phone."""

from datetime import timedelta

import pytest

from tests.helpers import Api, iso, new_uuid, now
from tests.test_sync import push


@pytest.fixture
def family(api: Api):
    owner = api.user()
    pid = api.patient(owner)
    device = api.pair_device(owner, pid)
    return owner, pid, device


def next_rec(api: Api, actor, pid: str, **body) -> dict:
    response = api.client.post(
        "/api/v1/activities/next", json={"patient_id": pid, **body}, headers=actor.headers
    )
    assert response.status_code == 200, response.text
    return response.json()


def observe(api: Api, owner, pid: str, **fields):
    return api.client.post(
        f"/api/v1/patients/{pid}/observations",
        json={
            "observed_at": iso(now() - timedelta(minutes=5)),
            "category": "fatigue",
            "note": "Synthetic: dozing off",
            **fields,
        },
        headers=owner.headers,
    )


def pull(api: Api, device, since: int = 0) -> list[dict]:
    response = api.client.get(f"/api/v1/sync/pull?since={since}", headers=device.headers)
    assert response.status_code == 200
    return response.json()["changes"]


def test_level_is_only_allowed_on_fatigue_observations(api: Api, family) -> None:
    owner, pid, _ = family
    assert observe(api, owner, pid, category="mood", fatigue_level="mild").status_code == 422
    assert observe(api, owner, pid, fatigue_level="exhausted").status_code == 422
    ok = observe(api, owner, pid, fatigue_level="mild")
    assert ok.status_code == 201
    assert ok.json()["fatigue_level"] == "mild"


def test_severe_caregiver_report_means_a_rest_mild_means_easier(api: Api, family) -> None:
    owner, pid, device = family
    before = next_rec(api, device, pid)
    assert before["action"] == "activity"

    observe(api, owner, pid, fatigue_level="mild")
    mild = next_rec(api, device, pid)
    assert mild["action"] == "activity"
    assert mild["difficulty"] == 1
    assert "RECENT_FATIGUE_OBSERVATION" in mild["reason_codes"]
    assert "LOW_EFFORT_FOR_FATIGUE" in mild["reason_codes"]

    observe(api, owner, pid, fatigue_level="severe")
    severe = next_rec(api, device, pid)
    assert severe["action"] == "break"
    assert "CAREGIVER_REPORTED_SEVERE_FATIGUE" in severe["reason_codes"]
    assert severe["break_minutes"] == 10


def test_report_from_the_phone_becomes_a_fatigue_observation(api: Api, family) -> None:
    owner, pid, device = family
    report_id = new_uuid()
    mutation = {
        "mutation_id": new_uuid(),
        "entity_type": "fatigue_report",
        "data": {"id": report_id, "level": "severe", "reported_at": iso(now())},
    }
    assert push(api, device, mutation).json()["results"][0]["status"] == "applied"
    # Replayed (also under a new mutation ID): stored once.
    assert push(api, device, mutation).json()["results"][0]["status"] == "duplicate"
    renamed = {**mutation, "mutation_id": new_uuid()}
    assert push(api, device, renamed).json()["results"][0]["status"] == "duplicate"

    observations = api.client.get(
        f"/api/v1/patients/{pid}/observations", headers=owner.headers
    ).json()
    assert len(observations) == 1
    obs = observations[0]
    assert obs["id"] == report_id
    assert obs["category"] == "fatigue"
    assert obs["fatigue_level"] == "severe"
    assert obs["source"] == "device"
    assert "caregiver" in obs["note"]

    # And the server engine respects it straight away.
    assert next_rec(api, device, pid)["action"] == "break"


def test_phone_report_payload_has_no_free_text_and_no_future_times(api: Api, family) -> None:
    _, _, device = family
    with_note = {
        "mutation_id": new_uuid(),
        "entity_type": "fatigue_report",
        "data": {"id": new_uuid(), "level": "mild", "reported_at": iso(now()), "note": "x"},
    }
    assert push(api, device, with_note).status_code == 422
    future = {
        "mutation_id": new_uuid(),
        "entity_type": "fatigue_report",
        "data": {"id": new_uuid(), "level": "mild", "reported_at": iso(now() + timedelta(days=1))},
    }
    assert push(api, device, future).json()["results"][0]["status"] == "rejected"


def test_phone_pulls_fatigue_level_and_time_but_never_the_note(api: Api, family) -> None:
    owner, pid, device = family
    obs = observe(api, owner, pid, fatigue_level="severe", note="Synthetic: private detail").json()
    api.client.post(
        f"/api/v1/patients/{pid}/observations",
        json={"observed_at": iso(now()), "category": "mood", "note": "Synthetic: cheerful"},
        headers=owner.headers,
    )
    changes = [c for c in pull(api, device) if c["entity_type"] == "fatigue_report"]
    assert len(changes) == 1, "only fatigue observations reach the phone"
    data = changes[0]["data"]
    assert data == {
        "id": obs["id"],
        "level": "severe",
        "observed_at": data["observed_at"],
        "source": "dashboard",
    }
    assert "private" not in str(changes)

    # Re-categorised away from fatigue → the phone is told to forget it.
    cursor = max(c["seq"] for c in pull(api, device))
    api.client.patch(
        f"/api/v1/patients/{pid}/observations/{obs['id']}",
        json={"expected_version": 1, "category": "mood", "reason": "Synthetic: wrong category"},
        headers=owner.headers,
    )
    later = [c for c in pull(api, device, cursor) if c["entity_type"] == "fatigue_report"]
    assert [c["operation"] for c in later] == ["delete"]
    stored = api.client.get(
        f"/api/v1/patients/{pid}/observations/{obs['id']}", headers=owner.headers
    ).json()
    assert stored["fatigue_level"] is None


def test_another_familys_phone_never_receives_the_report(api: Api, family) -> None:
    owner, pid, _ = family
    observe(api, owner, pid, fatigue_level="severe")
    other_owner = api.user()
    other_pid = api.patient(other_owner)
    other_device = api.pair_device(other_owner, other_pid)
    assert [c for c in pull(api, other_device) if c["entity_type"] == "fatigue_report"] == []


def test_caregiver_very_tired_on_the_phone_counts_once_in_analytics(api: Api) -> None:
    """The phone ends the session (fatigue_detected) AND stores the caregiver's report as an
    observation. That is one tiredness signal, not two."""
    from datetime import time

    from app.analytics.service import summarise
    from app.models.patients import PatientProfile
    from tests.analytics_fixtures import PERIOD_END, PERIOD_START, R, observe, seed

    owner = api.user()
    pid = api.patient(owner, timezone="Asia/Kolkata")
    first, second = PERIOD_START, PERIOD_START.replace(day=23)
    for day in (first, second):
        seed(api.db, pid, [R(day, at=time(14))], end_reason="fatigue_detected")
        observe(api.db, pid, day)  # 14:00, inside that session

    def tiredness():
        patient = api.db.get(PatientProfile, pid)
        s = summarise(api.db, patient, PERIOD_START, PERIOD_END)
        return next((f for f in s.review_flags if f.rule_id == "REPEATED_TIREDNESS"), None)

    assert tiredness() is None, "2 reports on 2 days, not 4 signals"
    observe(api.db, pid, PERIOD_START.replace(day=25))
    flag = tiredness()
    assert flag is not None
    assert flag.numbers["signals"] == 3 and flag.numbers["days"] == 3


# ---------------------------------------------------------------- delivery to the phone (0014)


def delivery(api: Api, actor, pid: str):
    return api.client.get(f"/api/v1/patients/{pid}/fatigue-delivery", headers=actor.headers)


def test_delivery_status_is_honest_waiting_then_sent(api: Api, family) -> None:
    owner, pid, device = family
    obs = observe(api, owner, pid, fatigue_level="severe").json()
    before = delivery(api, owner, pid).json()
    assert before["devices"][0]["last_sync_at"] is None
    assert before["items"] == [{"observation_id": obs["id"], "status": "waiting", "sent_at": None}]

    pull(api, device)  # the phone syncs
    after = delivery(api, owner, pid).json()
    assert after["items"][0]["status"] == "sent"
    assert after["items"][0]["sent_at"] is not None
    assert after["devices"][0]["last_sync_at"] is not None

    # A newer note is waiting again until the next sync.
    newer = observe(api, owner, pid, fatigue_level="mild").json()
    items = {i["observation_id"]: i["status"] for i in delivery(api, owner, pid).json()["items"]}
    assert items == {obs["id"]: "sent", newer["id"]: "waiting"}


def test_delivery_without_a_phone_and_for_reports_made_on_the_phone(api: Api) -> None:
    owner = api.user()
    pid = api.patient(owner)
    observe(api, owner, pid, fatigue_level="mild")
    assert delivery(api, owner, pid).json()["items"][0]["status"] == "no_phone"

    device = api.pair_device(owner, pid)
    push(
        api,
        device,
        {
            "mutation_id": new_uuid(),
            "entity_type": "fatigue_report",
            "data": {"id": new_uuid(), "level": "severe", "reported_at": iso(now())},
        },
    )
    statuses = {i["status"] for i in delivery(api, owner, pid).json()["items"]}
    assert "from_phone" in statuses


def test_phone_and_outsiders_cannot_read_caregiver_notes(api: Api, family) -> None:
    owner, pid, device = family
    observe(api, owner, pid, fatigue_level="severe", note="Synthetic: private caregiver note")
    # The patient's own phone receives level and time through sync, never the notes.
    assert api.client.get(
        f"/api/v1/patients/{pid}/observations", headers=device.headers
    ).status_code in (403, 404)
    assert delivery(api, device, pid).status_code in (403, 404)
    stranger = api.user()
    assert delivery(api, stranger, pid).status_code == 404
    assert (
        api.client.get(f"/api/v1/patients/{pid}/observations", headers=stranger.headers).status_code
        == 404
    )
