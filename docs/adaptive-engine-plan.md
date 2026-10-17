# Adaptive engagement engine: inspection and plan

Date: 2026-10-18. Scope: make the **existing** engine adapt better to each person's observed
interactions. No second engine, no ML model, no clinical prediction.

## 1. What already exists (inspected)

SNEHA has two cooperating, deterministic layers, both offline-capable on the phone:

| Layer | Where | Decides | When |
|---|---|---|---|
| Between activities ("engine") | `services/api/app/personalization/engine.py` (source of truth) and the line-by-line Dart port `apps/patient_app/lib/personalization/engine.dart`, held together by 34 generated parity scenarios and a config-parity test | stop, break, which activity, difficulty, hints on/off, which approved memories | before each activity (server when online, phone otherwise) |
| Inside an activity ("in-session policy") | `apps/patient_app/lib/adaptation/session_policy.dart` | hint, shorten, offer a rest, end | after each wrong answer, after each round, on reports |

Signals the engine already uses: stop request; the person's "I'm tired"; caregiver fatigue
with level; sessions ended for tiredness; score; hint count (≤ 1 for a "comfortable success");
interruption; "did you enjoy it?"; caregiver interests and dislikes; repetition; what the phone
can play; approved memory content; language. Response time is used **only to withhold a step
up** (answers much slower than the person's own median); it never lowers the level or causes
any other action.

Decisions that were already explainable and tested: stop first; fatigue → rest or easiest
low-effort activity; difficulty up only after 3 comfortable successes, down after 2 struggles,
never within 3 results of the last change; missing scores neutral; cold start default order;
enjoyed activities favoured; "not enjoyed"/interruptions switch away; no immediate repeats.

## 2. Gaps found

| # | Gap | Effect today |
|---|---|---|
| G1 | **Hint-heavy runs are invisible.** A run finished only with many hints is "neutral" (not success, not struggle), so the next run gets no extra support | The person who needs hints has to struggle again before hints are offered |
| G2 | **No way out at the easiest level.** At an activity's minimum difficulty, repeated struggles cannot step down further, and nothing steers to a different, gentler activity | The same too-hard activity keeps being suggested |
| G3 | **"Read it again" is not recorded.** The Read-aloud button is the patient's "repeat the instruction" request, but presses are not counted or used | Instruction support never adapts |
| G4 | **On-phone decisions leave no trace.** Server recommendations are stored with reasons; on-device ones are not recorded anywhere | No record of why an offline activity was chosen |
| G5 | Reason codes reach the dashboard but some lacked plain-language labels; the patient card had no wording for new supports | — |

Not gaps (kept): "offer fewer choices" already happens through lower difficulty levels
(`config/activities.toml` level parameters) and through in-activity hints that remove options;
"different suitable activity after success" already happens through the repetition penalty.

## 3. Changes (engine ALGORITHM_VERSION 1.2.0, config 2026.10.3)

All rules live in both engines and are parity-tested; thresholds are in
`config/personalization.toml [support]`.

| Rule | Signal | Threshold (default, why) | Effect | Reason code |
|---|---|---|---|---|
| S1 Hint support | hint count per result of **this** activity | ≥ 2 of its last 3 results used ≥ 2 hints (two runs, not one, so one hard day is not a pattern) | hints on and the in-activity policy gives the first hint after 1 wrong answer; difficulty unchanged | `HINT_SUPPORT_AFTER_HINT_USE` |
| S2 Easier alternative | classified outcomes of a candidate at its **easiest** level | its last 2 results were struggles (same as the step-down rule) | score penalty (50) so another suitable activity is preferred; still offered (with hints) if it is the only one | `EASIER_ALTERNATIVE_AFTER_STRUGGLE` |
| S3 Read the question aloud first | `instructions_repeated` metric on recent results (any activity) | ≥ 3 presses over the last 3 results | the runner reads each question aloud when it appears (only if read-aloud is switched on and a voice exists) | `INSTRUCTIONS_READ_ALOUD_FIRST` |
| S4 Decision trace | engine output on the phone | — | `activity_started` records the engine's reason codes and whether the phone or server decided | — |

Recording changes (minimal, additive): event type `instructions_repeated` (migration 0013
widens the CHECK constraint), result metric `instructions_repeated`, event fields
`engine_reason_codes` and `decided_on`, response field `read_aloud_first`.

## 4. Priorities (unchanged, now documented once)

1. Stop request → `stop` (engine) / `end_session` (in-activity). Nothing can override it.
2. "Very tired" (person or caregiver) → rest.
3. "A little tired" / recent tiredness → easiest low-effort activity, hints on, shorter run.
4. Everything else (support, difficulty, preference, variety).

## 5. Flow (traced end to end)

Patient starts an activity → runner records events (answers, hints, read-aloud presses) →
result + events stored on the phone and synced → engine (phone or server) reads the results
for the next suggestion → suggestion carries difficulty, hints, read-aloud-first and reasons →
launcher passes them to the runner (difficulty sets the level parameters, hints lower the
auto-hint threshold, read-aloud-first speaks each question) → `activity_started` records the
reasons → next suggestion uses the new history.

## 6. Status (2026-10-18): implemented and tested

| Step | Status | Evidence |
|---|---|---|
| S1–S3 rules in Python and Dart, thresholds in `[support]` | ✅ | `tests/test_adaptive_engine.py` (13), parity fixture 41 scenarios incl. 7 new, config parity |
| Read-aloud presses recorded (event + metric), questions read first | ✅ | `test/adaptation/adaptive_engine_test.dart` |
| Engine reasons and `decided_on` recorded on `activity_started` | ✅ | phone and API tests |
| Plain wording: patient card and dashboard (and a test that every code has a label) | ✅ | `apps/web_dashboard/tests/reasonLabels.test.ts` |

## 7. Signals that influence decisions (complete list)

| Signal | Recorded where | Used for |
|---|---|---|
| Stop request | request flag / runner Stop | stop, always first |
| "I'm tired" (person), caregiver tiredness with level | result flag, session end, fatigue observation | rest, easiest low-effort activity, shorter run, hints |
| Score of finished runs | result | difficulty steps (with hysteresis), "struggle at easiest" |
| Hints used | result `hint_count` | comfortable success needs ≤ 1 hint; **hint support (S1)** |
| Interrupted runs (not tiredness) | result `abandoned` | switch away after a pattern |
| "Did you enjoy it?" | result `engagement` | favour enjoyed, avoid not enjoyed |
| Read-aloud presses | event + result metric `instructions_repeated` | **read questions first (S3)** |
| Recent activities | results | variety (no immediate repeat) |
| Caregiver interests / dislikes | preferences | interest match, exclusion |
| Approved memories on the phone | memories cache | memory activities only when content exists |
| Answer time vs the person's own median | result metric | only withholds a step up; never lowers or flags |
| Wrong answers, struggled rounds (in a run) | runner | in-activity hint, shorten, rest |

Not used: anything about emotion, confusion or clinical state; other patients' data.

## 8. Reason codes

Between activities (engine): `STOP_REQUESTED`, `FATIGUE_REPORTED_BREAK`,
`CAREGIVER_REPORTED_SEVERE_FATIGUE`, `RECENT_FATIGUE_FEEDBACK`, `RECENT_FATIGUE_OBSERVATION`,
`LOW_EFFORT_FOR_FATIGUE`, `DIFFICULTY_INCREASED_AFTER_COMFORTABLE_SUCCESS`,
`DIFFICULTY_DECREASED_AFTER_REPEATED_ERRORS`, `DIFFICULTY_HELD_TO_AVOID_OSCILLATION`,
`DIFFICULTY_UNCHANGED`, `DIFFICULTY_STARTING_LEVEL`, `HINTS_OFFERED_AFTER_ERRORS`,
**`HINT_SUPPORT_AFTER_HINT_USE`**, **`EASIER_ALTERNATIVE_AFTER_STRUGGLE`**,
**`INSTRUCTIONS_READ_ALOUD_FIRST`**, `INTEREST_MATCH`, `ENJOYED_BEFORE`, `FAMILIAR_ACTIVITY`,
`LOW_ENGAGEMENT_SWITCH`, `AVOID_REPETITION`, `COLD_START_DEFAULT`,
`MISSING_DATA_NOT_COUNTED_AS_ERROR`, and content/availability codes. Full meanings:
[personalization-rules.md](../packages/shared_docs/personalization-rules.md).

Mapping to the brief's examples: REPEATED_DIFFICULTY → `DIFFICULTY_DECREASED_AFTER_REPEATED_ERRORS`,
`EASIER_ALTERNATIVE_AFTER_STRUGGLE`; HINT_SUPPORT_NEEDED → `HINTS_OFFERED_AFTER_ERRORS`,
`HINT_SUPPORT_AFTER_HINT_USE`; SUCCESSFUL_COMPLETION → `DIFFICULTY_INCREASED_AFTER_COMFORTABLE_SUCCESS`
(only after 3) and `AVOID_REPETITION`; PREFERENCE_MATCH → `INTEREST_MATCH`, `ENJOYED_BEFORE`;
CAREGIVER_REPORTED_FATIGUE → `RECENT_FATIGUE_OBSERVATION`, `CAREGIVER_REPORTED_SEVERE_FATIGUE`;
PATIENT_REQUESTED_BREAK → `FATIGUE_REPORTED_BREAK`; PATIENT_REQUESTED_STOP → `STOP_REQUESTED`;
INSUFFICIENT_OBSERVATIONS → `COLD_START_DEFAULT`, `DIFFICULTY_STARTING_LEVEL`,
`MISSING_DATA_NOT_COUNTED_AS_ERROR`. In-activity codes are listed in the same rules document.
The patient never sees codes; the home card and dashboard show sentences.

## 9. Limitations

- Thresholds are design defaults, not tuned on real use; no study with older adults.
- "Read questions first" depends on read-aloud being switched on and the phone having a voice
  for the language; otherwise nothing changes (the reason stays recorded).
- Read-aloud presses are only recorded from this version on; older results count as unknown.
- The engine has no explicit "simplified instructions" text: activities have one instruction
  set, so support comes from earlier hints, fewer options (lower levels) and reading aloud.
- A suggestion reaches the phone at the next suggestion request; the in-activity policy acts
  immediately within a run.
