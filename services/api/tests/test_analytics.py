"""Analytics calculations, date boundaries, baselines and review flags (synthetic data)."""

from datetime import UTC, date, datetime, time

import pytest

from app.analytics.service import summarise
from app.models.patients import PatientProfile
from tests.analytics_fixtures import (
    OBJECTS,
    PERIOD_END,
    PERIOD_START,
    STORY,
    R,
    baseline_rows,
    days,
    observe,
    seed,
)
from tests.helpers import Api

NOW = datetime(2026, 10, 15, 6, 0, tzinfo=UTC)


@pytest.fixture
def family(api: Api):
    owner = api.user()
    pid = api.patient(owner, timezone="Asia/Kolkata", display_name="Synthetic Analytics Patient")
    return owner, pid


def summary(api: Api, pid: str, start=PERIOD_START, end=PERIOD_END, now=NOW):
    api.db.expire_all()
    return summarise(api.db, api.db.get(PatientProfile, pid), start, end, now=now)


def flag_ids(s) -> set[str]:
    return {f.rule_id for f in s.review_flags}


def test_metrics_known_numbers(api: Api, family) -> None:
    _, pid = family
    d1, d2 = PERIOD_START, PERIOD_START.replace(day=21)
    seed(
        api.db,
        pid,
        [
            R(d1, score=0.5, hints=2, rt_ms=1000, engagement="enjoyed"),
            R(d1, score=1.0, hints=0, rt_ms=3000, at=time(11), engagement="not_enjoyed"),
            R(d2, score=None, activity=STORY, difficulty=1, rt_ms=None),  # unscored → no accuracy
            R(d2, score=0.2, abandoned=True, at=time(11), rt_ms=5000),  # stopped part-way
        ],
    )
    s = summary(api, pid)
    t = s.totals
    assert t.results == 4
    assert t.scored_results == 2
    assert t.accuracy_mean == 0.75  # (0.5 + 1.0) / 2: abandoned and unscored excluded
    assert t.interrupted_results == 1 and t.interruption_rate == 0.25
    assert t.median_response_ms == 3000.0  # median of 1000, 3000, 5000
    assert t.hints_per_result == 0.5 and t.share_results_with_hints == 0.25
    assert t.sessions_started == 2 and t.sessions_completed == 1 and t.sessions_stopped == 1
    assert t.completion_rate == 0.5
    assert s.engagement.model_dump() == {
        "enjoyed": 1,
        "neutral": 0,
        "not_enjoyed": 1,
        "unanswered": 2,
    }
    by_slug = {a.slug: a for a in s.activities}
    assert by_slug["story-time"].accuracy_mean is None
    assert by_slug["picture-pairs"].results == 3
    assert s.completeness.days_elapsed == 9
    assert s.completeness.days_with_activity == 2
    assert len(s.completeness.missing_days) == 7
    assert s.completeness.longest_gap_days == 7
    assert "not a medical assessment" in s.disclaimer


def test_day_boundaries_use_patient_timezone(api: Api, family) -> None:
    _, pid = family
    # 23:59 IST on 19 Sep (before the period) and 00:01 IST on 20 Sep (first day).
    seed(api.db, pid, [R(date(2026, 9, 19), at=time(23, 59)), R(PERIOD_START, at=time(0, 1))])
    s = summary(api, pid)
    assert s.totals.results == 1
    assert s.daily[0].day == PERIOD_START and s.daily[0].results == 1
    # 23:59 IST on the last day is still inside the period.
    seed(api.db, pid, [R(PERIOD_END, at=time(23, 59))])
    assert summary(api, pid).totals.results == 2


def test_future_days_are_not_missing(api: Api, family) -> None:
    _, pid = family
    seed(api.db, pid, [R(date(2026, 10, 14))])
    s = summary(api, pid, date(2026, 10, 12), date(2026, 10, 20))
    assert s.completeness.days_elapsed == 4  # 12–15 Oct; NOW is 15 Oct in IST
    assert date(2026, 10, 16) not in s.completeness.missing_days


