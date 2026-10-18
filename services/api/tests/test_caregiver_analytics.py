"""Caregiver analytics, review evidence and reporting (Part 5). SYNTHETIC data only."""

import uuid
from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.analytics.service import summarise
from app.models.activities import ActivitySession
from app.models.enums import RecordSource, SessionEndReason, SessionStatus
from app.models.patients import PatientProfile
from app.reports import service as report_service
from tests.analytics_fixtures import (
    OBJECTS,
    PAIRS,
    PERIOD_END,
    PERIOD_START,
    R,
    baseline_rows,
    days,
    local,
    seed,
)
from tests.helpers import Api, iso, new_uuid, now
from tests.test_activity_events import event_mutation
from tests.test_sync import push, session_mutation

NOW = datetime(2026, 10, 15, 6, 0, tzinfo=UTC)
IST = ZoneInfo("Asia/Kolkata")


@pytest.fixture
def family(api: Api):
    owner = api.user(name="Synthetic Analytics Daughter")
    pid = api.patient(owner, timezone="Asia/Kolkata")
    return owner, pid


def summary(api: Api, pid: str, start=PERIOD_START, end=PERIOD_END, at=NOW):
    api.db.expire_all()
    return summarise(api.db, api.db.get(PatientProfile, pid), start, end, now=at)


def open_session(api: Api, pid: str, day, end_reason=None, hour=9) -> str:
    start = local(day, time(hour))
    session = ActivitySession(
        id=str(uuid.uuid4()),
        patient_id=pid,
        status=SessionStatus.ABANDONED if end_reason else SessionStatus.IN_PROGRESS,
        end_reason=SessionEndReason(end_reason) if end_reason else None,
        source=RecordSource.DEVICE,
        started_at=start,
        ended_at=start + timedelta(minutes=3) if end_reason else None,
    )
    api.db.add(session)
    api.db.commit()
    return session.id


# ---------------------------------------------------------------- sessions and dates


def test_sessions_are_counted_by_how_they_ended(api: Api, family) -> None:
    _, pid = family
    seed(api.db, pid, [R(d) for d in days(PERIOD_START, 3)])  # 3 completed
    open_session(api, pid, PERIOD_START, "timeout")
    open_session(api, pid, PERIOD_START, "user_stopped", hour=8)
    open_session(api, pid, PERIOD_START.replace(day=22))  # still open
    t = summary(api, pid).totals
    assert t.sessions_started == 6
    assert t.sessions_completed == 3
    assert t.sessions_interrupted == 1
    assert t.sessions_in_progress == 1
    assert t.sessions_stopped == 2  # user_stopped + timeout are both "abandoned"
    assert t.completion_rate == pytest.approx(3 / 5)  # open session not counted as ended


def test_period_dates_are_inclusive_in_the_patients_timezone(api: Api, family) -> None:
    _, pid = family
    seed(
        api.db,
        pid,
        [
            R(PERIOD_START - timedelta(days=1), at=time(23, 59)),  # day before: out
            R(PERIOD_START, at=time(0, 0)),  # first instant: in
            R(PERIOD_END, at=time(23, 59)),  # last minute of the last day: in
            R(PERIOD_END + timedelta(days=1), at=time(0, 0)),  # next day: out
        ],
    )
    s = summary(api, pid)
    assert s.totals.results == 2
    assert s.completeness.days_elapsed == 9
    assert {d.day for d in s.daily if d.has_data} == {PERIOD_START, PERIOD_END}


# ---------------------------------------------------------------- like with like


def test_a_different_mix_of_games_is_not_a_change(api: Api, family) -> None:
    _, pid = family
    seed(api.db, pid, baseline_rows(score=0.9))  # usual: picture pairs, comfortable
    # This period: picture pairs as usual, plus a NEW game played with low scores.
    period = [R(d, score=0.9) for d in days(PERIOD_START, 7)]
    period += [R(d, activity=OBJECTS, score=0.3, at=time(15)) for d in days(PERIOD_START, 7)]
    seed(api.db, pid, period)
    s = summary(api, pid)
    assert s.baseline.status == "compared"
    assert s.baseline.activities_compared == ["Matching pairs"]
    assert s.baseline.activities_not_compared == ["Name the object"]
    assert [a.title for a in s.baseline.per_activity] == ["Matching pairs"]
    assert "ACCURACY_LOWER_THAN_USUAL" not in {f.rule_id for f in s.review_flags}


