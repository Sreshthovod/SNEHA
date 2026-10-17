"""Review items: an automated prompt needs a caregiver's decision before a clinician sees it."""

import pytest

from tests.analytics_fixtures import PERIOD_END, PERIOD_START, R, baseline_rows, days, seed
from tests.helpers import Api

PERIOD = {"period_start": str(PERIOD_START), "period_end": str(PERIOD_END)}


@pytest.fixture
def family(api: Api):
    owner = api.user(name="Synthetic Manager")
    pid = api.patient(owner, timezone="Asia/Kolkata")
    # A sustained, explained change: lower scores on most days at the same difficulty.
    seed(api.db, pid, baseline_rows(score=0.9, rt=2000))
    seed(api.db, pid, [R(d, score=0.6, rt_ms=3200, hints=1) for d in days(PERIOD_START, 7)])
    return owner, pid


def scan(api: Api, actor, pid: str):
    return api.client.post(
        f"/api/v1/patients/{pid}/review-items/scan", json=PERIOD, headers=actor.headers
    )


def decide(api: Api, actor, pid: str, item_id: str, decision: str, reason: str | None):
    body = {"decision": decision}
    if reason is not None:
        body["reason"] = reason
    return api.client.post(
        f"/api/v1/patients/{pid}/review-items/{item_id}/decision", json=body, headers=actor.headers
    )


def test_scan_keeps_each_prompt_with_its_evidence_once(api: Api, family) -> None:
    owner, pid = family
    first = scan(api, owner, pid)
    assert first.status_code == 200, first.text
    items = {i["rule_id"]: i for i in first.json()}
    assert "ACCURACY_LOWER_THAN_USUAL" in items
    acc = items["ACCURACY_LOWER_THAN_USUAL"]
    assert acc["status"] == "awaiting_review"
    assert acc["kind"] == "change"
    assert acc["numbers"]["baseline"] == pytest.approx(0.9)
    assert acc["numbers"]["current"] == pytest.approx(0.6)
    assert "compared with a usual" in acc["explanation"]
    assert acc["period_start"] == str(PERIOD_START)
    assert acc["method_version"] and acc["config_version"]
    assert "not a diagnosis" in acc["wording"]
    assert acc["decided_at"] is None

    again = scan(api, owner, pid).json()
    assert sorted(i["id"] for i in again) == sorted(i["id"] for i in first.json())


def test_a_decision_needs_a_manager_and_a_reason_and_is_final(api: Api, family) -> None:
    owner, pid = family
    item = next(i for i in scan(api, owner, pid).json() if i["kind"] == "change")

    helper = api.user(name="Synthetic Helper")
    api.add_caregiver(owner, pid, helper, can_manage=False)
    assert scan(api, helper, pid).status_code == 200, "any caregiver may look"
    assert decide(api, helper, pid, item["id"], "confirmed", "Synthetic: agree").status_code == 403

    assert decide(api, owner, pid, item["id"], "confirmed", None).status_code == 422
    assert decide(api, owner, pid, item["id"], "confirmed", "  ").status_code == 422
    assert decide(api, owner, pid, item["id"], "awaiting_review", "Synthetic").status_code == 422

    ok = decide(api, owner, pid, item["id"], "confirmed", "Synthetic: also forgetting names")
    assert ok.status_code == 200
    body = ok.json()
    assert body["status"] == "confirmed"
    assert body["decided_by_id"] == owner.id
    assert body["decided_at"] is not None
    assert body["decision_reason"] == "Synthetic: also forgetting names"

    again = decide(api, owner, pid, item["id"], "dismissed", "Synthetic: changed my mind")
    assert again.status_code == 409
    # Re-scanning never rewrites a decided item.
    rescanned = {i["id"]: i for i in scan(api, owner, pid).json()}
    assert rescanned[item["id"]]["status"] == "confirmed"


def test_clinician_sees_only_confirmed_items_and_no_raw_prompts(api: Api, family) -> None:
    owner, pid = family
    clinician = api.user("clinician", name="Synthetic Clinician")
    api.grant_clinician(owner, pid, clinician)
    items = scan(api, owner, pid).json()
    assert len(items) >= 2, [i["rule_id"] for i in items]
    confirmed, dismissed = items[0], items[1]

    url = f"/api/v1/patients/{pid}/review-items"
    assert api.client.get(url, headers=clinician.headers).json() == []
    analytics = api.client.get(
        f"/api/v1/patients/{pid}/analytics?from={PERIOD_START}&to={PERIOD_END}",
        headers=clinician.headers,
    ).json()
    assert analytics["review_flags"] == []
    assert analytics["review_flags_withheld"] is True
    assert analytics["totals"]["results"] > 0, "descriptive data is still shared"
    flags = api.client.get(
        f"/api/v1/patients/{pid}/analytics/review-flags?from={PERIOD_START}&to={PERIOD_END}",
        headers=clinician.headers,
    ).json()
    assert flags["review_flags"] == [] and flags["review_flags_withheld"] is True

    decide(api, owner, pid, confirmed["id"], "confirmed", "Synthetic: worth discussing")
    decide(api, owner, pid, dismissed["id"], "dismissed", "Synthetic: new glasses that week")
    seen = api.client.get(url, headers=clinician.headers).json()
    assert [i["id"] for i in seen] == [confirmed["id"]]
    assert seen[0]["decision_reason"] == "Synthetic: worth discussing"

    # Clinicians cannot create or decide items.
    assert scan(api, clinician, pid).status_code == 403
    assert decide(api, clinician, pid, confirmed["id"], "dismissed", "x" * 5).status_code == 403

    # Caregivers still see the raw prompts and every item.
    own = api.client.get(
        f"/api/v1/patients/{pid}/analytics?from={PERIOD_START}&to={PERIOD_END}",
        headers=owner.headers,
    ).json()
    assert own["review_flags"] and own["review_flags_withheld"] is False
    assert len(api.client.get(url, headers=owner.headers).json()) == len(items)


def test_scan_period_is_bounded(api: Api, family) -> None:
    owner, pid = family
    too_short = {"period_start": str(PERIOD_START), "period_end": str(PERIOD_START)}
    assert (
        api.client.post(
            f"/api/v1/patients/{pid}/review-items/scan", json=too_short, headers=owner.headers
        ).status_code
        == 422
    )


def test_items_from_another_patient_cannot_be_decided(api: Api, family) -> None:
    owner, pid = family
    item = scan(api, owner, pid).json()[0]
    other = api.user(name="Synthetic Other Family")
    other_pid = api.patient(other)
    response = decide(api, other, other_pid, item["id"], "dismissed", "Synthetic: not mine")
    assert response.status_code == 404
