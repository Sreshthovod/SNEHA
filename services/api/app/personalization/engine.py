"""Deterministic, explainable activity personalization.

Pure functions over immutable facts: no database, no network, no randomness, no LLM.
The same inputs always give the same recommendation, so it can be tested exhaustively,
explained precisely, and run without internet. Rules and thresholds come from
config/personalization.toml.

These are engagement rules (choosing a comfortable, enjoyable activity). Nothing here
measures or implies any medical condition.

Specification for client ports: packages/shared_docs/personalization-rules.md
"""

import statistics
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import StrEnum

from app.personalization.config import PersonalizationConfig

ALGORITHM_VERSION = "1.2.0"


class Reason(StrEnum):
    STOP_REQUESTED = "STOP_REQUESTED"
    FATIGUE_REPORTED_BREAK = "FATIGUE_REPORTED_BREAK"
    RECENT_FATIGUE_FEEDBACK = "RECENT_FATIGUE_FEEDBACK"
    RECENT_FATIGUE_OBSERVATION = "RECENT_FATIGUE_OBSERVATION"
    CAREGIVER_SEVERE_FATIGUE = "CAREGIVER_REPORTED_SEVERE_FATIGUE"
    LOW_EFFORT_FOR_FATIGUE = "LOW_EFFORT_FOR_FATIGUE"
    COLD_START_DEFAULT = "COLD_START_DEFAULT"
    INTEREST_MATCH = "INTEREST_MATCH"
    CONVERSATION_CONTEXT_MATCH = "CONVERSATION_CONTEXT_MATCH"
    ENJOYED_BEFORE = "ENJOYED_BEFORE"
    FAMILIAR_ACTIVITY = "FAMILIAR_ACTIVITY"
    LOW_ENGAGEMENT_SWITCH = "LOW_ENGAGEMENT_SWITCH"
    AVOID_REPETITION = "AVOID_REPETITION"
    ONLY_AVAILABLE_ACTIVITY = "ONLY_AVAILABLE_ACTIVITY"
    DIFFICULTY_INCREASED = "DIFFICULTY_INCREASED_AFTER_COMFORTABLE_SUCCESS"
    DIFFICULTY_DECREASED = "DIFFICULTY_DECREASED_AFTER_REPEATED_ERRORS"
    DIFFICULTY_HELD_COOLDOWN = "DIFFICULTY_HELD_TO_AVOID_OSCILLATION"
    DIFFICULTY_UNCHANGED = "DIFFICULTY_UNCHANGED"
    DIFFICULTY_STARTING_LEVEL = "DIFFICULTY_STARTING_LEVEL"
    HINTS_OFFERED = "HINTS_OFFERED_AFTER_ERRORS"
    MISSING_DATA_IGNORED = "MISSING_DATA_NOT_COUNTED_AS_ERROR"
    MEMORY_CONTENT_USED = "APPROVED_MEMORIES_USED"
    PERSONAL_ROUTINES_USED = "PERSONAL_ROUTINES_USED"
    DISLIKED_EXCLUDED = "DISLIKED_ACTIVITY_EXCLUDED"
    OFFLINE_CONTENT_FILTER = "LIMITED_TO_AVAILABLE_OFFLINE_CONTENT"
    LANGUAGE_CONTENT_FALLBACK = "LANGUAGE_CONTENT_FALLBACK"
    NO_AVAILABLE_ACTIVITY = "NO_AVAILABLE_ACTIVITY"
    # 1.2.0: support that follows what the person needed last time.
    HINT_SUPPORT = "HINT_SUPPORT_AFTER_HINT_USE"
    EASIER_ALTERNATIVE = "EASIER_ALTERNATIVE_AFTER_STRUGGLE"
    READ_ALOUD_FIRST = "INSTRUCTIONS_READ_ALOUD_FIRST"


class Action(StrEnum):
    ACTIVITY = "activity"
    BREAK = "break"
    STOP = "stop"
    NONE = "none"


class Outcome(StrEnum):
    SUCCESS = "success"  # comfortable success
    STRUGGLE = "struggle"  # repeated errors
    NEUTRAL = "neutral"  # fine, or not enough information
    INTERRUPTION = "interruption"  # stopped part-way (not because of fatigue)


