"""Pure-engine scenarios. The Flutter port (apps/patient_app) mirrors these for parity."""

from datetime import UTC, datetime, timedelta

import pytest

from app.personalization.config import get_activity_specs, get_personalization_config
from app.personalization.engine import (
    Action,
    ActivityFact,
    ContentAvailability,
    EngineInput,
    ObservationFact,
    Reason,
    ResultFact,
    SessionEndFact,
    decide_difficulty,
    recommend,
)

NOW = datetime(2026, 10, 15, 10, 0, tzinfo=UTC)
CFG = get_personalization_config()

PAIRS = ActivityFact("a-pairs", "picture-pairs", 1, 5, False)
OBJECT = ActivityFact("a-object", "name-the-object", 1, 3, False)
SORT = ActivityFact("a-sort", "sort-into-groups", 1, 3, False)
SEQUENCE = ActivityFact("a-seq", "daily-sequence", 1, 5, False)
STORY = ActivityFact("a-story", "story-time", 1, 1, True)
PHOTO = ActivityFact("a-photo", "photo-recall", 1, 5, True)
ALL = (PAIRS, OBJECT, SORT, SEQUENCE, STORY, PHOTO)
NO_MEMORIES = {
    "photo-recall": ContentAvailability(False),
    "story-time": ContentAvailability(False),
    "familiar-faces": ContentAvailability(False),
}

_n = 0


def result(
    activity=PAIRS, *, score=0.9, hints=0, abandoned=False, minutes_ago=60, **kw
) -> ResultFact:
    global _n
    _n += 1
    return ResultFact(
        id=f"r{_n:04d}",
        activity_id=activity.id,
        completed_at=NOW - timedelta(minutes=minutes_ago),
        difficulty=kw.pop("difficulty", 1),
        score=score,
        hints=hints,
        abandoned=abandoned,
        **kw,
    )


def series(activity, scores, start_minutes=600, **kw):
    return [
        result(activity, score=s, minutes_ago=start_minutes - i * 10, **kw)
        for i, s in enumerate(scores)
    ]


def run(**kw) -> object:
    base = dict(now=NOW, language="as", activities=ALL, results=(), content=NO_MEMORIES)
    base.update(kw)
    if isinstance(base["results"], list):
        base["results"] = tuple(base["results"])
    return recommend(EngineInput(**base), CFG)


# ---------------- configuration ----------------


def test_config_loads_and_covers_catalog_levels() -> None:
    specs = get_activity_specs()
    for slug in [
        "picture-pairs",
        "photo-recall",
        "familiar-faces",
        "daily-sequence",
        "name-the-object",
        "sort-into-groups",
    ]:
        spec = specs[slug]
        assert spec.instructions and spec.hint and spec.evaluation and spec.stop
        assert [lv.level for lv in spec.levels] == sorted(lv.level for lv in spec.levels)
    assert CFG.config_version
    assert CFG.difficulty.struggle_score < CFG.difficulty.success_score


def test_invalid_config_is_rejected() -> None:
    from pydantic import ValidationError

    from app.personalization.config import PersonalizationConfig

    raw = CFG.model_dump()
    raw["difficulty"]["struggle_score"] = 0.9
    with pytest.raises(ValidationError, match="struggle_score"):
        PersonalizationConfig.model_validate(raw)


# ---------------- difficulty ----------------


def test_three_comfortable_successes_step_up_one_level() -> None:
    assert decide_difficulty(PAIRS, series(PAIRS, [0.9, 0.9]), CFG).level == 1
    decision = decide_difficulty(PAIRS, series(PAIRS, [0.9, 0.9, 0.95]), CFG)
    assert decision.level == 2
    assert Reason.DIFFICULTY_INCREASED in decision.reasons


def test_cooldown_prevents_rapid_oscillation() -> None:
    # Up after 3 successes, then 2 struggles immediately: held (cooldown), not dropped.
    decision = decide_difficulty(PAIRS, series(PAIRS, [0.9, 0.9, 0.9, 0.2, 0.2]), CFG)
    assert decision.level == 2
    assert Reason.DIFFICULTY_HELD_COOLDOWN in decision.reasons
    # One more struggle after the cooldown → step down.
    assert decide_difficulty(PAIRS, series(PAIRS, [0.9, 0.9, 0.9, 0.2, 0.2, 0.2]), CFG).level == 1


def test_two_struggles_step_down_and_offer_hints() -> None:
    six_good = [0.9] * 6  # → level 3
    decision = decide_difficulty(PAIRS, series(PAIRS, [*six_good, 0.6, 0.6, 0.3, 0.3]), CFG)
    assert decision.level == 2
    assert Reason.DIFFICULTY_DECREASED in decision.reasons
    assert decision.hints_enabled


