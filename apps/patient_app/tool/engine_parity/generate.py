"""Generate test/fixtures/engine_parity.json from the PYTHON engine.

The Dart port (lib/personalization/engine.dart) must reproduce these outputs
exactly. Re-run after any change to services/api/app/personalization/engine.py
or config/personalization.toml:

    cd services/api && .venv/bin/python ../../apps/patient_app/tool/engine_parity/generate.py

All data is SYNTHETIC.
"""

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "services" / "api"))

from app.personalization.config import get_personalization_config  # noqa: E402
from app.personalization.engine import (  # noqa: E402
    ALGORITHM_VERSION,
    ActivityFact,
    ContentAvailability,
    EngineInput,
    ObservationFact,
    ResultFact,
    SessionEndFact,
    recommend,
)

OUT = Path(__file__).resolve().parents[2] / "test" / "fixtures" / "engine_parity.json"
NOW = datetime(2026, 10, 15, 10, 0, tzinfo=UTC)

A = {
    "picture-pairs": ("4b0c2d0e-5f0e-4c39-9d43-1a6f3f0a0001", 1, 5, False),
    "daily-sequence": ("4b0c2d0e-5f0e-4c39-9d43-1a6f3f0a0003", 1, 5, False),
    "photo-recall": ("4b0c2d0e-5f0e-4c39-9d43-1a6f3f0a0006", 1, 5, True),
    "story-time": ("4b0c2d0e-5f0e-4c39-9d43-1a6f3f0a0007", 1, 1, True),
    "familiar-faces": ("4b0c2d0e-5f0e-4c39-9d43-1a6f3f0a0008", 1, 3, True),
    "name-the-object": ("4b0c2d0e-5f0e-4c39-9d43-1a6f3f0a0009", 1, 3, False),
    "sort-into-groups": ("4b0c2d0e-5f0e-4c39-9d43-1a6f3f0a0010", 1, 3, False),
}
ALL = list(A)


def act(slug):
    i, lo, hi, mem = A[slug]
    return {"id": i, "slug": slug, "min": lo, "max": hi, "memory": mem}


_n = [0]


def res(slug, score=0.9, *, mins_ago=None, hints=0, abandoned=False, engagement=None,
        fatigue=False, rt=None, difficulty=1, repeats=None):
    _n[0] += 1
    when = NOW - timedelta(minutes=mins_ago if mins_ago is not None else 600 - _n[0])
    return {
        "id": f"00000000-0000-4000-8000-{_n[0]:012d}",
        "activity_id": A[slug][0],
        "completed_at": when.isoformat().replace("+00:00", "Z"),
        "difficulty": difficulty,
        "score": score,
        "hints": hints,
        "abandoned": abandoned,
        "engagement": engagement,
        "fatigue_reported": fatigue,
        "mean_response_ms": rt,
        "instructions_repeated": repeats,
    }


def scenario(name, *, slugs=ALL, results=(), **kw):
    return {"name": name, "activities": [act(s) for s in slugs], "results": list(results), **kw}