# ---------------------------------------------------------------- facts


@dataclass(frozen=True)
class ActivityFact:
    id: str
    slug: str
    min_difficulty: int
    max_difficulty: int
    uses_memory_bank: bool


@dataclass(frozen=True)
class ResultFact:
    id: str
    activity_id: str
    completed_at: datetime
    difficulty: int
    score: float | None
    hints: int
    abandoned: bool
    engagement: str | None = None
    fatigue_reported: bool = False
    mean_response_ms: float | None = None
    # Times "Read aloud" was pressed during the run (1.2.0). None = not recorded (older app).
    instructions_repeated: int | None = None


@dataclass(frozen=True)
class ObservationFact:
    id: str
    category: str
    observed_at: datetime
    # Fatigue observations only: "mild" | "severe" | None (not given).
    fatigue_level: str | None = None


@dataclass(frozen=True)
class SessionEndFact:
    id: str
    ended_at: datetime
    end_reason: str | None


@dataclass(frozen=True)
class ContentAvailability:
    """What personal content an activity can use (from memory/routine retrieval)."""

    sufficient: bool
    memory_item_ids: tuple[str, ...] = ()
    routine_item_ids: tuple[str, ...] = ()
    matched_interests: tuple[str, ...] = ()


@dataclass(frozen=True)
class EngineInput:
    now: datetime
    language: str
    activities: tuple[ActivityFact, ...]
    results: tuple[ResultFact, ...]  # oldest first
    interests: tuple[str, ...] = ()
    disliked_slugs: frozenset[str] = frozenset()
    observations: tuple[ObservationFact, ...] = ()
    session_ends: tuple[SessionEndFact, ...] = ()
    content: dict[str, ContentAvailability] = field(default_factory=dict)
    stop_requested: bool = False
    fatigue_reported: bool = False
    available_slugs: frozenset[str] | None = None  # None = no device restriction
    # Topics from the current conversation, already resolved against stored tags. Transient:
    # they nudge the choice but never change approved interests.
    context_tags: tuple[str, ...] = ()


@dataclass(frozen=True)
class Support:
    """A stored record that supports a decision. `detail` never contains free text notes."""

    kind: str
    id: str
    detail: str


@dataclass
class DifficultyDecision:
    level: int
    reasons: list[Reason]
    supporting: list[Support]
    hints_enabled: bool
    # Consecutive struggles at the end of the history (1.2.0).
    trailing_struggles: int = 0


@dataclass
class Recommendation:
    action: Action
    activity: ActivityFact | None
    difficulty: int | None
    reasons: list[Reason]
    supporting: list[Support]
    hints_enabled: bool = False
    memory_item_ids: tuple[str, ...] = ()
    routine_item_ids: tuple[str, ...] = ()
    fallback_used: bool = False
    fallback_reason: str | None = None
    break_minutes: int | None = None
    # 1.2.0: read each question aloud when it appears (if read-aloud is on).
    read_aloud_first: bool = False

    @property
    def reason_codes(self) -> list[str]:
        seen: list[str] = []
        for reason in self.reasons:
            if reason.value not in seen:
                seen.append(reason.value)
        return seen


# ---------------------------------------------------------------- difficulty


def classify(result: ResultFact, baseline_ms: float | None, cfg: PersonalizationConfig) -> Outcome:
    rules = cfg.difficulty
    if result.abandoned:
        # Fatigue is handled by the fatigue rules, never as an error.
        return Outcome.NEUTRAL if result.fatigue_reported else Outcome.INTERRUPTION
    if result.score is None:
        return Outcome.NEUTRAL  # missing data is not a failure
    comfortable = (
        result.mean_response_ms is None
        or baseline_ms is None
        or result.mean_response_ms <= baseline_ms * rules.slow_response_factor
    )
    if (
        result.score >= rules.success_score
        and result.hints <= rules.max_hints_for_success
        and comfortable
    ):
        return Outcome.SUCCESS
    if result.score < rules.struggle_score:
        return Outcome.STRUGGLE
    return Outcome.NEUTRAL