def test_missing_score_and_interruptions_are_not_failures() -> None:
    results = [
        *series(PAIRS, [0.9, 0.9]),
        result(PAIRS, score=None, minutes_ago=300),
        result(PAIRS, score=None, abandoned=True, minutes_ago=290),
        result(PAIRS, score=0.95, minutes_ago=280),
    ]
    decision = decide_difficulty(PAIRS, results, CFG)
    assert decision.level == 2  # streak survived the gaps
    latest_none = decide_difficulty(
        PAIRS, [*series(PAIRS, [0.9]), result(PAIRS, score=None, minutes_ago=1)], CFG
    )
    assert Reason.MISSING_DATA_IGNORED in latest_none.reasons
    assert not latest_none.hints_enabled


def test_many_hints_or_slow_responses_are_not_comfortable() -> None:
    hinted = [result(PAIRS, score=0.9, hints=3, minutes_ago=100 - i) for i in range(3)]
    assert decide_difficulty(PAIRS, hinted, CFG).level == 1
    slow = [
        result(PAIRS, score=0.9, mean_response_ms=2000, minutes_ago=200),
        result(PAIRS, score=0.9, mean_response_ms=6000, minutes_ago=190),
        result(PAIRS, score=0.9, mean_response_ms=6500, minutes_ago=180),
    ]
    assert decide_difficulty(PAIRS, slow, CFG).level == 1


def test_difficulty_never_leaves_activity_range() -> None:
    assert decide_difficulty(OBJECT, series(OBJECT, [1.0] * 30), CFG).level == 3
    assert decide_difficulty(OBJECT, series(OBJECT, [0.0] * 30), CFG).level == 1


# ---------------- selection ----------------


def test_stop_always_wins() -> None:
    rec = run(stop_requested=True, fatigue_reported=True, results=series(PAIRS, [0.9]))
    assert rec.action is Action.STOP
    assert rec.activity is None
    assert rec.reason_codes == ["STOP_REQUESTED"]


def test_cold_start_uses_configured_order_and_marks_fallback() -> None:
    rec = run()
    assert rec.action is Action.ACTIVITY
    assert rec.activity.slug == CFG.selection.cold_start_order[0]
    assert rec.fallback_used and rec.fallback_reason == "no_history"
    assert Reason.COLD_START_DEFAULT in rec.reasons


def test_explicit_fatigue_offers_break_with_easy_alternative() -> None:
    rec = run(fatigue_reported=True, results=series(SEQUENCE, [0.9, 0.9, 0.9, 0.9]))
    assert rec.action is Action.BREAK
    assert rec.break_minutes == CFG.fatigue.break_minutes
    assert rec.activity.slug in CFG.fatigue.low_effort_slugs
    assert rec.difficulty == rec.activity.min_difficulty
    assert Reason.LOW_EFFORT_FOR_FATIGUE in rec.reasons


def test_tiredness_in_latest_result_offers_break() -> None:
    results = [
        *series(SEQUENCE, [0.9, 0.9]),
        result(SEQUENCE, score=0.6, minutes_ago=2, fatigue_reported=True),
    ]
    assert run(results=results).action is Action.BREAK


def test_caregiver_fatigue_observation_selects_low_effort_activity() -> None:
    history = series(
        SEQUENCE, [0.9, 0.9, 0.9, 0.9, 0.9, 0.9]
    )  # sequence would otherwise be level 3
    calm = run(results=history, interests=("gardening",))
    tired = run(
        results=history,
        interests=("gardening",),
        observations=(ObservationFact("o1", "fatigue", NOW - timedelta(hours=1)),),
    )
    assert calm.activity.slug == "sort-into-groups"  # gardening interest, not low effort
    assert tired.action is Action.ACTIVITY
    assert tired.activity.slug in CFG.fatigue.low_effort_slugs
    assert tired.difficulty == tired.activity.min_difficulty
    assert Reason.RECENT_FATIGUE_OBSERVATION in tired.reasons
    assert any(s.kind == "caregiver_observation" and s.id == "o1" for s in tired.supporting)


def test_old_fatigue_observation_is_ignored() -> None:
    rec = run(observations=(ObservationFact("o1", "fatigue", NOW - timedelta(days=2)),))
    assert Reason.RECENT_FATIGUE_OBSERVATION not in rec.reasons


def test_fatigue_ended_session_counts_as_recent_fatigue() -> None:
    rec = run(
        results=series(SEQUENCE, [0.9]),
        session_ends=(SessionEndFact("s1", NOW - timedelta(minutes=30), "fatigue_detected"),),
    )
    assert Reason.RECENT_FATIGUE_FEEDBACK in rec.reasons


