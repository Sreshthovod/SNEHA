# Caregiver analytics, review and reporting: inspection and plan

Date: 2026-10-18. Extends the existing analytics (`services/api/app/analytics/`), review items
(`app/review/`) and PDF (`app/reports/`). No second analytics system, no ML.

## 1. What existed (inspected)

| Piece | Where | State |
|---|---|---|
| Descriptive metrics from stored results and sessions | `analytics/compute.py` (`totals`, `per_activity`, `daily`, `engagement`, `preferences`) | ✅ real records only; missing days listed, never filled |
| Own-baseline comparison | `compute.baseline` (previous 28 days, minimums of 10 results on 4 days) | ⚠️ **mixes all activities**: a week of harder games looks like "lower scores" |
| Review prompts | `compute.review_flags`: needs a large overall change *and* the change on ≥ 66 % of days | ✅ conservative; ⚠️ uses the mixed baseline |
| Review items | `review_items` (0011): snapshot of numbers, caregiver confirm/dismiss with reason; clinicians see confirmed only | ⚠️ no list of the records behind an item, no stated limitations, no way to **add context** without deciding |
| Activity events (0009) | answers, hints (asked vs automatic), pauses (person vs screen left), stop requests, rests, in-activity adjustments, read-aloud presses | ❌ **recorded but never summarised** |
| Session states | completed / stopped / tiredness / interrupted (`timeout`) / still open | ⚠️ "interrupted" and "still open" not shown separately |
| Offline data not yet synced | phone outbox; server knows each phone's last sync (0014) | ❌ **reports never say they may be incomplete** |
| 8–9 day PDF | `reports/pdf.py`: recorded / automated / caregiver-confirmed parts, tiredness by source | ⚠️ none of the above gaps reflected |

## 2. Metric definitions (all derived from stored records; period = inclusive local dates)

| Metric | Source | Calculation | Fact or derived | Missing data |
|---|---|---|---|---|
| Sessions started / completed / stopped / ended for tiredness / interrupted / still open | `activity_sessions` started in the period | counts by `status` + `end_reason` | fact | an open session is shown as open, never as completed or failed |
| Activities done, per activity | `activity_results` completed in the period | counts | fact | days without results listed as missing |
| Completion rate | sessions | completed ÷ ended | derived | none if no ended session |
| Average score | finished, scored results | mean | derived | unscored (story time) excluded |
| Hints per activity; share with a hint | results `hint_count` | mean; share | derived | — |
| Hints asked for vs given automatically; read-aloud presses; pauses (person / screen left); stop requests; rests taken / declined; in-activity adjustments by kind | `activity_events` (deduplicated by event id) | counts | fact | **only for sessions that have a step-by-step record**; coverage is shown ("N of M sessions"); older sessions are "not recorded", never zero |
| Tiredness reports by who | results (person), fatigue observations (phone / dashboard, level) | counts, each report once | fact | — |
| Comparison with the person's usual pattern | results of **activities played in both** windows only | same means and medians, per activity and overall over the comparable set | derived | no comparison if no activity was played in both, or below the minimums |
| Data completeness for the phone | each paired phone's last sync (0014), results' latest time | "may be incomplete" when no phone has synced since the end of the period | derived | stated, never hidden |

## 3. Changes

| # | Change |
|---|---|
| A1 | Like-with-like baseline: comparisons and review prompts use only activities present in both windows; the activities compared are named; per-activity comparison rows |
| A2 | Session summary adds interrupted and still-open counts |
| A3 | `support` summary from activity events with coverage |
| A4 | `sync` completeness: last phone sync and a "may be incomplete" flag with the reason |
| R1 | Review items keep their evidence (the result records considered, missing days, the rules' limitations) and accept caregiver **context notes** (append-only, who and when) without changing the decision; migration 0015 |
| P1 | PDF: period definition in words, support given, like-with-like comparison, sync completeness warning, review evidence and context notes |
| D1 | Dashboard: the same additions with text summaries |

## 4. Status (2026-10-18): implemented and tested

| # | Status | Tests |
|---|---|---|
| A1 like-with-like comparison, compared / not-compared activities named, per-activity rows | ✅ | `test_caregiver_analytics.py` "a different mix of games is not a change", "no shared activity…" |
| A2 interrupted and still-open sessions counted separately; open sessions not counted as ended | ✅ | "sessions are counted by how they ended" |
| A3 support summary from events, deduplicated, with coverage; unknown stays unknown | ✅ | "support comes from events counted once…", "no step record is unknown, not zero"; dashboard `alignment.test.tsx` |
| A4 sync completeness (no phone / period not ended / phone not synced since the end) | ✅ | "report says it may be incomplete until the phone has synced"; dashboard warning test |
| R1 review evidence and append-only context notes (migration 0015, `POST …/review-items/{id}/context`; caregivers incl. helpers; clinicians 403; outsiders 404) | ✅ | "review items keep the records behind them", "context is added without changing the decision"; dashboard context flow |
| P1 PDF additions | ✅ | full and sparse report tests (text checked in uncompressed PDFs) |
| D1 dashboard | ✅ | 3 new tests in `alignment.test.tsx` |

Period boundaries are inclusive local dates in the person's time zone (tested at 00:00 on the
first day and 23:59 on the last).

## 5. Remaining limits

- "May be incomplete" is based on the last time any paired phone synced. It cannot know
  whether the phone holds unsent records; a phone that synced after the period with nothing
  pending is reported as complete, which is correct, but a phone that was reset loses its
  unsent records silently.
- Support counts exist only for sessions recorded with step-by-step events (from migration
  0009 onward); older sessions are shown as "not recorded".
- Evidence keeps at most 100 result ids per review item; the count of results considered is
  always exact.
- Context notes cannot be edited or deleted (by design, like decisions). They are visible to
  clinicians only on confirmed items, through the PDF.