def test_no_data_at_all(api: Api, family) -> None:
    _, pid = family
    s = summary(api, pid)
    assert s.totals.results == 0
    assert s.totals.accuracy_mean is None
    assert s.baseline.status == "insufficient_data"
    assert flag_ids(s) == {"DATA_GAP"}  # a data gap, never "low performance"
    gap = s.review_flags[0]
    assert gap.kind == "data"
    assert "not counted as low performance" in gap.explanation


def test_insufficient_baseline_means_no_comparison_and_no_change_flags(api: Api, family) -> None:
    _, pid = family
    seed(api.db, pid, [R(d, score=0.2) for d in days(PERIOD_START, 9)])  # low, but no baseline
    s = summary(api, pid)
    assert s.baseline.status == "insufficient_data"
    assert s.baseline.comparisons == []
    assert not flag_ids(s) & {"ACCURACY_LOWER_THAN_USUAL", "SLOWER_RESPONSES_THAN_USUAL"}
    skipped = {r.rule_id: r.reason for r in s.rules_not_evaluated}
    assert "earlier activity" in skipped["ACCURACY_LOWER_THAN_USUAL"]


def test_one_bad_session_never_raises_a_flag(api: Api, family) -> None:
    _, pid = family
    seed(api.db, pid, baseline_rows())
    period = [R(d, score=0.9) for d in days(PERIOD_START, 8)]
    period += [
        R(PERIOD_END, score=0.1, rt_ms=9000, hints=4, at=t) for t in (time(10), time(11), time(12))
    ]
    seed(api.db, pid, period)
    s = summary(api, pid)
    assert s.baseline.status == "compared"
    assert not flag_ids(s) & {
        "ACCURACY_LOWER_THAN_USUAL",
        "SLOWER_RESPONSES_THAN_USUAL",
        "MORE_HINTS_THAN_USUAL",
    }


def test_sustained_change_raises_explained_flags(api: Api, family) -> None:
    _, pid = family
    seed(api.db, pid, baseline_rows(score=0.9, rt=2000))
    seed(api.db, pid, [R(d, score=0.6, rt_ms=3200, hints=1) for d in days(PERIOD_START, 7)])
    obs_id = observe(api.db, pid, PERIOD_START.replace(day=22), category="sleep")
    s = summary(api, pid)
    ids = flag_ids(s)
    assert {"ACCURACY_LOWER_THAN_USUAL", "SLOWER_RESPONSES_THAN_USUAL"} <= ids
    acc = next(f for f in s.review_flags if f.rule_id == "ACCURACY_LOWER_THAN_USUAL")
    assert acc.numbers["baseline"] == 0.9 and acc.numbers["current"] == 0.6
    assert acc.numbers["share_of_days"] == 1.0
    assert obs_id in acc.observation_ids  # caregiver context attached
    assert "Not a finding" in acc.wording
    comparisons = {c.metric: c for c in s.baseline.comparisons}
    assert comparisons["accuracy_mean"].change == pytest.approx(-0.3)
    for f in s.review_flags:
        for banned in ("dementia", "decline", "impair", "diagnos", "severity"):
            assert banned not in (f.explanation + f.title).lower()


def test_harder_level_explains_lower_scores(api: Api, family) -> None:
    _, pid = family
    seed(api.db, pid, baseline_rows(score=0.9))
    seed(api.db, pid, [R(d, score=0.6, difficulty=4) for d in days(PERIOD_START, 7)])
    assert "ACCURACY_LOWER_THAN_USUAL" not in flag_ids(summary(api, pid))


def test_missing_days_do_not_count_as_failure(api: Api, family) -> None:
    _, pid = family
    seed(api.db, pid, baseline_rows(score=0.9))
    # Good scores on 4 days, nothing on the other 5.
    seed(
        api.db,
        pid,
        [R(d, score=0.9, at=t) for d in days(PERIOD_START, 4) for t in (time(9), time(10))],
    )
    s = summary(api, pid)
    assert s.totals.accuracy_mean == 0.9
    assert "ACCURACY_LOWER_THAN_USUAL" not in flag_ids(s)
    assert "DATA_GAP" in flag_ids(s)


