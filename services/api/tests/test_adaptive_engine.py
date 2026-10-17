"""Engine 1.2.0: support that follows what the person needed (synthetic scenarios).

Each test names the acceptance criterion it covers (docs/adaptive-engine-plan.md).
"""

from app.personalization.engine import Action, Reason
from tests.test_personalization_engine import (
    ALL,
    NO_MEMORIES,
    OBJECT,
    PAIRS,
    SORT,
    result,
    run,
    series,
)

ONLY = {"available_slugs": frozenset({"picture-pairs", "name-the-object"})}


def codes(rec) -> set[str]:
    return set(rec.reason_codes)


def test_one_success_does_not_escalate_difficulty() -> None:
    rec = run(results=[result(PAIRS, score=1.0)], available_slugs=frozenset({"picture-pairs"}))
    assert rec.difficulty == 1
    assert Reason.DIFFICULTY_INCREASED.value not in codes(rec)


def test_comfortable_success_varies_the_activity_before_escalating() -> None:
    # Two comfortable runs of picture pairs: no step up yet, and the next suggestion is a
    # different suitable activity (gentle variation, not constant escalation).
    rec = run(results=series(PAIRS, [1.0, 1.0]), **ONLY)
    assert rec.activity.slug == "name-the-object"
    assert Reason.AVOID_REPETITION.value in codes(rec)


def test_hint_heavy_runs_turn_hints_on_without_changing_difficulty() -> None:
    heavy = series(PAIRS, [0.7, 0.7], hints=3)
    rec = run(results=heavy, available_slugs=frozenset({"picture-pairs"}))
    assert rec.hints_enabled is True
    assert Reason.HINT_SUPPORT.value in codes(rec)
    assert rec.difficulty == 1
    assert {s.id for s in rec.supporting} >= {r.id for r in heavy}


def test_one_hint_heavy_run_is_not_a_pattern() -> None:
    rec = run(
        results=[*series(PAIRS, [0.7], hints=3), *series(PAIRS, [0.9], start_minutes=300)],
        available_slugs=frozenset({"picture-pairs"}),
    )
    assert Reason.HINT_SUPPORT.value not in codes(rec)
    assert rec.hints_enabled is False


def test_repeated_struggle_at_easiest_level_prefers_a_gentler_activity() -> None:
    struggles = series(OBJECT, [0.2, 0.3])  # name-the-object at level 1
    rec = run(results=struggles, **ONLY)
    assert rec.activity.slug == "picture-pairs"
    assert Reason.EASIER_ALTERNATIVE.value in codes(rec)


def test_struggle_at_easiest_with_no_alternative_still_offers_it_with_hints() -> None:
    rec = run(results=series(OBJECT, [0.2, 0.3]), available_slugs=frozenset({"name-the-object"}))
    assert rec.activity.slug == "name-the-object"
    assert rec.hints_enabled is True
    assert Reason.EASIER_ALTERNATIVE.value not in codes(rec)


def test_read_aloud_presses_turn_on_reading_questions_first() -> None:
    rec = run(results=series(PAIRS, [0.9, 0.9], instructions_repeated=2))
    assert rec.read_aloud_first is True
    assert Reason.READ_ALOUD_FIRST.value in codes(rec)
    few = run(results=series(PAIRS, [0.9], instructions_repeated=1))
    assert few.read_aloud_first is False


def test_missing_observations_are_unknown_not_negative() -> None:
    # Older results without the new metric, unscored results: no support rule fires and
    # nothing is treated as a struggle.
    rec = run(results=series(PAIRS, [None, None], hints=3))
    assert rec.read_aloud_first is False
    assert Reason.EASIER_ALTERNATIVE.value not in codes(rec)
    cold = run()
    assert Reason.COLD_START_DEFAULT.value in codes(cold)
    assert cold.hints_enabled is False and cold.read_aloud_first is False


def test_different_histories_give_different_justified_recommendations() -> None:
    a = run(results=series(OBJECT, [0.2, 0.3]), **ONLY)
    b = run(results=series(OBJECT, [1.0, 1.0]), **ONLY)
    c = run(
        results=series(PAIRS, [0.7, 0.7], hints=3), available_slugs=frozenset({"picture-pairs"})
    )
    assert (a.activity.slug, a.hints_enabled) != (c.activity.slug, c.hints_enabled) or codes(
        a
    ) != codes(c)
    assert codes(a) != codes(b)
    assert Reason.HINT_SUPPORT.value in codes(c)


