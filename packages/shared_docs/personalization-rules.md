# Personalization rules: specification (ALGORITHM_VERSION 1.2.0)

**Implemented.** Source of truth: `services/api/app/personalization/engine.py`, with
thresholds in `services/api/config/personalization.toml` (`config_version` is stored on
every recommendation). The patient app runs a line-by-line Dart port
(`apps/patient_app/lib/personalization/`) for offline use. Parity is enforced by
`engine_parity_test.dart` (32 scenarios generated from the Python engine) and
`config_parity_test.dart` (every TOML key and value).

These are **engagement rules** for choosing a comfortable, enjoyable activity. They are not
clinical thresholds and say nothing about any medical condition. No LLM takes part in
selection.

## Inputs (all stored facts)

Active catalog · approved interests and disliked activities (managing caregivers only) ·
language · the patient's results (score, hints, interruption, response time, engagement
answer, tiredness flag) · caregiver observations (category and time only, never note
text) · sessions ended for tiredness · approved memory and routine content per activity ·
the device's available activities · the request's stop/fatigue flags · conversation
context tags (transient).

## Order of decisions

1. **Stop request → `stop`.** Always first, before anything else.
2. **Candidate filters**, each explained by a reason code:
   - activities the device can run (`available_slugs`)
   - disliked activities removed (unless nothing would remain)
   - Memory Bank activities only with enough approved content (photo recall ≥ 3 photos,
     familiar faces ≥ 2 people with photos, story time ≥ 1)
   - language content, relaxed with an explicit fallback if nothing matches
   - nothing left → `none`
3. **Fatigue.**
   - Explicit (this request, or the latest result says "I'm tired", within 3 h) →
     `break` (10 min) plus an easy alternative.
   - Recent (result feedback or a session ended for tiredness within 3 h, or a caregiver
     `fatigue` observation within 8 h) → low-effort activities only (`story-time`,
     `picture-pairs`, `name-the-object`) at their easiest level.
   - A caregiver fatigue observation with level **`severe`** ("very tired") within 8 h is
     treated as explicit: `break` (`CAREGIVER_REPORTED_SEVERE_FATIGUE`). `mild` or no level
     → low-effort as above. These reports reach the phone through sync (level and time
     only), so the on-phone engine applies them offline (added in 1.1.0).
4. **Low engagement.** If 2 of the last 3 results were interruptions (not tiredness) or
   "not enjoyed", switch away from those activities if an alternative exists.