def test_low_enjoyment_and_repeated_tiredness(api: Api, family) -> None:
    _, pid = family
    rows = [R(d, engagement="not_enjoyed", activity=OBJECTS) for d in days(PERIOD_START, 4)]
    rows += [
        R(PERIOD_START, engagement="enjoyed", at=time(12)),
        R(PERIOD_START.replace(day=24), fatigue=True, abandoned=True, at=time(15)),
    ]
    seed(api.db, pid, rows)
    observe(api.db, pid, PERIOD_START.replace(day=21))
    observe(api.db, pid, PERIOD_START.replace(day=25))
    s = summary(api, pid)
    assert "LOW_ENJOYMENT" in flag_ids(s)
    tired = next(f for f in s.review_flags if f.rule_id == "REPEATED_TIREDNESS")
    assert tired.kind == "context"
    assert tired.numbers["signals"] == 3 and tired.numbers["days"] == 3
    # Fatigue stops are tiredness signals, not interruptions.
    assert s.totals.interrupted_results == 0


def test_one_tired_press_counts_once(api: Api, family) -> None:
    # The app marks the result AND ends the session as fatigue_detected for one press.
    _, pid = family
    two_days = [PERIOD_START.replace(day=d) for d in (22, 24)]
    seed(
        api.db,
        pid,
        [R(d, fatigue=True, at=time(15)) for d in two_days],
        end_reason="fatigue_detected",
    )
    assert "REPEATED_TIREDNESS" not in flag_ids(summary(api, pid))
    # A session ended for tiredness with no tired result is still its own signal.
    seed(api.db, pid, [R(PERIOD_START.replace(day=26))], end_reason="fatigue_detected")
    tired = next(f for f in summary(api, pid).review_flags if f.rule_id == "REPEATED_TIREDNESS")
    assert tired.numbers["signals"] == 3 and tired.numbers["days"] == 3


def test_preferences_rank_enjoyed_first(api: Api, family) -> None:
    _, pid = family
    seed(
        api.db,
        pid,
        [
            R(PERIOD_START, activity=OBJECTS, engagement="enjoyed"),
            R(PERIOD_START, at=time(11), engagement="not_enjoyed"),
            R(PERIOD_START, at=time(12), engagement="not_enjoyed"),
        ],
    )
    prefs = summary(api, pid).preferences
    assert [p.slug for p in prefs] == ["name-the-object", "picture-pairs"]


# ---------------------------------------------------------------- endpoints


def test_analytics_endpoint_and_authorization(api: Api, family) -> None:
    owner, pid = family
    seed(api.db, pid, [R(d) for d in days(PERIOD_START, 3)])
    url = f"/api/v1/patients/{pid}/analytics?from={PERIOD_START}&to={PERIOD_END}"

    ok = api.client.get(url, headers=owner.headers)
    assert ok.status_code == 200
    body = ok.json()
    assert body["totals"]["results"] == 3
    assert body["method_version"] and body["config_version"]
    flags = api.client.get(
        f"/api/v1/patients/{pid}/analytics/review-flags?from={PERIOD_START}&to={PERIOD_END}",
        headers=owner.headers,
    )
    assert flags.status_code == 200
    assert {f["rule_id"] for f in flags.json()["review_flags"]} == {"DATA_GAP"}

    outsider = api.user()
    assert api.client.get(url, headers=outsider.headers).status_code == 404
    device = api.pair_device(owner, pid)
    assert api.client.get(url, headers=device.headers).status_code == 403
    clinician = api.user("clinician")
    assert api.client.get(url, headers=clinician.headers).status_code == 404
    api.grant_clinician(owner, pid, clinician)
    assert api.client.get(url, headers=clinician.headers).status_code == 200


def test_analytics_range_validation(api: Api, family) -> None:
    owner, pid = family
    base = f"/api/v1/patients/{pid}/analytics"
    assert (
        api.client.get(f"{base}?from=2026-09-28&to=2026-09-20", headers=owner.headers).status_code
        == 422
    )
    assert (
        api.client.get(f"{base}?from=2024-01-01&to=2026-09-20", headers=owner.headers).status_code
        == 422
    )
    default = api.client.get(base, headers=owner.headers)
    assert default.status_code == 200
    body = default.json()
    assert (date.fromisoformat(body["to_date"]) - date.fromisoformat(body["from_date"])).days == 8
