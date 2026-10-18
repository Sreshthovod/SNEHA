# Safety and privacy

Date: 2026-10-18. This page covers the wellbeing and human-oversight rules the original
problem requires, and what changed in the alignment work. Authentication, consent ledger,
files, audit and data-minimisation details are in
[privacy-and-safety.md](privacy-and-safety.md). The security audit results are in
[stage8-validation-report.md](stage8-validation-report.md).

**SNEHA is not a medical device.** It does not diagnose, screen, stage or predict any
condition, and it never says that a person's cognition is declining.

## Wellbeing rules (enforced in code and tests)

| Rule | Where | Test |
|---|---|---|
| A stop request ends the activity; nothing (policy, engine, AI model) can override it | `session_policy.dart` priority 1; `engine.py` step 1; conversation guard ORs stop flags | `session_policy_test.dart` "stop beats everything"; `runner_adaptation_test.dart` "stop is final"; `test_model_cannot_hide_stop_or_fatigue`; demo |
| Tiredness lowers demand at once: "a little tired" shortens the run to at most 1 more round with earlier hints; "very tired" ends the session (or offers a rest, per config) | `session_policy.dart`, runner `_onFatigue` | `runner_adaptation_test.dart` caregiver mild and severe tests |
| Tiredness carries over: the next suggestion is the easiest low-effort activity (mild) or a rest (very tired), on the phone even offline | `engine.py` / `engine.dart` 1.1.0 | `test_caregiver_fatigue.py`, `fatigue_sync_and_memory_test.dart` |
| The app never lengthens an activity to keep someone playing; there is no engagement target, streak or time-on-app goal | policy has no "extend" action; engine scoring rewards enjoyment, not duration | "the policy never lengthens an activity" |
| A rest is offered at most once per activity; "keep going" is respected | runner `_breakOffered` | "a rest is offered once…" |
| No time pressure: there are no countdowns. Latency is recorded only as information | runner, games | — |
| Tiredness is never counted as a mistake, and one report is counted once | engine (neutral outcome); analytics dedup of a phone report plus the session it ended | `test_one_tired_press_counts_once`, `test_caregiver_very_tired_on_the_phone_counts_once_in_analytics` |
| One wrong answer or one unusual session never raises a concern | analytics thresholds (≥ 66 % of days, minimum data) | `test_one_bad_session_never_raises_a_flag` |
| Distress words get a "call a family member / 112" reply, never hidden by a model | conversation guard; offline helper | conversation safety tests |

## Human oversight of possible concerns

1. Fixed rules compute **review prompts** from stored data (an interpretation).
2. A scan stores each prompt as a **review item** with a snapshot of its evidence
   (rule, numbers, explanation, period, method and settings versions, related notes).
3. Any caregiver can add **context notes** (append-only, who and when) without deciding;
   each item also keeps the records it was based on and the rules' limitations.
4. A **managing caregiver** confirms ("worth discussing with a clinician") or dismisses it,
   always with a written reason. The decision is final and audited (who, when). Helpers can
   see items but cannot decide.
5. **Clinicians see only confirmed items.** Their analytics response has
   `review_flags: []` and `review_flags_withheld: true`.
6. The PDF separates **Part 1** (what was recorded), **Part 2** (automatic prompts, each
   with its review status) and **Part 3** (caregiver-confirmed concerns and dismissals,
   with reasons).

Tests: `test_review_items.py`, `test_reports.py` (three parts), dashboard
`analytics.test.tsx` (reason required, helper cannot decide, clinician view).

## Privacy of the new data

| Data | What is kept | What is not |
|---|---|---|
| Activity events | Event type, order, round, time and typed values (`correct`, `latency_ms`, `action`, reason codes, level) | **No free text**: the schema forbids extra fields (422) |
| Caregiver tiredness report from the phone | Level, time; stored as a fatigue observation with a fixed note | Who held the phone (only "a caregiver on the person's phone") |
| Fatigue observations sent to the phone | ID, level, time, source | **The caregiver's note text never leaves the server** |
| Review items | Rule outputs (numbers, explanation), evidence (result ids, missing days, limitations), context notes, decision, reason, decider | The reason and context notes are visible to clinicians once confirmed; write them with that in mind |

All new tables cascade on patient erasure. Every new patient route is in the outsider sweep
in `tests/test_authorization.py` (404, no change).

## Known limits

- A caregiver's report on the phone cannot say *which* caregiver made it (the phone has one
  patient account).
- A dashboard "very tired" note reaches a running activity only after the phone syncs. During
  an activity the phone syncs in the background at most once a minute while online; there is
  no push channel. The dashboard shows whether each note has reached the phone. The on-phone
  caregiver button acts at once.
- Review decisions are final. There is no reopen; a mistaken decision is corrected by a new
  observation, and the next period's scan raises a new item if the pattern continues.
- Open security findings O1–O5 from Stage 8 still apply.
