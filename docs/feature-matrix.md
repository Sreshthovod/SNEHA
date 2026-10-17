# Feature matrix

Status as of 2026-10-18 (alignment work: rows marked **new** or **changed**).

- **Screens:** Flutter paths are under `apps/patient_app/lib/features/`; dashboard paths
  are under `apps/web_dashboard/src/pages/`.
- **Endpoints:** paths under `/api/v1`.
- **Offline:** whether the patient app can do this without a connection.
- **Tests:** API tests are in `services/api/tests/`; `FL` = Flutter tests, `WD` =
  dashboard tests.

| Feature | Screen | Endpoint(s) | Storage | AI / provider | Offline | Tests |
|---|---|---|---|---|---|---|
| Caregiver/clinician sign-in, roles | WD `LoginPage`, `RegisterPage`, role-aware `AppShell` | `/auth/register`, `/auth/login`, `/auth/logout`, `/auth/me` | `users`, `auth_sessions` (token hash) | — | n/a (dashboard) | `test_auth.py`; WD auth/role tests |
| Patient phone pairing, multiple profiles | FL `onboarding/*`, `profiles/pair_screen`, `profile_select_screen` | `/patients/{id}/pairing-codes`, `/auth/device/pair` | `device_pairing_codes`; phone: profiles + secure token | — | ❌ (pairing needs a connection) | `test_auth.py`; FL onboarding/pairing tests |
| Authorization (patient, caregiver, manager, clinician, admin) | all | every patient-scoped route | `caregiver_relationships`, `clinician_access_grants`, `consent_records` | — | n/a | `test_authorization.py` (all patient routes × 4 outsiders + positive control) |
| Patient profile and data management | WD `patient/ProfileSection`, `PeopleSection`, `ConsentSection` | `/patients`, `/patients/{id}`, `/caregivers`, `/clinician-grants`, `/consents`, `/devices/revoke`, `/erase` | `patient_profiles` + cascades | — | consent view cached on phone | `test_auth.py`, `test_security.py`, `test_erasure.py`; WD consent tests |
| Memory Bank (create, approve, correct, delete, photos) | WD `patient/MemoriesSection`; FL memory games, story time | `/patients/{id}/memories[/…]`, `/memory-relationships`, `/media`, `/files/{id}/content` | `memory_items`, `memory_relationships`, `stored_files` + disk | — | ✅ approved memories and cached photos | `test_memories.py`, `test_files.py`, `test_e2e_workflows.py::…memory_approval…`; WD memory tests |
| Memory retrieval | used by suggestions and conversation | `/patients/{id}/memories-retrieve` | approved memories, tags, relationships | Tag/entity/relationship rules (no LLM) | phone uses its approved cache | `test_personalization_api.py::test_memory_retrieval_endpoint` |
| Six games + story time on one activity runner | FL `activities/*`, `memories/story_time_screen` | `/activities/catalog` (specs) | `activity_definitions` + `config/activities.toml`; phone catalog cache | — | ✅ | FL game/runner/spec tests; `test_personalization_api.py::test_catalog…` |
| Results and sessions | FL runner, result screen | `/patients/{id}/sessions…`, `/activities/result`, `/sync/push` | `activity_sessions`, `activity_results`; phone outbox | — | ✅ (outbox) | `test_activities.py`, `test_sync.py`; FL recorder/sync tests |
| Personalization and adaptive difficulty | FL "Suggested for you"; WD `ProgressSection`, `PreferencesSection` | `/activities/next`, `/activities/result`, `/patients/{id}/preferences`, `/progress`, `/recommendations` | `activity_recommendations`, `personalization_states`, `patient_preferences` | Deterministic engine 1.0.0 (Python + parity-tested Dart port) | ✅ (on-phone engine) | `test_personalization_engine.py` (26), `test_personalization_api.py`; FL parity (32 scenarios) + config parity; WD personalization tests |
| Fatigue-driven adaptation (**changed**) | FL "I'm tired", caregiver button in the runner and "For caregivers" screen; WD observation with level | `/activities/next`, `/observations` (`fatigue_level`), `/sync/push` + `/sync/pull` `fatigue_report` | results `fatigue_reported`, `caregiver_observations.fatigue_level`; phone `fatigue_reports` | Engine 1.1.0 + in-activity policy | ✅ caregiver reports act at once on the phone; dashboard notes after sync | `test_caregiver_fatigue.py`, `runner_adaptation_test.dart`, `fatigue_sync_and_memory_test.dart` |
| Conversation and suggestion | FL `conversation/conversation_screen` | `/conversation/analyze` | `conversation_records` (metadata only) | Gemini (consent) → local LLM → deterministic; guards | ✅ offline helper on phone | `test_conversation.py` (41), `test_e2e_workflows.py::test_conversation_based…`; FL conversation tests |
| Speech recognition | FL conversation mic | `/speech/status`, `/speech/transcribe` | none (audio and transcript not stored) | faster-whisper (verified with the tiny model) | ❌ | `test_speech.py` (incl. real model); FL speech tests |
| Read aloud | FL runner, instructions | (`/speech/synthesize` optional) | none | Android system TTS; Indic Parler-TTS (server, optional, not run here) | ✅ if the phone has the voice | FL speech tests; `test_speech.py` (TTS errors) |
| In-activity adaptation (**new**) | FL runner | — (phone only) | phone `activity_events`, outbox | Rules: `session_policy.dart` | ✅ | `session_policy_test.dart`, `runner_adaptation_test.dart` |
| Session event log (**new**) | FL runner; WD `HistorySection` "What happened" | `/sync/push` `activity_event`, `/patients/{id}/sessions/{sid}/events` | `activity_events` (both sides) | — | ✅ (queued) | `test_activity_events.py`, runner tests, WD `alignment.test.tsx` |
| Review items with caregiver confirmation (**new**) | WD `AnalyticsSection` "Your review", clinician dashboard | `/patients/{id}/review-items`, `/scan`, `/{id}/decision` | `review_items` | Rules (analytics) | n/a | `test_review_items.py`, WD `analytics.test.tsx` |
| Caregiver observations workflow | WD `patient/ObservationsSection`, caregiver dashboard | `/patients/{id}/observations[/…/review,/resolve,/revisions]` | `caregiver_observations`, `observation_revisions` | — | n/a | `test_observation_workflow.py`, `test_care.py`; WD observation tests |
| Analytics and review prompts | WD `patient/AnalyticsSection`, clinician dashboard | `/patients/{id}/analytics`, `/analytics/review-flags` | computed from results/sessions/observations | pandas/NumPy, `config/analytics.toml` rules (no LLM) | local descriptive progress only | `test_analytics.py`; WD analytics tests |
| 8–9 day PDF reports (**changed**: three parts, tiredness by source) | WD `patient/ReportsSection`, `ReportViewer`, clinician dashboard | `/patients/{id}/reports[/…/generate]`, `/files/{id}/content` | `reports`, `stored_files` (PDF) | ReportLab (no LLM); `scripts/generate_due_reports.py` | n/a | `test_reports.py`, `test_e2e_workflows.py::test_clinician_report_download`; WD report tests; live smoke |
| Offline status and sync | FL `sync/sync_status_screen`, home connection card | `/sync/push`, `/sync/pull` | `sync_changes`, `sync_mutations`; phone outbox with backoff | — | ✅ queue, retry, needs-attention | `test_sync.py`, `test_e2e_workflows.py::test_offline_recording…`; FL sync tests |
| Accessibility and language settings | FL `settings/settings_screen`; WD `SettingsPage` | — | phone settings table; browser localStorage | — | ✅ | FL a11y guideline tests; WD settings tests |
| Privacy and consent | FL `privacy/privacy_screen`; WD `ConsentSection` | `/patients/{id}/consents` | `consent_records` (append-only) | — | read-only cache on phone | `test_erasure.py`, `test_authorization.py`; FL privacy tests |
| Audit | — | all writes and denials | `audit_events` (allow-listed details) | — | n/a | `test_security.py`, `test_authorization.py` |

**Demo fixtures.** Normal app mode has no fake success responses. All test data is
labelled synthetic ("Synthetic …" names, `example.org` emails, `is_synthetic` profiles, a
macOS-`say` voice clip). No separate demo mode exists yet.