def test_no_shared_activity_means_no_comparison_with_a_reason(api: Api, family) -> None:
    _, pid = family
    seed(api.db, pid, baseline_rows())
    seed(api.db, pid, [R(d, activity=OBJECTS) for d in days(PERIOD_START, 7)])
    s = summary(api, pid)
    assert s.baseline.status == "insufficient_data"
    assert "no activity was played both" in s.baseline.reason
    reasons = {r.rule_id: r.reason for r in s.rules_not_evaluated}
    assert "no activity was played both" in reasons["ACCURACY_LOWER_THAN_USUAL"]


# ---------------------------------------------------------------- events and sync


def test_support_comes_from_events_counted_once_even_when_resent(api: Api) -> None:
    owner = api.user()
    pid = api.patient(owner, timezone="Asia/Kolkata")
    device = api.pair_device(owner, pid)
    started = now() - timedelta(hours=2)
    s = session_mutation(started_at=iso(started))
    sid = s["data"]["id"]
    events = [
        event_mutation(sid, 0, "hint_requested", source="patient"),
        event_mutation(sid, 1, "hint_auto", source="system"),
        event_mutation(sid, 2, "paused", source="system"),
        event_mutation(
            sid, 3, "adaptation", action="shorten", reason_codes=["MILD_FATIGUE_SHORTEN"]
        ),
        event_mutation(sid, 4, "stop_requested", source="patient"),
    ]
    push(api, device, s, *events)
    push(api, device, *[{**e, "mutation_id": new_uuid()} for e in events])  # re-sent
    old = session_mutation(started_at=iso(started - timedelta(hours=1)))  # no step record
    push(api, device, old)
    today = now().astimezone(IST).date()
    sup = summary(api, pid, today - timedelta(days=8), today, at=now()).support
    assert sup.sessions_with_events == 1 and sup.sessions_started == 2
    assert (sup.hints_asked_for, sup.hints_given_automatically) == (1, 1)
    assert (sup.pauses_screen_left, sup.pauses_by_person) == (1, 0)
    assert sup.adjustments == {"shorten": 1}
    assert sup.stop_requests == 1


def test_no_step_record_is_unknown_not_zero(api: Api, family) -> None:
    _, pid = family
    seed(api.db, pid, [R(PERIOD_START)])
    sup = summary(api, pid).support
    assert sup.sessions_with_events == 0
    assert sup.hints_asked_for is None and sup.adjustments is None


def test_report_says_it_may_be_incomplete_until_the_phone_has_synced(api: Api) -> None:
    owner = api.user()
    pid = api.patient(owner, timezone="Asia/Kolkata")
    yesterday = now().astimezone(IST).date() - timedelta(days=1)
    start = yesterday - timedelta(days=7)
    no_phone = summary(api, pid, start, yesterday, at=now()).sync
    assert no_phone.phone_paired is False and no_phone.may_be_incomplete is False

    device = api.pair_device(owner, pid)
    waiting = summary(api, pid, start, yesterday, at=now()).sync
    assert waiting.may_be_incomplete is True
    assert "has not shared its records" in waiting.reason
    api.client.get("/api/v1/sync/pull?since=0", headers=device.headers)
    done = summary(api, pid, start, yesterday, at=now()).sync
    assert done.may_be_incomplete is False and done.last_phone_sync_at is not None

    running = summary(api, pid, start, yesterday + timedelta(days=1), at=now()).sync
    assert running.may_be_incomplete is True and running.reason == "the period has not ended yet"


# ---------------------------------------------------------------- review evidence and context


@pytest.fixture
def flagged(api: Api, family):
    owner, pid = family
    seed(api.db, pid, baseline_rows(score=0.9, rt=2000))
    seed(api.db, pid, [R(d, score=0.6, rt_ms=3200, hints=1) for d in days(PERIOD_START, 7)])
    items = api.client.post(
        f"/api/v1/patients/{pid}/review-items/scan",
        json={"period_start": str(PERIOD_START), "period_end": str(PERIOD_END)},
        headers=owner.headers,
    ).json()
    return owner, pid, next(i for i in items if i["rule_id"] == "ACCURACY_LOWER_THAN_USUAL")