5. **Scoring** (integer, deterministic):
   - approved interest matches: +20 each, capped at 40
   - conversation context matches: +10 each
   - enjoyed: +15 each; not enjoyed: −25 each; interruptions: −10 each (all over the
     activity's last 5 results)
   - completed before: +10
   - same as the last activity: −60; each appearance in the last 5 results: −15
   - cold start: the configured default order
   - ties: never played → least recently played → default order → slug
6. **Difficulty**: replay this activity's results (latest 40):
   - *comfortable success* = score ≥ 0.8, hints ≤ 1, and mean response ≤ 1.5 × the
     patient's own median (if known)
   - *struggle* = score < 0.5
   - missing score, interruptions and tiredness-related stops are **neutral**: they
     neither count as failure nor break a streak
   - +1 level after 3 consecutive successes; −1 after 2 consecutive struggles; never
     within 3 results of the last change (anti-oscillation); always within the activity's
     min/max
   - hints offered after ≥ 1 trailing struggle, and always when tired
7. **Output**: action, activity, difficulty, level parameters (from
   `config/activities.toml`), reason codes, supporting records (IDs plus short non-free-text
   details), content refs (approved memory and routine IDs), algorithm and config
   versions, fallback status (`no_history`, `language_content_unavailable`,
   `no_available_activity`).

## Reason codes

`STOP_REQUESTED`, `FATIGUE_REPORTED_BREAK`, `RECENT_FATIGUE_FEEDBACK`,
`RECENT_FATIGUE_OBSERVATION`, `CAREGIVER_REPORTED_SEVERE_FATIGUE`, `LOW_EFFORT_FOR_FATIGUE`, `COLD_START_DEFAULT`,
`INTEREST_MATCH`, `CONVERSATION_CONTEXT_MATCH`, `ENJOYED_BEFORE`, `FAMILIAR_ACTIVITY`,
`LOW_ENGAGEMENT_SWITCH`, `AVOID_REPETITION`, `ONLY_AVAILABLE_ACTIVITY`,
`DIFFICULTY_INCREASED_AFTER_COMFORTABLE_SUCCESS`, `DIFFICULTY_DECREASED_AFTER_REPEATED_ERRORS`,
`DIFFICULTY_HELD_TO_AVOID_OSCILLATION`, `DIFFICULTY_UNCHANGED`, `DIFFICULTY_STARTING_LEVEL`,
`HINTS_OFFERED_AFTER_ERRORS`, `MISSING_DATA_NOT_COUNTED_AS_ERROR`, `APPROVED_MEMORIES_USED`,
`PERSONAL_ROUTINES_USED`, `DISLIKED_ACTIVITY_EXCLUDED`, `LIMITED_TO_AVAILABLE_OFFLINE_CONTENT`,
`LANGUAGE_CONTENT_FALLBACK`, `NO_AVAILABLE_ACTIVITY`.

## Support that follows what the person needed (1.2.0, `[support]`)

| Rule | When | Effect | Code |
|---|---|---|---|
| Hint support | ≥ 2 of this activity's last 3 finished results used ≥ 2 hints | hints on (first in-activity hint after 1 wrong answer); level unchanged | `HINT_SUPPORT_AFTER_HINT_USE` |
| Easier alternative | an activity is at its easiest level and its last 2 results were struggles | −50 to its score so another suitable activity is preferred; offered with hints if it is the only one | `EASIER_ALTERNATIVE_AFTER_STRUGGLE` |
| Read questions first | ≥ 3 "Read aloud" presses over the last 3 results (`instructions_repeated` metric) | `read_aloud_first`: the runner reads each question aloud when it appears (if read-aloud is on and a voice exists) | `INSTRUCTIONS_READ_ALOUD_FIRST` |

Missing metrics (older results) count as unknown, never as a need for support. Stop and
tiredness rules run first and are unaffected.

## Inside an activity: the comfort policy (phone)

`apps/patient_app/lib/adaptation/session_policy.dart`, thresholds in `[in_session]` and
`fatigue.caregiver_severe_action` of `personalization.toml` (config-parity tested; the
Python config validates them). Checked after every wrong answer, after every round and
whenever tiredness or a stop is reported. First match wins:

| # | Condition | Action | Reason codes |
|---|---|---|---|
| 1 | Stop requested | `end_session` | `STOP_REQUESTED` |
| 2 | "Very tired" | `end_session` (or `offer_break` if configured; a declined rest then ends) | `SEVERE_FATIGUE_END_SESSION` / `SEVERE_FATIGUE_OFFER_BREAK`, `CAREGIVER_REPORT` / `PATIENT_REPORT` |
| 3 | "A little tired" and more than `mild_fatigue_max_remaining_rounds` (1) left | `shorten` | `MILD_FATIGUE_SHORTEN` |
| 4 | After a round: ≥ `break_after_struggled_rounds` (3) struggled rounds, rest not yet offered | `offer_break` | `REPEATED_STRUGGLE_OFFER_BREAK` |
| 5 | After a round: ≥ `shorten_after_struggled_rounds` (2) in a row and > 1 round left | `shorten` to 1 | `REPEATED_STRUGGLE_SHORTEN` |
| 6 | After a wrong answer: errors in the round ≥ threshold × (hints shown + 1); threshold `auto_hint_after_errors` (2), or `…_assisted` (1) when the engine advised hints or the person is a little tired | `show_hint` | `REPEATED_ERRORS_IN_ROUND` (+ `HINTS_ADVISED_BY_ENGINE`, `MILD_FATIGUE_MORE_HINTS`) |
| 7 | Otherwise | `continue` | — |

A *struggled* round has ≥ `struggled_round_errors` (2) wrong answers or was skipped.
Response time is recorded per answer but not used. Accepting a rest after struggling keeps
the result scored (not abandoned), so the next suggestion can be easier. Every decision is
stored as an `adaptation` event.

## Changing the rules

Edit the TOML (bump `config_version`) or the engine (bump `ALGORITHM_VERSION`), port the
change to Dart, then regenerate the parity fixture:
`cd services/api && .venv/bin/python ../../apps/patient_app/tool/engine_parity/generate.py`.