def test_interest_match_chooses_activity() -> None:
    history = [
        result(a, score=0.7, minutes_ago=500 - i)
        for i, a in enumerate((PAIRS, OBJECT, SORT, SEQUENCE))
    ]
    gardening = run(results=history, interests=("gardening",))
    tools = run(results=history, interests=("tools",))
    assert gardening.activity.slug in {"sort-into-groups", "daily-sequence"}
    assert tools.activity.slug == "name-the-object"
    assert Reason.INTEREST_MATCH in tools.reasons


def test_repetition_is_avoided() -> None:
    rec = run(results=series(PAIRS, [0.9, 0.9]))
    assert rec.activity.slug != "picture-pairs"
    assert Reason.AVOID_REPETITION in rec.reasons


def test_low_engagement_switches_to_a_familiar_different_activity() -> None:
    results = [
        result(OBJECT, score=0.8, engagement="enjoyed", minutes_ago=400),
        result(PAIRS, score=None, abandoned=True, minutes_ago=30),
        result(PAIRS, score=0.4, engagement="not_enjoyed", minutes_ago=20),
    ]
    rec = run(results=results)
    assert rec.activity.slug != "picture-pairs"
    assert Reason.LOW_ENGAGEMENT_SWITCH in rec.reasons


def test_enjoyed_activities_are_preferred() -> None:
    results = [
        result(SORT, score=0.7, engagement="enjoyed", minutes_ago=300),
        result(OBJECT, score=0.7, engagement="neutral", minutes_ago=290),
        result(PAIRS, score=0.7, minutes_ago=280),
    ]
    rec = run(results=results)
    assert rec.activity.slug == "sort-into-groups"
    assert Reason.ENJOYED_BEFORE in rec.reasons


def test_disliked_and_unavailable_activities_are_excluded() -> None:
    rec = run(
        disliked_slugs=frozenset({"picture-pairs"}),
        available_slugs=frozenset({"picture-pairs", "daily-sequence"}),
    )
    assert rec.activity.slug == "daily-sequence"
    assert Reason.DISLIKED_EXCLUDED in rec.reasons
    assert Reason.OFFLINE_CONTENT_FILTER in rec.reasons


def test_memory_activities_need_enough_approved_content() -> None:
    only_memory = frozenset({"photo-recall"})
    assert run(available_slugs=only_memory).action is Action.NONE
    content = {
        **NO_MEMORIES,
        "photo-recall": ContentAvailability(True, ("m1", "m2", "m3"), (), ("tea",)),
    }
    rec = run(available_slugs=only_memory, content=content, interests=("tea",))
    assert rec.activity.slug == "photo-recall"
    assert rec.memory_item_ids == ("m1", "m2", "m3")
    assert Reason.MEMORY_CONTENT_USED in rec.reasons
    assert Reason.INTEREST_MATCH in rec.reasons


def test_language_without_content_falls_back_explicitly() -> None:
    rec = run(language="kha", available_slugs=frozenset({"name-the-object"}))
    assert rec.activity.slug == "name-the-object"
    assert rec.fallback_used and rec.fallback_reason == "language_content_unavailable"


def test_no_activity_available() -> None:
    rec = run(available_slugs=frozenset())
    assert rec.action is Action.NONE
    assert Reason.NO_AVAILABLE_ACTIVITY in rec.reasons


def test_engine_is_deterministic() -> None:
    results = series(PAIRS, [0.9, 0.5, 0.8]) + series(SORT, [0.7], start_minutes=50)
    first, second = run(results=results), run(results=results)
    assert (first.activity, first.difficulty, first.reason_codes) == (
        second.activity,
        second.difficulty,
        second.reason_codes,
    )


def test_supporting_details_never_contain_free_text() -> None:
    rec = run(observations=(ObservationFact("o1", "fatigue", NOW - timedelta(hours=1)),))
    for item in rec.supporting:
        assert len(item.detail) < 120


def test_conversation_context_nudges_but_approved_interest_wins() -> None:
    history = [
        result(a, score=0.7, minutes_ago=500 - i)
        for i, a in enumerate((PAIRS, OBJECT, SORT, SEQUENCE))
    ]
    rec = run(results=history, context_tags=("tools",))
    assert rec.activity.slug == "name-the-object"
    assert Reason.CONVERSATION_CONTEXT_MATCH in rec.reasons
    both = run(results=history, interests=("gardening", "food"), context_tags=("tools",))
    assert both.activity.slug == "sort-into-groups"