def test_review_items_keep_the_records_behind_them(api: Api, flagged) -> None:
    _, _, item = flagged
    ev = item["evidence"]
    assert ev["results_considered"] == 7 and len(ev["result_ids"]) == 7
    assert ev["activities"] == ["Matching pairs"]
    assert ev["missing_days"] == [str(PERIOD_START + timedelta(days=d)) for d in (7, 8)]
    assert any("LOW_ENJOYMENT" in limitation for limitation in ev["limitations"])


def test_context_is_added_without_changing_the_decision(api: Api, flagged) -> None:
    owner, pid, item = flagged
    url = f"/api/v1/patients/{pid}/review-items/{item['id']}"
    helper = api.user(name="Synthetic Helper")
    api.add_caregiver(owner, pid, helper)
    added = api.client.post(
        f"{url}/context", json={"note": "Synthetic: new glasses this week"}, headers=helper.headers
    )
    assert added.status_code == 200
    body = added.json()
    assert body["status"] == "awaiting_review"
    assert body["context_notes"][0]["note"] == "Synthetic: new glasses this week"
    assert body["context_notes"][0]["by"] == helper.id
    assert body["numbers"] == item["numbers"] and body["evidence"] == item["evidence"]
    assert (
        api.client.post(f"{url}/context", json={"note": " "}, headers=owner.headers).status_code
        == 422
    )

    clinician = api.user("clinician")
    api.grant_clinician(owner, pid, clinician)
    assert (
        api.client.post(
            f"{url}/context", json={"note": "Synthetic"}, headers=clinician.headers
        ).status_code
        == 403
    )
    stranger = api.user()
    assert (
        api.client.post(
            f"{url}/context", json={"note": "Synthetic"}, headers=stranger.headers
        ).status_code
        == 404
    )


# ---------------------------------------------------------------- report


@pytest.fixture
def uncompressed(monkeypatch):
    original = report_service.build_pdf
    monkeypatch.setattr(
        report_service, "build_pdf", lambda data, **kw: original(data, compress=False, **kw)
    )


def test_full_report_shows_period_definition_comparison_and_review_context(
    api: Api, flagged, uncompressed
) -> None:
    owner, pid, item = flagged
    api.client.post(
        f"/api/v1/patients/{pid}/review-items/{item['id']}/context",
        json={"note": "Synthetic: visiting relatives"},
        headers=owner.headers,
    )
    api.client.post(
        f"/api/v1/patients/{pid}/review-items/{item['id']}/decision",
        json={"decision": "confirmed", "reason": "Synthetic: worth discussing"},
        headers=owner.headers,
    )
    report = api.client.post(
        f"/api/v1/patients/{pid}/reports",
        json={"period_start": str(PERIOD_START), "period_end": str(PERIOD_END)},
        headers=owner.headers,
    ).json()
    pdf = api.client.get(
        f"/api/v1/files/{report['file_id']}/content", headers=owner.headers
    ).content
    for text in [
        b"Both dates are included",
        b"Only activities played in both periods are",
        b"Support given during activities",
        b"Based on 7 recorded activities.",
        b"Synthetic: visiting relatives",
    ]:
        assert text in pdf, text


def test_sparse_report_states_what_is_missing(api: Api, uncompressed) -> None:
    owner = api.user()
    pid = api.patient(owner, timezone="Asia/Kolkata")
    api.pair_device(owner, pid)  # paired, never synced
    report = api.client.post(
        f"/api/v1/patients/{pid}/reports",
        json={"period_start": str(PERIOD_START), "period_end": str(PERIOD_END)},
        headers=owner.headers,
    ).json()
    pdf = api.client.get(
        f"/api/v1/files/{report['file_id']}/content", headers=owner.headers
    ).content
    assert b"No activity was recorded in this period" in pdf
    assert b"This report may be incomplete" in pdf
    assert b"No step-by-step record" in pdf
    assert PAIRS  # synthetic catalog ids used above