S = [
    scenario("cold_start_default_order"),
    scenario("success_streak_steps_up_after_3", slugs=["picture-pairs"],
             results=[res("picture-pairs") for _ in range(3)]),
    scenario("two_successes_not_enough", slugs=["picture-pairs"],
             results=[res("picture-pairs") for _ in range(2)]),
    scenario("cooldown_prevents_oscillation", slugs=["picture-pairs"],
             results=[*(res("picture-pairs") for _ in range(3)),
                      res("picture-pairs", 0.2), res("picture-pairs", 0.2)]),
    scenario("struggles_step_down_after_cooldown", slugs=["picture-pairs"],
             results=[*(res("picture-pairs") for _ in range(3)), res("picture-pairs", 0.6),
                      res("picture-pairs", 0.2), res("picture-pairs", 0.3)]),
    scenario("struggle_at_minimum_offers_hints", slugs=["picture-pairs"],
             results=[res("picture-pairs", 0.1), res("picture-pairs", 0.2)]),
    scenario("null_score_does_not_break_streak", slugs=["picture-pairs"],
             results=[res("picture-pairs"), res("picture-pairs"), res("picture-pairs", None),
                      res("picture-pairs")]),
    scenario("latest_null_score_is_missing_data", slugs=["picture-pairs"],
             results=[*(res("picture-pairs") for _ in range(3)), res("picture-pairs", None)]),
    scenario("hints_block_comfortable_success", slugs=["picture-pairs"],
             results=[res("picture-pairs", 0.9, hints=3) for _ in range(3)]),
    scenario("slow_response_not_comfortable", slugs=["picture-pairs"],
             results=[res("picture-pairs", rt=2000), res("picture-pairs", rt=2000),
                      res("picture-pairs", rt=5000)]),
    scenario("interruption_is_not_failure", slugs=["picture-pairs"],
             results=[res("picture-pairs"), res("picture-pairs", None, abandoned=True),
                      res("picture-pairs"), res("picture-pairs")]),
    scenario("difficulty_never_leaves_activity_range", slugs=["name-the-object"],
             results=[res("name-the-object") for _ in range(20)]),
    scenario("stop_request_wins", stop=True, fatigue=True),
    scenario("explicit_fatigue_request_offers_break", fatigue=True),
    scenario("fatigue_in_latest_result_offers_break",
             results=[res("daily-sequence", None, abandoned=True, fatigue=True, mins_ago=5)]),
    scenario("caregiver_fatigue_observation_low_effort",
             results=[res("sort-into-groups", mins_ago=100)],
             observations=[{"id": "obs-1", "category": "fatigue",
                            "observed_at": (NOW - timedelta(hours=2)).isoformat().replace("+00:00", "Z")}]),
    scenario("caregiver_severe_fatigue_offers_break",
             observations=[{"id": "obs-3", "category": "fatigue", "fatigue_level": "severe",
                            "observed_at": (NOW - timedelta(hours=1)).isoformat().replace("+00:00", "Z")}]),
    scenario("caregiver_mild_fatigue_low_effort",
             observations=[{"id": "obs-4", "category": "fatigue", "fatigue_level": "mild",
                            "observed_at": (NOW - timedelta(hours=1)).isoformat().replace("+00:00", "Z")}]),
    scenario("old_fatigue_observation_ignored",
             results=[res("sort-into-groups", mins_ago=100)],
             observations=[{"id": "obs-2", "category": "fatigue",
                            "observed_at": (NOW - timedelta(hours=20)).isoformat().replace("+00:00", "Z")}]),
    scenario("fatigue_session_end_low_effort",
             results=[res("sort-into-groups", mins_ago=100)],
             session_ends=[{"id": "ses-1", "end_reason": "fatigue_detected",
                            "ended_at": (NOW - timedelta(hours=1)).isoformat().replace("+00:00", "Z")}]),
    scenario("interest_match_chooses_activity", interests=["Weaving"]),
    scenario("interest_from_memory_tags", interests=["family"],
             content={"photo-recall": {"sufficient": True, "memory_item_ids": ["m1", "m2", "m3"],
                                       "matched_interests": ["family"]}}),
    scenario("conversation_context_nudges", context_tags=["Tea"]),
    scenario("approved_interest_beats_conversation_context",
             interests=["animals"], context_tags=["tea", "cooking"]),
    scenario("repetition_avoided", results=[res("picture-pairs", 0.7)]),
    scenario("low_engagement_switches",
             results=[res("name-the-object", None, abandoned=True),
                      res("name-the-object", 0.7, engagement="not_enjoyed"),
                      res("picture-pairs", 0.7)]),
    scenario("enjoyed_activity_preferred",
             results=[res("sort-into-groups", 0.7, engagement="enjoyed"),
                      res("sort-into-groups", 0.7, engagement="enjoyed"),
                      res("picture-pairs", 0.7)]),
    scenario("disliked_activity_excluded", disliked=["picture-pairs"]),
    scenario("insufficient_memory_content_excluded",
             slugs=["photo-recall", "familiar-faces", "picture-pairs"],
             content={"photo-recall": {"sufficient": False}, "familiar-faces": {"sufficient": False}}),
    scenario("memory_content_used", slugs=["photo-recall"],
             content={"photo-recall": {"sufficient": True, "memory_item_ids": ["m1", "m2", "m3"]}}),
    scenario("personal_routines_used", slugs=["daily-sequence"],
             content={"daily-sequence": {"sufficient": True, "routine_item_ids": ["r1", "r2", "r3"]}}),
    scenario("offline_content_filter", available=["name-the-object", "story-time"]),
    scenario("language_fallback", slugs=["name-the-object"], language="kha"),
    scenario("nothing_available", slugs=["photo-recall"],
             content={"photo-recall": {"sufficient": False}}),
    # 1.2.0: support that follows what the person needed last time.
    scenario("hint_heavy_runs_turn_hints_on", slugs=["picture-pairs"],
             results=[res("picture-pairs", 0.7, hints=3) for _ in range(2)]),
    scenario("one_hint_heavy_run_is_not_a_pattern", slugs=["picture-pairs"],
             results=[res("picture-pairs", 0.7, hints=3), res("picture-pairs", 0.9)]),
    scenario("struggle_at_easiest_prefers_gentler_activity",
             slugs=["picture-pairs", "name-the-object"],
             results=[res("name-the-object", 0.2), res("name-the-object", 0.3)]),
    scenario("struggle_at_easiest_only_activity_keeps_it_with_hints",
             slugs=["name-the-object"],
             results=[res("name-the-object", 0.2), res("name-the-object", 0.3)]),
    scenario("read_aloud_presses_read_questions_first",
             results=[res("picture-pairs", repeats=2), res("sort-into-groups", repeats=1)]),
    scenario("too_few_read_aloud_presses",
             results=[res("picture-pairs", repeats=1), res("sort-into-groups")]),
    scenario("stop_beats_support_rules", stop=True,
             results=[res("picture-pairs", 0.7, hints=3, repeats=3) for _ in range(2)]),
]


