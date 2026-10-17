# Implementation progress: original-problem alignment

Started 2026-10-18 on branch `stage-8-security-validation` (base `b2bbe03`). Findings F1–F9
are defined in [original-problem-alignment-audit.md](original-problem-alignment-audit.md).
Every increment left all suites green before the next one started.

| # | Increment | Findings | Status | Main files | Tests |
|---|---|---|---|---|---|
| 1 | Session event log: phone SQLite (schema v5) → outbox → `activity_events` (migration 0009) → dashboard timeline | F4 | ✅ Done | `run_tracker.dart`, `activity_recorder.dart`, `local_database.dart`, `models/activities.py`, `schemas/events.py`, `services/sync.py`, `routes/activities.py`, WD `HistorySection.tsx` | `test_activity_events.py`, runner tests, WD `alignment.test.tsx` |
| 2 | In-activity comfort policy and runner integration; engine memory refs and hint advice reach the games | F3, F5 | ✅ Done | `adaptation/session_policy.dart`, `activity_runner_screen.dart`, `[in_session]` in `personalization.toml` and its Python and Dart configs, `activity.dart` `pickPreferred` | `session_policy_test.dart`, `runner_adaptation_test.dart`, config parity |
| 3 | Caregiver fatigue: level on observations (migration 0010), caregiver button in the runner and on the caregiver screen, `fatigue_report` push and pull (level and time only), engine 1.1.0 "very tired → rest" in Python and Dart, analytics counts one report once | F1 | ✅ Done | `caregiver_fatigue_sheet.dart`, `sync_service.dart`, `recommendation_source.dart`, `engine.py`/`.dart`, `routes/care.py`, `services/changes.py`, `compute.py`, WD `ObservationsSection.tsx` | `test_caregiver_fatigue.py`, `fatigue_sync_and_memory_test.dart`, parity (34 scenarios) |
| 4 | Review items with caregiver confirm or dismiss (migration 0011); clinicians see confirmed only; prompts withheld from clinician analytics | F2 | ✅ Done | `review/service.py`, `routes/review.py`, `schemas/review.py`, `access.py`, `routes/analytics.py`, WD `ReviewItemsPanel.tsx`, `ClinicianDashboardPage.tsx` | `test_review_items.py`, WD `analytics.test.tsx` |
| 5 | Report in three parts (recorded, automated, caregiver-confirmed) plus tiredness by source | F9 | ✅ Done | `reports/pdf.py`, `reports/service.py` | `test_reports.py` |
| 6 | Offline and sync tests for the new entities | — | ✅ Done | — | phone sync tests, `test_activity_events.py`, `test_caregiver_fatigue.py` |
| 7 | Voice: honest per-language table and fallbacks | F8 | ✅ Documented, no code change | `ai-and-ml-methods.md` | demo speech check |
| 8a | Patient home: 3 big choices plus "For caregivers" | F7 | ✅ Done | `home_screen.dart`, `caregiver/caregiver_screen.dart` | `caregiver_home_test.dart` |
| 8b | Memory `relationship` field (done, migration 0012) and per-memory AI opt-out (not started) | F6 | ◐ Partly done | see "Memory-based activities" below | `test_memories.py` |
| — | Repeatable demonstration | — | ✅ Done | `scripts/demo_alignment.py`, `scripts/demo_alignment.sh` | `test_demo_alignment.py` |

## Versions bumped

- Personalization `ALGORITHM_VERSION` 1.0.0 → **1.1.0**; `config_version` 2026.10.1 → **2026.10.2**.
- Alembic head **0011**; phone local schema **v5**.
- Analytics method and config are unchanged (`analytics-1.0.0`, `2026.10.1`).

## Next steps (in priority order)

1. Install the build on the test phone and exercise the runner, caregiver screen and sync.
2. F6: per-memory AI opt-out (the relationship field was added with the memory-based activities, below).
3. Translate the new strings (Hindi, Assamese, Bengali drafts) with native speakers.
4. A push or poll channel so a dashboard "very tired" note reaches a running activity
   without waiting for sync.
5. Evaluate an offline ASR (IndicConformer) on device before any regional voice claim.

## UI/UX redesign (2026-10-18)

Both apps were redesigned to a shared design system ([design-system-spec.md](design-system-spec.md)),
driven by the audit in [ui-ux-audit.md](ui-ux-audit.md). Routes, API calls and behaviour are
unchanged. Evidence is in [ui-ux-validation.md](ui-ux-validation.md).

| Area | Done |
|---|---|
| Dashboard | sidebar shell and mobile drawer, grouped patient sections, per-route titles and focus, analytics with progressive disclosure, review prompts grouped by rule, green token palette, dark and high-contrast fixes, confirmation before deleting a note or removing a caregiver |
| Patient app | explicit font family and colour scheme, calm home with one primary action, two-tier runner controls, scrollable rounds, gentle feedback, result screen and story time navigation, grouped caregiver screen |
| QA tooling | `tools/ui-qa/` (seed + Chrome DevTools screenshots), `apps/patient_app/test/ui_qa/screenshots_test.dart` |

## Memory-based activities (2026-10-18)

Plan and rules: [memory-personalization-plan.md](memory-personalization-plan.md).

| # | Increment | Status |
|---|---|---|
| 1 | Server: `memory_items.relationship` (migration 0012); memory fields on events; foreign memory refs refused | ✅ |
| 2 | Dashboard: relationship field, duplicate-safe create, "How SNEHA uses this", memory links, named memories in the session timeline (titles hidden from clinicians) | ✅ |
| 3 | Phone: schema v6, `memory_content.dart` rules, photo recall / familiar faces / picture pairs / sorting / story time from approved cached memories with generic fallback, memory use recorded on events, defensive refusal of non-approved memories | ✅ |
| 4 | Tests and docs | ✅ API 347, phone 210, dashboard 67 passing |

Versions: Alembic head **0012**, phone local schema **v6**. Engine and analytics unchanged.

## Adaptive engagement engine (2026-10-18)

Plan, signals, reason codes and limits: [adaptive-engine-plan.md](adaptive-engine-plan.md).

| # | Increment | Status |
|---|---|---|
| 1 | Engine 1.2.0 (Python + Dart, parity): hint support, gentler alternative at the easiest level, read questions first; config 2026.10.3 `[support]` | ✅ |
| 2 | Recording: `instructions_repeated` event (migration 0013) and metric; `engine_reason_codes` + `decided_on` on `activity_started`; `read_aloud_first` on recommendations | ✅ |
| 3 | Patient experience: runner reads questions first, counts "Read aloud" presses, hint support lowers the auto-hint threshold; home card explains in plain words | ✅ |
| 4 | Dashboard wording for every reason code (drift test reads the engine) | ✅ |
| 5 | Tests | ✅ API 360, phone 225, dashboard 69 passing |

Versions: Alembic head **0013**, engine **1.2.0**, personalization config **2026.10.3**.