def test_identical_inputs_give_identical_decisions() -> None:
    history = [*series(OBJECT, [0.2, 0.3]), *series(PAIRS, [0.7, 0.7], hints=3, start_minutes=200)]
    first = run(results=history, activities=ALL)
    for _ in range(5):
        again = run(results=history, activities=ALL)
        assert again.reason_codes == first.reason_codes
        assert (again.activity, again.difficulty, again.hints_enabled) == (
            first.activity,
            first.difficulty,
            first.hints_enabled,
        )


def test_stop_and_tiredness_override_every_support_rule() -> None:
    history = [
        *series(OBJECT, [0.2, 0.3], instructions_repeated=3),
        *series(PAIRS, [0.7, 0.7], hints=3),
    ]
    stop = run(results=history, stop_requested=True, fatigue_reported=True)
    assert stop.action is Action.STOP and stop.reason_codes == [Reason.STOP_REQUESTED.value]
    tired = run(results=history, fatigue_reported=True)
    assert tired.action is Action.BREAK
    assert tired.activity.slug in {"picture-pairs", "name-the-object", "story-time"}
    assert tired.difficulty == tired.activity.min_difficulty


def test_incompatible_activities_are_never_recommended() -> None:
    history = series(SORT, [0.2, 0.3])
    rec = run(
        results=history,
        available_slugs=frozenset({"sort-into-groups", "picture-pairs"}),
        content=NO_MEMORIES,
    )
    assert rec.activity.slug in {"sort-into-groups", "picture-pairs"}
    no_photos = run(results=(), available_slugs=frozenset({"photo-recall"}), content=NO_MEMORIES)
    assert no_photos.action is Action.NONE


# ---------------------------------------------------------------- through the API


def test_synced_history_changes_the_server_suggestion_and_reasons_persist(api) -> None:
    from datetime import timedelta

    from tests.helpers import PAIRS_ID, iso, new_uuid, now
    from tests.test_activity_events import event_mutation
    from tests.test_sync import push, session_mutation

    owner = api.user()
    pid = api.patient(owner)
    device = api.pair_device(owner, pid)
    mutations = []
    for i, repeats in enumerate([2, 1]):
        s = session_mutation(started_at=iso(now() - timedelta(minutes=60 - i * 10)))
        mutations.append(s)
        body = api.result_body(now() - timedelta(minutes=55 - i * 10))
        body["metrics"] = {"instructions_repeated": repeats}
        mutations.append(
            {
                "mutation_id": new_uuid(),
                "entity_type": "activity_result",
                "data": {**body, "session_id": s["data"]["id"]},
            }
        )
    sid = mutations[-2]["data"]["id"]
    mutations.append(event_mutation(sid, 0, "instructions_repeated"))
    mutations.append(
        event_mutation(
            sid,
            1,
            "activity_started",
            engine_reason_codes=["INSTRUCTIONS_READ_ALOUD_FIRST", "HINT_SUPPORT_AFTER_HINT_USE"],
            decided_on="device",
        )
    )
    assert {r["status"] for r in push(api, device, *mutations).json()["results"]} == {"applied"}

    rec = api.client.post(
        "/api/v1/activities/next", json={"patient_id": pid}, headers=device.headers
    ).json()
    assert rec["read_aloud_first"] is True
    assert "INSTRUCTIONS_READ_ALOUD_FIRST" in rec["reason_codes"]
    assert rec["algorithm_version"] == "1.2.0"
    listed = api.client.get(f"/api/v1/patients/{pid}/recommendations", headers=owner.headers)
    assert listed.status_code == 200  # stored with the same flag and reasons
    assert any(r["read_aloud_first"] for r in listed.json())

    stored = api.client.get(
        f"/api/v1/patients/{pid}/sessions/{sid}/events", headers=owner.headers
    ).json()
    assert [e["event_type"] for e in stored] == ["instructions_repeated", "activity_started"]
    assert stored[1]["data"]["decided_on"] == "device"
    assert stored[1]["data"]["engine_reason_codes"][0] == "INSTRUCTIONS_READ_ALOUD_FIRST"
    bad = event_mutation(sid, 2, "activity_started", decided_on="cloud_ai")
    assert push(api, device, bad).status_code == 422
    assert PAIRS_ID  # the synthetic results above are picture-pairs
