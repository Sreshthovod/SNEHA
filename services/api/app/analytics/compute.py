"""Descriptive activity metrics, own-baseline comparison and review flags.

Pure functions over pandas DataFrames (no database access), so every number can be
tested exactly. Definitions are listed in `METHODOLOGY` and printed in every report.

Nothing here measures, stages or predicts any medical condition. Review flags say only
that a REPEATED change in game behaviour may be worth a caregiver or clinician looking at.
"""

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

import numpy as np
import pandas as pd

from app.analytics.config import AnalyticsConfig

METHOD_VERSION = "analytics-1.0.0"

DISCLAIMER = (
    "This summary describes how the person used SNEHA's activities. It is not a medical "
    "assessment and does not diagnose, stage or predict any condition. Activity results are "
    "affected by mood, sleep, eyesight, hearing, familiarity with the phone, difficulty level "
    "and many other everyday factors. Review prompts only suggest that a repeated change may "
    "be worth discussing; they are not findings."
)

METHODOLOGY = [
    "Period: calendar days in the person's own timezone, first and last day included.",
    "Results: one row per finished or stopped activity. Days without results are reported as "
    "missing data and are never counted as low performance.",
    "Completion rate: completed sessions ÷ sessions that ended (completed or stopped).",
    "Interruption rate: activities stopped part-way ÷ all activities. Stops because of "
    "tiredness are counted separately as tiredness signals.",
    "Accuracy: mean score (0–1) of finished, scored activities only. Unscored activities "
    "(such as Story time) are excluded.",
    "Response time: median of each activity's average response time, where recorded.",
    "Hints: hints used per activity, and the share of activities with at least one hint.",
    "Session duration: median minutes from session start to end, for ended sessions.",
    "Engagement: answers to 'Did you enjoy this?'. Unanswered is not treated as negative.",
    "Baseline: the same person's results in the window just before the period. A comparison "
    "is only made when the baseline and the period both meet minimum amounts of data.",
    "Review prompts require a large enough overall change AND the change on most days with "
    "data, so a single session or day can never raise one.",
]


# ---------------------------------------------------------------- frames

RESULT_COLUMNS = [
    "id",
    "activity_id",
    "slug",
    "title",
    "session_id",
    "completed_at",
    "day",
    "difficulty",
    "score",
    "hints",
    "abandoned",
    "engagement",
    "fatigue_reported",
    "mean_response_ms",
    "duration_ms",
]
SESSION_COLUMNS = ["id", "started_at", "ended_at", "day", "status", "end_reason"]
OBSERVATION_COLUMNS = ["id", "observed_at", "day", "category", "status", "source"]


def empty(columns: list[str]) -> pd.DataFrame:
    return pd.DataFrame({c: pd.Series(dtype="object") for c in columns})