def decide_difficulty(
    activity: ActivityFact, results: Sequence[ResultFact], cfg: PersonalizationConfig
) -> DifficultyDecision:
    """Replay this activity's results through the step rules (with hysteresis)."""
    rules = cfg.difficulty
    history = list(results)[-rules.history_window :]
    level = activity.min_difficulty
    if not history:
        return DifficultyDecision(level, [Reason.DIFFICULTY_STARTING_LEVEL], [], False)

    successes = struggles = 0
    trailing_struggles = 0  # consecutive struggles at the end of the history (not reset by steps)
    since_change = rules.min_results_between_changes
    response_times: list[float] = []
    last_change: tuple[str, ResultFact] | None = None
    pending_blocked = False

    for result in history:
        baseline = statistics.median(response_times) if response_times else None
        outcome = classify(result, baseline, cfg)
        since_change += 1
        if outcome is Outcome.SUCCESS:
            successes, struggles = successes + 1, 0
        elif outcome is Outcome.STRUGGLE:
            struggles, successes = struggles + 1, 0
        # NEUTRAL and INTERRUPTION leave streaks untouched: no data is not a failure.
        if outcome is Outcome.STRUGGLE:
            trailing_struggles += 1
        elif outcome is Outcome.SUCCESS:
            trailing_struggles = 0

        pending_blocked = False
        if successes >= rules.increase_after_successes and level < activity.max_difficulty:
            if since_change >= rules.min_results_between_changes:
                level, successes, since_change = level + 1, 0, 0
                last_change = ("up", result)
            else:
                pending_blocked = True
        elif struggles >= rules.decrease_after_struggles and level > activity.min_difficulty:
            if since_change >= rules.min_results_between_changes:
                level, struggles, since_change = level - 1, 0, 0
                last_change = ("down", result)
            else:
                pending_blocked = True

        if result.mean_response_ms is not None and not result.abandoned:
            response_times.append(result.mean_response_ms)

    level = max(activity.min_difficulty, min(activity.max_difficulty, level))
    latest = history[-1]
    reasons: list[Reason] = []
    supporting = [
        Support(
            "activity_result", r.id, f"difficulty {r.difficulty}, completed {r.completed_at.date()}"
        )
        for r in history[-3:]
    ]
    if last_change is not None and last_change[1] is latest:
        reasons.append(
            Reason.DIFFICULTY_INCREASED if last_change[0] == "up" else Reason.DIFFICULTY_DECREASED
        )
    elif pending_blocked:
        reasons.append(Reason.DIFFICULTY_HELD_COOLDOWN)
    else:
        reasons.append(Reason.DIFFICULTY_UNCHANGED)
    if latest.score is None and not latest.abandoned:
        reasons.append(Reason.MISSING_DATA_IGNORED)

    hints = trailing_struggles >= rules.hints_after_struggles
    if hints:
        reasons.append(Reason.HINTS_OFFERED)
    return DifficultyDecision(level, reasons, supporting, hints, trailing_struggles)


def hint_heavy(results: Sequence[ResultFact], cfg: PersonalizationConfig) -> list[ResultFact]:
    """This activity's recent results that needed many hints, if they form a pattern."""
    rules = cfg.support
    recent = [r for r in results if not r.abandoned][-rules.hint_window :]
    heavy = [r for r in recent if r.hints >= rules.hint_heavy_min_hints]
    return heavy if len(heavy) >= rules.hint_heavy_results else []


def struggling_at_easiest(
    activity: ActivityFact, results: Sequence[ResultFact], cfg: PersonalizationConfig
) -> list[ResultFact]:
    """The latest struggles if the person is struggling at this activity's easiest level."""
    decision = decide_difficulty(activity, results, cfg)
    needed = cfg.support.struggle_at_easiest_results
    if decision.level == activity.min_difficulty and decision.trailing_struggles >= needed:
        return [r for r in results if r.score is not None and not r.abandoned][-needed:]
    return []


def read_aloud_first(results: Sequence[ResultFact], cfg: PersonalizationConfig) -> list[ResultFact]:
    """Recent results where "Read aloud" was pressed often enough to read questions first."""
    rules = cfg.support
    recent = list(results)[-rules.instruction_window :]
    pressed = [r for r in recent if (r.instructions_repeated or 0) > 0]
    total = sum(r.instructions_repeated or 0 for r in recent)
    return pressed if total >= rules.read_aloud_after_repeats else []


