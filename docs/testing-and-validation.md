# Testing and validation

Date: 2026-10-18. All data in tests and in the demonstration is **synthetic** (labelled
"Synthetic …", `example.org` emails, a generated tone instead of a voice). Nothing here is
a clinical validation or a study with older users.

## How to run

```bash
./scripts/test_all.sh            # every suite and linter
./scripts/demo_alignment.sh      # the repeatable demonstration (API story + phone tests)
cd services/api && uv run python scripts/demo_alignment.py   # API demonstration only
SNEHA_TEST_POSTGRES_URL=postgresql://… uv run pytest          # API suite on PostgreSQL
```

`scripts/demo_alignment.py` runs the real API in-process against a fresh throwaway SQLite
database and prints PASS or FAIL with evidence for each criterion. It is also a test
(`tests/test_demo_alignment.py`), so it cannot silently stop working.

## Results (this machine, 2026-10-18)

| Suite | Before alignment (`b2bbe03`) | After |
|---|---|---|
| API, SQLite | 325 passed, 3 skipped | **345 passed**, 3 skipped (PostgreSQL-only and live-Gemini) |
| API, PostgreSQL 16 (pgserver) | not re-run | **347 passed**, 1 skipped (live Gemini) |
| API lint, format, OpenAPI contract | pass | pass |
| Patient app (`flutter analyze`, `flutter test`) | 172 passed | **200 passed**, no analyzer issues |
| Dashboard (`vitest`, `tsc -b`, `oxlint`) | 56 passed, 2 skipped | **62 passed**, 2 skipped (live API test) |
| Demonstration | — | **12 of 12** API checks pass |

Not re-run in this pass: `npm ci`/`npm run build` (the disk was nearly full, so
dependencies were not reinstalled; `tsc -b` and lint ran), the live dashboard-to-API test,
and anything on the physical phone.

## Acceptance criteria

| Criterion | Status | Evidence |
|---|---|---|
| An approved memory influences a relevant activity | **Pass** | Demo: photo recall chosen with the approved "tea" memory first (`APPROVED_MEMORIES_USED`); pending proposal absent. Phone: `fatigue_sync_and_memory_test.dart` "photo recall asks about the engine's memories first" |
| Session events are persisted, not only in frontend state | **Pass** | Phone: events written to SQLite and the outbox as they happen (`runner_adaptation_test.dart`, "events recorded offline survive…"). Server: `test_activity_events.py`; demo stores 8 events for a session |
| Different interactions lead to different justified decisions | **Pass** | In-activity: `session_policy_test.dart`; runner test "struggling rounds shorten the activity, calm ones do not". Between activities: demo (level down with hints vs level up, with reason codes) |
| Caregiver fatigue input immediately lowers demand or stops the session as configured | **Pass** | Runner tests for "a little tired" (1 round left, earlier hints) and "very tired" (session ends `fatigue_detected`); config `caregiver_severe_action` tested both ways; dashboard report → engine `break` (`test_caregiver_fatigue.py`, demo) |
| A stop request cannot be overridden by an AI response | **Pass** | `test_model_cannot_hide_stop_or_fatigue`; demo with a fake model returning `stop_requested=false`; policy test "stop beats everything" |
| Dashboard trends come from stored session records | **Pass** | Demo: 7 synced results on 7 of 9 days, missing days listed; `test_analytics.py` known-number tests |
| A report uses the requested range and handles missing data transparently | **Pass** | Demo (period matches, a 3-day request is refused); `test_reports.py` three-part, no-data and tiredness tests |
| A possible concern requires human review and is not a diagnosis | **Pass** | `test_review_items.py`; dashboard review tests; demo (clinician sees nothing until a managing caregiver confirms with a reason) |
| Core offline functionality works without a network | **Pass (in tests)** | `test/offline/offline_guarantee_test.dart`; caregiver report and severe-fatigue rest suggestion with the server offline (`caregiver_home_test.dart`, `fatigue_sync_and_memory_test.dart`). **Not re-checked on the real phone in this pass** |
| Synchronisation does not silently duplicate or lose events | **Pass** | Server dedupes events and fatigue reports by record ID even under new mutation IDs (tests and demo); unknown session → `rejected`, kept for attention; phone pushes once after an offline failure |
| Unauthorised users cannot access another patient's data | **Pass** | `test_authorization.py` now also sweeps the events, review-items, scan and decision routes; demo 404s |
| AI and speech failures produce safe, understandable fallbacks | **Pass** | Demo: malformed model output → deterministic reply; speech → `consent_required`, `model_missing`, `language_unsupported`; existing speech and Flutter tests |

## Unverified or unimplemented

- Usability and accessibility with older adults in the North Eastern Region; any clinical
  validity of the review rules.
- On-device testing of the new runner behaviour, caregiver screen and sync on the Samsung
  test phone.
- Live Gemini or local LLM; server TTS with real weights; ASR for any Indic language;
  phone TTS voice availability for Assamese.
- Native-speaker review of the new English-only strings (draft languages fall back to
  English for them).
- Concurrency and load testing.