def _num(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def _float(value: Any, digits: int = 4) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if np.isnan(number):
        return None
    return round(number, digits)


def _rate(numerator: int, denominator: int) -> float | None:
    return round(numerator / denominator, 4) if denominator else None


# ---------------------------------------------------------------- core metrics


def elapsed_days(from_date: date, to_date: date, today: date) -> list[date]:
    last = min(to_date, today)
    return [from_date + timedelta(days=i) for i in range((last - from_date).days + 1)]


def longest_run(days: list[date], missing: set[date]) -> int:
    best = run = 0
    for day in days:
        run = run + 1 if day in missing else 0
        best = max(best, run)
    return best


def _scored(results: pd.DataFrame) -> pd.DataFrame:
    return results[results["score"].notna() & ~results["abandoned"].astype(bool)]


def totals(results: pd.DataFrame, sessions: pd.DataFrame) -> dict[str, Any]:
    n = len(results)
    scored = _scored(results)
    interrupted = int(
        (results["abandoned"].astype(bool) & ~results["fatigue_reported"].astype(bool)).sum()
    )
    ended = sessions[sessions["ended_at"].notna()]
    completed = int((ended["status"] == "completed").sum())
    stopped = int((ended["status"] == "abandoned").sum())
    durations = (
        (
            pd.to_datetime(ended["ended_at"], utc=True)
            - pd.to_datetime(ended["started_at"], utc=True)
        )
        .dt.total_seconds()
        .div(60)
        if len(ended)
        else pd.Series(dtype="float64")
    )
    rt = _num(results["mean_response_ms"]).dropna()
    hints = _num(results["hints"]).fillna(0)
    return {
        "results": n,
        "scored_results": len(scored),
        "interrupted_results": interrupted,
        "sessions_started": len(sessions),
        "sessions_ended": len(ended),
        "sessions_completed": completed,
        "sessions_stopped": stopped,
        "sessions_ended_for_fatigue": int((ended["end_reason"] == "fatigue_detected").sum()),
        "completion_rate": _rate(completed, len(ended)),
        "interruption_rate": _rate(interrupted, n),
        "accuracy_mean": _float(_num(scored["score"]).mean()) if len(scored) else None,
        "accuracy_median": _float(_num(scored["score"]).median()) if len(scored) else None,
        "median_response_ms": _float(rt.median(), 1) if len(rt) else None,
        "hints_per_result": _float(hints.mean(), 3) if n else None,
        "share_results_with_hints": _rate(int((hints > 0).sum()), n),
        "median_session_minutes": _float(durations.median(), 1) if len(durations) else None,
        "total_session_minutes": _float(durations.sum(), 1) if len(durations) else 0.0,
        "mean_difficulty": _float(_num(results["difficulty"]).mean(), 2) if n else None,
    }


def engagement(results: pd.DataFrame) -> dict[str, int]:
    counts = results["engagement"].value_counts(dropna=True)
    return {
        "enjoyed": int(counts.get("enjoyed", 0)),
        "neutral": int(counts.get("neutral", 0)),
        "not_enjoyed": int(counts.get("not_enjoyed", 0)),
        "unanswered": int(results["engagement"].isna().sum()),
    }


def per_activity(results: pd.DataFrame) -> list[dict[str, Any]]:
    rows = []
    for (activity_id, slug, title), group in results.groupby(
        ["activity_id", "slug", "title"], sort=True
    ):
        scored = _scored(group)
        rt = _num(group["mean_response_ms"]).dropna()
        eng = engagement(group)
        rows.append(
            {
                "activity_id": activity_id,
                "slug": slug,
                "title": title,
                "results": len(group),
                "completed": int((~group["abandoned"].astype(bool)).sum()),
                "interrupted": int(group["abandoned"].astype(bool).sum()),
                "accuracy_mean": _float(_num(scored["score"]).mean()) if len(scored) else None,
                "median_response_ms": _float(rt.median(), 1) if len(rt) else None,
                "hints_per_result": _float(_num(group["hints"]).fillna(0).mean(), 3),
                "mean_difficulty": _float(_num(group["difficulty"]).mean(), 2),
                "enjoyed": eng["enjoyed"],
                "not_enjoyed": eng["not_enjoyed"],
                "last_played": max(group["day"]),
            }
        )
    return rows


def preferences(activities: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Ranked by enjoyment share (of answered), then by how often chosen. Descriptive only."""

    def key(a: dict[str, Any]) -> tuple:
        answered = a["enjoyed"] + a["not_enjoyed"]
        share = a["enjoyed"] / answered if answered else 0.0
        return (-share, -a["results"], a["slug"])

    return [
        {
            "slug": a["slug"],
            "title": a["title"],
            "results": a["results"],
            "enjoyed": a["enjoyed"],
            "not_enjoyed": a["not_enjoyed"],
        }
        for a in sorted(activities, key=key)
    ]


def daily(results: pd.DataFrame, days: list[date]) -> list[dict[str, Any]]:
    rows = []
    by_day = {d: g for d, g in results.groupby("day")} if len(results) else {}
    for day in days:
        group = by_day.get(day)
        if group is None or not len(group):
            rows.append(
                {
                    "day": day,
                    "has_data": False,
                    "results": 0,
                    "interrupted": 0,
                    "accuracy_mean": None,
                    "median_response_ms": None,
                    "hints_per_result": None,
                }
            )
            continue
        scored = _scored(group)
        rt = _num(group["mean_response_ms"]).dropna()
        rows.append(
            {
                "day": day,
                "has_data": True,
                "results": len(group),
                "interrupted": int(
                    (
                        group["abandoned"].astype(bool) & ~group["fatigue_reported"].astype(bool)
                    ).sum()
                ),
                "accuracy_mean": _float(_num(scored["score"]).mean()) if len(scored) else None,
                "median_response_ms": _float(rt.median(), 1) if len(rt) else None,
                "hints_per_result": _float(_num(group["hints"]).fillna(0).mean(), 3),
            }
        )
    return rows


# ---------------------------------------------------------------- baseline


@dataclass
class Baseline:
    status: str  # "compared" | "insufficient_data"
    from_date: date
    to_date: date
    results: int
    days: int
    required_results: int
    required_days: int
    metrics: dict[str, Any] = field(default_factory=dict)
    comparisons: list[dict[str, Any]] = field(default_factory=list)
    period_sufficient: bool = False


def baseline(
    baseline_results: pd.DataFrame,
    period_results: pd.DataFrame,
    baseline_from: date,
    baseline_to: date,
    cfg: AnalyticsConfig,
) -> Baseline:
    days = int(baseline_results["day"].nunique()) if len(baseline_results) else 0
    period_days = int(period_results["day"].nunique()) if len(period_results) else 0
    period_ok = len(period_results) >= cfg.period.min_results and period_days >= cfg.period.min_days
    enough = len(baseline_results) >= cfg.baseline.min_results and days >= cfg.baseline.min_days
    result = Baseline(
        status="compared" if enough and period_ok else "insufficient_data",
        from_date=baseline_from,
        to_date=baseline_to,
        results=len(baseline_results),
        days=days,
        required_results=cfg.baseline.min_results,
        required_days=cfg.baseline.min_days,
        period_sufficient=period_ok,
    )
    if result.status != "compared":
        return result
    empty_sessions = empty(SESSION_COLUMNS)
    base = totals(baseline_results, empty_sessions)
    cur = totals(period_results, empty_sessions)
    result.metrics = base
    for metric, unit in [
        ("accuracy_mean", "score 0–1"),
        ("median_response_ms", "ms"),
        ("interruption_rate", "share"),
        ("hints_per_result", "hints"),
        ("mean_difficulty", "level"),
    ]:
        b, c = base[metric], cur[metric]
        result.comparisons.append(
            {
                "metric": metric,
                "unit": unit,
                "baseline": b,
                "current": c,
                "change": _float(c - b) if b is not None and c is not None else None,
            }
        )
    return result


# ---------------------------------------------------------------- review flags


@dataclass
class Flag:
    rule_id: str
    kind: str  # "change" | "data" | "context"
    title: str
    explanation: str
    numbers: dict[str, Any]
    observation_ids: list[str] = field(default_factory=list)


@dataclass
class NotEvaluated:
    rule_id: str
    reason: str


def _share(values: list[bool]) -> float:
    return sum(values) / len(values) if values else 0.0


def review_flags(
    period_results: pd.DataFrame,
    baseline_results: pd.DataFrame,
    sessions: pd.DataFrame,
    observations: pd.DataFrame,
    base: Baseline,
    days: list[date],
    cfg: AnalyticsConfig,
) -> tuple[list[Flag], list[NotEvaluated]]:
    rules = cfg.review
    flags: list[Flag] = []
    skipped: list[NotEvaluated] = []
    context_ids = list(observations["id"]) if len(observations) else []
    daily_rows = [r for r in daily(period_results, days) if r["has_data"]]

    # --- changes against the person's own baseline -------------------------------
    change_rules = [
        "ACCURACY_LOWER_THAN_USUAL",
        "SLOWER_RESPONSES_THAN_USUAL",
        "MORE_INTERRUPTIONS_THAN_USUAL",
        "MORE_HINTS_THAN_USUAL",
    ]
    if base.status != "compared":
        reason = (
            "not enough activity in this period"
            if not base.period_sufficient
            else "not enough earlier activity to know what is usual for this person"
        )
        skipped += [NotEvaluated(rule, reason) for rule in change_rules]
    else:
        b = base.metrics
        cur = totals(period_results, empty(SESSION_COLUMNS))

        # Accuracy: also require that difficulty did not go up
        # (a harder level explains lower scores).
        b_acc, c_acc = b["accuracy_mean"], cur["accuracy_mean"]
        acc_days = [r for r in daily_rows if r["accuracy_mean"] is not None]
        if b_acc is None or c_acc is None or len(acc_days) < cfg.period.min_days:
            skipped.append(NotEvaluated("ACCURACY_LOWER_THAN_USUAL", "too few scored activities"))
        else:
            share = _share([r["accuracy_mean"] < b_acc - rules.accuracy_drop / 2 for r in acc_days])
            harder = (cur["mean_difficulty"] or 0) > (b["mean_difficulty"] or 0) + 0.5
            if (
                b_acc - c_acc >= rules.accuracy_drop
                and share >= rules.min_share_of_days
                and not harder
            ):
                flags.append(
                    Flag(
                        "ACCURACY_LOWER_THAN_USUAL",
                        "change",
                        "Scores lower than this person's usual",
                        f"Average score was {c_acc:.2f} compared with a usual {b_acc:.2f}, "
                        f"lower on {share:.0%} of days with scored activities, "
                        "at a similar difficulty level.",
                        {
                            "baseline": b_acc,
                            "current": c_acc,
                            "threshold_drop": rules.accuracy_drop,
                            "share_of_days": round(share, 3),
                            "days_considered": len(acc_days),
                            "baseline_difficulty": b["mean_difficulty"],
                            "current_difficulty": cur["mean_difficulty"],
                        },
                        context_ids,
                    )
                )

        b_rt, c_rt = b["median_response_ms"], cur["median_response_ms"]
        rt_days = [r for r in daily_rows if r["median_response_ms"] is not None]
        if b_rt is None or c_rt is None or len(rt_days) < cfg.period.min_days:
            skipped.append(
                NotEvaluated("SLOWER_RESPONSES_THAN_USUAL", "too few recorded response times")
            )
        else:
            limit = b_rt * (1 + rules.response_time_increase / 2)
            share = _share([r["median_response_ms"] > limit for r in rt_days])
            if (
                c_rt >= b_rt * (1 + rules.response_time_increase)
                and share >= rules.min_share_of_days
            ):
                flags.append(
                    Flag(
                        "SLOWER_RESPONSES_THAN_USUAL",
                        "change",
                        "Responses slower than this person's usual",
                        f"Typical response time was {c_rt / 1000:.1f} s compared with a usual "
                        f"{b_rt / 1000:.1f} s, slower on {share:.0%} of days with recorded times.",
                        {
                            "baseline_ms": b_rt,
                            "current_ms": c_rt,
                            "threshold_increase": rules.response_time_increase,
                            "share_of_days": round(share, 3),
                            "days_considered": len(rt_days),
                        },
                        context_ids,
                    )
                )

        b_int, c_int = b["interruption_rate"], cur["interruption_rate"]
        if len(sessions) < rules.min_sessions_for_interruptions or b_int is None or c_int is None:
            skipped.append(NotEvaluated("MORE_INTERRUPTIONS_THAN_USUAL", "too few sessions"))
        else:
            share = _share([(r["interrupted"] / r["results"]) > b_int for r in daily_rows])
            if (
                c_int - b_int >= rules.interruption_rate_increase
                and share >= rules.min_share_of_days
            ):
                flags.append(
                    Flag(
                        "MORE_INTERRUPTIONS_THAN_USUAL",
                        "change",
                        "Activities stopped part-way more often",
                        f"{c_int:.0%} of activities were stopped part-way compared with a usual "
                        f"{b_int:.0%}, on {share:.0%} of days with activity.",
                        {
                            "baseline": b_int,
                            "current": c_int,
                            "threshold_increase": rules.interruption_rate_increase,
                            "share_of_days": round(share, 3),
                            "sessions": len(sessions),
                        },
                        context_ids,
                    )
                )

        b_h, c_h = b["hints_per_result"], cur["hints_per_result"]
        if b_h is None or c_h is None:
            skipped.append(NotEvaluated("MORE_HINTS_THAN_USUAL", "no hint data"))
        else:
            share = _share(
                [r["hints_per_result"] > b_h + rules.hint_rate_increase / 2 for r in daily_rows]
            )
            if c_h - b_h >= rules.hint_rate_increase and share >= rules.min_share_of_days:
                flags.append(
                    Flag(
                        "MORE_HINTS_THAN_USUAL",
                        "change",
                        "More hints used than usual",
                        f"{c_h:.1f} hints per activity compared with a usual {b_h:.1f}, "
                        f"higher on {share:.0%} of days with activity.",
                        {
                            "baseline": b_h,
                            "current": c_h,
                            "threshold_increase": rules.hint_rate_increase,
                            "share_of_days": round(share, 3),
                        },
                        context_ids,
                    )
                )

    # --- engagement (no baseline needed) ------------------------------------------
    answered = (
        period_results[period_results["engagement"].notna()]
        if len(period_results)
        else period_results
    )
    if len(answered) < rules.low_engagement_min_answers:
        skipped.append(NotEvaluated("LOW_ENJOYMENT", "too few enjoyment answers"))
    else:
        not_enjoyed = int((answered["engagement"] == "not_enjoyed").sum())
        share = not_enjoyed / len(answered)
        answer_days = int(answered["day"].nunique())
        if share >= rules.low_engagement_share and answer_days >= cfg.period.min_days:
            flags.append(
                Flag(
                    "LOW_ENJOYMENT",
                    "change",
                    "Activities often not enjoyed",
                    f"{not_enjoyed} of {len(answered)} answers ({share:.0%}) said the activity "
                    "was not "
                    f"enjoyed, across {answer_days} days. Different activities may suit better.",
                    {
                        "not_enjoyed": not_enjoyed,
                        "answers": len(answered),
                        "share": round(share, 3),
                        "threshold_share": rules.low_engagement_share,
                        "days": answer_days,
                    },
                    context_ids,
                )
            )

    # --- data completeness ----------------------------------------------------------
    active = set(period_results["day"]) if len(period_results) else set()
    missing = {d for d in days if d not in active}
    if len(days) < 3:
        skipped.append(NotEvaluated("DATA_GAP", "period has fewer than 3 elapsed days"))
    else:
        run = longest_run(days, missing)
        share = len(missing) / len(days)
        if share >= rules.data_gap_share or run >= rules.data_gap_consecutive_days:
            flags.append(
                Flag(
                    "DATA_GAP",
                    "data",
                    "Days without any activity",
                    f"No activity was recorded on {len(missing)} of {len(days)} days (longest gap "
                    f"{run} days). This may be a break, a phone or sync problem, "
                    "or simply less use; "
                    "it is not counted as low performance.",
                    {
                        "missing_days": len(missing),
                        "elapsed_days": len(days),
                        "longest_gap_days": run,
                        "threshold_share": rules.data_gap_share,
                        "threshold_consecutive": rules.data_gap_consecutive_days,
                    },
                )
            )

    # --- tiredness signals (context) ------------------------------------------------
    signal_days: list[date] = []
    if len(period_results):
        signal_days += list(period_results[period_results["fatigue_reported"].astype(bool)]["day"])
    if len(sessions):
        signal_days += list(sessions[sessions["end_reason"] == "fatigue_detected"]["day"])
    fatigue_obs = (
        observations[observations["category"] == "fatigue"] if len(observations) else observations
    )
    if len(fatigue_obs):
        signal_days += list(fatigue_obs["day"])
    if (
        len(signal_days) >= rules.fatigue_min_signals
        and len(set(signal_days)) >= rules.fatigue_min_days
    ):
        flags.append(
            Flag(
                "REPEATED_TIREDNESS",
                "context",
                "Tiredness mentioned on several days",
                f"Tiredness was reported or noted {len(signal_days)} times on "
                f"{len(set(signal_days))} "
                "different days. Shorter or earlier sessions may help.",
                {
                    "signals": len(signal_days),
                    "days": len(set(signal_days)),
                    "threshold_signals": rules.fatigue_min_signals,
                    "threshold_days": rules.fatigue_min_days,
                },
                list(fatigue_obs["id"]) if len(fatigue_obs) else [],
            )
        )
    return flags, skipped