# ---------------------------------------------------------------- selection


def _within(now: datetime, moment: datetime, hours: float) -> bool:
    return now - timedelta(hours=hours) <= moment <= now + timedelta(minutes=5)


def _fatigue_signals(
    inp: EngineInput, cfg: PersonalizationConfig
) -> tuple[bool, list[Reason], list[Support]]:
    """Returns (explicit_now, reasons, supporting). explicit_now → offer a break."""
    rules = cfg.fatigue
    reasons: list[Reason] = []
    supporting: list[Support] = []
    latest = inp.results[-1] if inp.results else None
    explicit_now = inp.fatigue_reported or bool(
        latest
        and latest.fatigue_reported
        and _within(inp.now, latest.completed_at, rules.feedback_window_hours)
    )
    if inp.fatigue_reported:
        supporting.append(Support("request", "fatigue_reported", "tiredness reported just now"))
    if latest and latest.fatigue_reported and explicit_now:
        supporting.append(
            Support("activity_result", latest.id, "tiredness reported after this activity")
        )

    for r in inp.results:
        if r.fatigue_reported and _within(inp.now, r.completed_at, rules.feedback_window_hours):
            if not (latest and r.id == latest.id):
                reasons.append(Reason.RECENT_FATIGUE_FEEDBACK)
                supporting.append(Support("activity_result", r.id, "tiredness reported recently"))
    for s in inp.session_ends:
        if s.end_reason == "fatigue_detected" and _within(
            inp.now, s.ended_at, rules.feedback_window_hours
        ):
            reasons.append(Reason.RECENT_FATIGUE_FEEDBACK)
            supporting.append(
                Support("activity_session", s.id, "session ended early for tiredness")
            )
    for o in inp.observations:
        if o.category == "fatigue" and _within(
            inp.now, o.observed_at, rules.observation_window_hours
        ):
            if o.fatigue_level == "severe":
                # A caregiver said "very tired": a rest, not another activity.
                explicit_now = True
                reasons.append(Reason.CAREGIVER_SEVERE_FATIGUE)
            else:
                reasons.append(Reason.RECENT_FATIGUE_OBSERVATION)
            supporting.append(
                Support(
                    "caregiver_observation",
                    o.id,
                    f"caregiver noted tiredness at {o.observed_at:%H:%M} UTC"
                    + (f" ({o.fatigue_level})" if o.fatigue_level else ""),
                )
            )
    return explicit_now, reasons, supporting


def _language_ok(slug: str, language: str, cfg: PersonalizationConfig) -> bool:
    langs = cfg.content_languages.get(slug, ["*"])
    return "*" in langs or language in langs