def dt(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def run(sc):
    inp = EngineInput(
        now=NOW,
        language=sc.get("language", "as"),
        activities=tuple(
            ActivityFact(a["id"], a["slug"], a["min"], a["max"], a["memory"]) for a in sc["activities"]
        ),
        results=tuple(
            ResultFact(r["id"], r["activity_id"], dt(r["completed_at"]), r["difficulty"], r["score"],
                       r["hints"], r["abandoned"], r["engagement"], r["fatigue_reported"],
                       r["mean_response_ms"], r.get("instructions_repeated"))
            for r in sc["results"]
        ),
        interests=tuple(sc.get("interests", [])),
        context_tags=tuple(sc.get("context_tags", [])),
        disliked_slugs=frozenset(sc.get("disliked", [])),
        observations=tuple(
            ObservationFact(o["id"], o["category"], dt(o["observed_at"]), o.get("fatigue_level"))
            for o in sc.get("observations", [])
        ),
        session_ends=tuple(
            SessionEndFact(s["id"], dt(s["ended_at"]), s["end_reason"]) for s in sc.get("session_ends", [])
        ),
        content={
            k: ContentAvailability(v["sufficient"], tuple(v.get("memory_item_ids", [])),
                                   tuple(v.get("routine_item_ids", [])),
                                   tuple(v.get("matched_interests", [])))
            for k, v in sc.get("content", {}).items()
        },
        stop_requested=sc.get("stop", False),
        fatigue_reported=sc.get("fatigue", False),
        available_slugs=frozenset(sc["available"]) if "available" in sc else None,
    )
    rec = recommend(inp, get_personalization_config())
    return {
        "action": rec.action.value,
        "activity_slug": rec.activity.slug if rec.activity else None,
        "difficulty": rec.difficulty,
        "reason_codes": rec.reason_codes,
        "supporting": [[s.kind, s.id, s.detail] for s in rec.supporting],
        "hints_enabled": rec.hints_enabled,
        "memory_item_ids": list(rec.memory_item_ids),
        "routine_item_ids": list(rec.routine_item_ids),
        "fallback_used": rec.fallback_used,
        "fallback_reason": rec.fallback_reason,
        "break_minutes": rec.break_minutes,
        "read_aloud_first": rec.read_aloud_first,
    }


def main():
    cfg = get_personalization_config()
    out = {
        "algorithm_version": ALGORITHM_VERSION,
        "config_version": cfg.config_version,
        "now": NOW.isoformat().replace("+00:00", "Z"),
        "scenarios": [{"input": sc, "expected": run(sc)} for sc in S],
    }
    OUT.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
    print(f"Wrote {len(S)} scenarios to {OUT}")


if __name__ == "__main__":
    main()