def recommend(inp: EngineInput, cfg: PersonalizationConfig) -> Recommendation:
    # 1. A direct stop request always wins.
    if inp.stop_requested:
        return Recommendation(
            Action.STOP,
            None,
            None,
            [Reason.STOP_REQUESTED],
            [Support("request", "stop_requested", "the patient asked to stop")],
        )

    reasons: list[Reason] = []
    supporting: list[Support] = []

    # 2. Candidate filtering (each filter is explained, and relaxed only if it would leave nothing).
    candidates = list(inp.activities)
    if inp.available_slugs is not None:
        narrowed = [a for a in candidates if a.slug in inp.available_slugs]
        if len(narrowed) < len(candidates):
            reasons.append(Reason.OFFLINE_CONTENT_FILTER)
        candidates = narrowed
    if inp.disliked_slugs:
        narrowed = [a for a in candidates if a.slug not in inp.disliked_slugs]
        if len(narrowed) < len(candidates) and narrowed:
            reasons.append(Reason.DISLIKED_EXCLUDED)
            supporting.append(
                Support(
                    "preference", "disliked_activity_slugs", ", ".join(sorted(inp.disliked_slugs))
                )
            )
            candidates = narrowed
    # Activities that need personal content are only offered when enough approved content exists.
    candidates = [
        a for a in candidates if inp.content.get(a.slug, ContentAvailability(True)).sufficient
    ]
    fallback_reason: str | None = None
    language_ok = [a for a in candidates if _language_ok(a.slug, inp.language, cfg)]
    if language_ok:
        candidates = language_ok
    elif candidates:
        reasons.append(Reason.LANGUAGE_CONTENT_FALLBACK)
        fallback_reason = "language_content_unavailable"

    if not candidates:
        return Recommendation(
            Action.NONE,
            None,
            None,
            [*reasons, Reason.NO_AVAILABLE_ACTIVITY],
            supporting,
            fallback_used=True,
            fallback_reason="no_available_activity",
        )

    by_id = {a.id: a for a in inp.activities}

    # 3. Fatigue.
    explicit_fatigue, fatigue_reasons, fatigue_support = _fatigue_signals(inp, cfg)
    tired = explicit_fatigue or bool(fatigue_reasons)
    if tired:
        easy = [a for a in candidates if a.slug in cfg.fatigue.low_effort_slugs]
        if easy:
            candidates = easy
        reasons += fatigue_reasons
        supporting += fatigue_support

    # 4. Low engagement: several recent interruptions / "not enjoyed" → switch activity.
    recent_all = inp.results[-cfg.selection.low_engagement_window :]
    unhappy = [
        r
        for r in recent_all
        if (r.abandoned and not r.fatigue_reported) or r.engagement == "not_enjoyed"
    ]
    avoid: set[str] = set()
    if len(unhappy) >= cfg.selection.low_engagement_threshold:
        avoid = {r.activity_id for r in unhappy}
        if any(a.id not in avoid for a in candidates):
            reasons.append(Reason.LOW_ENGAGEMENT_SWITCH)
            supporting += [
                Support("activity_result", r.id, "interrupted or not enjoyed") for r in unhappy
            ]
        else:
            avoid = set()

    # 5. Score candidates.
    sel = cfg.selection
    cold_start = not inp.results
    last_activity = inp.results[-1].activity_id if inp.results else None
    recent_ids = [r.activity_id for r in inp.results[-sel.recent_window :]]
    last_played: dict[str, datetime] = {}
    for r in inp.results:
        last_played[r.activity_id] = r.completed_at
    interests = {t.lower() for t in inp.interests}

    def score(a: ActivityFact) -> tuple[int, list[Reason], list[Support]]:
        s, why, sup = 0, [], []
        if cold_start and a.slug in sel.cold_start_order:
            s += len(sel.cold_start_order) - sel.cold_start_order.index(a.slug)
        content = inp.content.get(a.slug)
        tags = set(cfg.activity_interest_tags.get(a.slug, []))
        if content:
            tags |= set(content.matched_interests)
        matched = sorted(interests & tags)
        if matched:
            s += min(sel.interest_bonus_cap, sel.interest_match_bonus * len(matched))
            why.append(Reason.INTEREST_MATCH)
            sup.append(
                Support("preference", "interests", "approved interests: " + ", ".join(matched))
            )
        context = sorted({t.lower() for t in inp.context_tags} & tags - set(matched))
        if context:
            s += min(sel.interest_bonus_cap, sel.context_match_bonus * len(context))
            why.append(Reason.CONVERSATION_CONTEXT_MATCH)
            sup.append(
                Support("conversation", "context_tags", "talked about: " + ", ".join(context))
            )
        mine = [r for r in inp.results if r.activity_id == a.id][-5:]
        enjoyed = sum(r.engagement == "enjoyed" for r in mine)
        if enjoyed:
            s += sel.enjoyed_bonus * enjoyed
            why.append(Reason.ENJOYED_BEFORE)
            sup += [
                Support("activity_result", r.id, "enjoyed")
                for r in mine
                if r.engagement == "enjoyed"
            ][-2:]
        s -= sel.not_enjoyed_penalty * sum(r.engagement == "not_enjoyed" for r in mine)
        s -= sel.interruption_penalty * sum(r.abandoned and not r.fatigue_reported for r in mine)
        if any(not r.abandoned for r in mine):
            s += sel.familiar_bonus
            why.append(Reason.FAMILIAR_ACTIVITY)
        if a.id == last_activity:
            s -= sel.repeat_last_penalty
        s -= sel.repeat_recent_penalty * recent_ids.count(a.id)
        if a.id in avoid:
            s -= 10_000
        if hard_at_easiest.get(a.id):
            s -= sel_support.struggle_at_easiest_penalty
        return s, why, sup

    # Repeated struggles at an activity's easiest level: prefer a different activity.
    sel_support = cfg.support
    hard_at_easiest = {
        a.id: struggling_at_easiest(a, [r for r in inp.results if r.activity_id == a.id], cfg)
        for a in candidates
    }

    scored = []
    for a in candidates:
        s, why, sup = score(a)
        never = a.id not in last_played
        order_key = sel.cold_start_order.index(a.slug) if a.slug in sel.cold_start_order else 99
        played_at = last_played.get(a.id, datetime.min.replace(tzinfo=inp.now.tzinfo))
        scored.append(((-s, not never, played_at, order_key, a.slug), a, why, sup))
    scored.sort(key=lambda item: item[0])
    _, chosen, why, sup = scored[0]
    reasons += why
    supporting += sup

    if len(candidates) == 1:
        reasons.append(Reason.ONLY_AVAILABLE_ACTIVITY)
    elif (
        last_activity is not None
        and chosen.id != last_activity
        and last_activity in {a.id for a in candidates}
    ):
        reasons.append(Reason.AVOID_REPETITION)
    if cold_start:
        reasons.append(Reason.COLD_START_DEFAULT)
        fallback_reason = fallback_reason or "no_history"
    avoided = [a for a in candidates if hard_at_easiest[a.id] and a.id != chosen.id]
    if avoided:
        reasons.append(Reason.EASIER_ALTERNATIVE)
        supporting += [
            Support("activity_result", r.id, "struggled at the easiest level")
            for a in avoided
            for r in hard_at_easiest[a.id]
        ]

    # 6. Difficulty for the chosen activity.
    decision = decide_difficulty(
        chosen, [r for r in inp.results if r.activity_id == chosen.id], cfg
    )
    difficulty = decision.level
    reasons += decision.reasons
    supporting += decision.supporting
    if tired:
        difficulty = chosen.min_difficulty
        reasons.append(Reason.LOW_EFFORT_FOR_FATIGUE)
    heavy = hint_heavy([r for r in inp.results if r.activity_id == chosen.id], cfg)
    if heavy:
        reasons.append(Reason.HINT_SUPPORT)
        supporting += [Support("activity_result", r.id, f"{r.hints} hints used") for r in heavy]
    repeated = read_aloud_first(inp.results, cfg)
    if repeated:
        reasons.append(Reason.READ_ALOUD_FIRST)
        supporting += [
            Support("activity_result", r.id, f"question read aloud {r.instructions_repeated}x")
            for r in repeated
        ]

    content = inp.content.get(chosen.slug, ContentAvailability(True))
    if content.memory_item_ids:
        reasons.append(Reason.MEMORY_CONTENT_USED)
        supporting += [
            Support("memory_item", mid, "approved memory") for mid in content.memory_item_ids
        ]
    if content.routine_item_ids:
        reasons.append(Reason.PERSONAL_ROUTINES_USED)
        supporting += [
            Support("routine_item", rid, "patient's own routine")
            for rid in content.routine_item_ids
        ]

    # Deduplicate supporting records, keep order.
    unique: list[Support] = []
    for item in supporting:
        if item not in unique:
            unique.append(item)

    return Recommendation(
        action=Action.BREAK if explicit_fatigue else Action.ACTIVITY,
        activity=by_id[chosen.id],
        difficulty=difficulty,
        reasons=reasons,
        supporting=unique,
        hints_enabled=decision.hints_enabled or tired or bool(heavy),
        memory_item_ids=content.memory_item_ids,
        routine_item_ids=content.routine_item_ids,
        fallback_used=fallback_reason is not None,
        fallback_reason=fallback_reason,
        break_minutes=cfg.fatigue.break_minutes if explicit_fatigue else None,
        read_aloud_first=bool(repeated),
    )
