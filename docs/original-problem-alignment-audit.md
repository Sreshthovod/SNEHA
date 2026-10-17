# Original problem alignment audit

Date: 2026-10-18. Branch: `stage-8-security-validation` at `b2bbe03`.

This audit checks SNEHA against the original problem, not against the stage briefs.
The question for each requirement is whether the real patient and caregiver workflow
works, not whether a screen, table or endpoint exists.

**How the evidence was gathered.** I read the models, migrations, routes, services,
engines, patient-app screens and dashboard pages listed below, and traced each
scenario through the code. I ran the existing suites before changing anything:

| Suite | Result on `b2bbe03` |
|---|---|
| API (`uv run pytest -q`) | 325 passed, 3 skipped |
| Patient app (`flutter test`) | 172 passed |
| Dashboard (`npx vitest run`) | 56 passed, 2 skipped |

All suites pass. That tells us the code does what its tests expect. It does not tell us
whether those tests cover the original requirements, which is what this audit checks.

Status words: **Works** (end to end, with test evidence), **Partial** (some of the
path works), **Simulated** (stands in for the real thing), **Missing**.

---

## 1. Scenario trace

| # | Scenario | Status before this work | Evidence |
|---|---|---|---|
| S1 | Caregiver creates a patient profile | **Works** | `POST /patients` (`api/routes/patients.py`), WD `PatientsPage`; `test_e2e_workflows.py` |
| S2 | Caregiver adds and approves memories and photos | **Works** | `api/routes/memories.py` (create → pending, approve/reject with `expected_version`), `/media` upload; WD `MemoriesSection`; `test_memories.py`, `test_files.py` |
| S3 | Patient starts an activity | **Works** | FL `features/home/suggestion_card.dart` → `features/activities/activity_launcher.dart` → `ActivityRunnerScreen` |
| S4 | The activity uses relevant approved memories | **Partial** | Memory games (`activities/games/memory_games.dart`) use only approved memories (the phone never receives others: `services/sync.py::_payload`). But the recommendation's `content_refs` / `memoryItemIds` (relevant memories picked by `personalization/memory_retrieval.py` or the Dart engine) are **never passed to the runner**. `launchActivity` loads *all* approved memories and the game picks them at random. So relevance ranking is computed, stored and then ignored. |
| S5 | Responses, hints, attempts, timing and completion are recorded | **Partial** | `RunTracker` counts attempts, hints, skips and active time, and `ActivityRecorder.recordResult` persists **one aggregate row per activity** (SQLite + outbox → `activity_results`). No per-attempt or per-round events exist anywhere. "Response latency" is `activeTime / attempts` (`run_tracker.dart`), which includes reading time and pauses between rounds. It is an approximation, not a per-answer latency. Help requests (hint presses) and pauses are counted but not timestamped. |
| S6 | The adaptation engine chooses an appropriate next action | **Works between activities; Missing within an activity** | `personalization/engine.py` and its parity-tested Dart port choose the next activity, difficulty and break with reason codes. **Within a running activity nothing adapts**: round count is fixed when the activity starts, repeated wrong answers do not trigger a hint, shorten the activity or offer a rest, and the engine's `hints_enabled` output is dropped (`ServerRecommendation.hintsEnabled` is parsed but never used). |
| S7 | A caregiver reports fatigue and the active session responds | **Missing** | The only caregiver fatigue input is a dashboard observation (`category=fatigue`). It is **not synced to the phone** (`recommendation_source.dart:227`: "Caregiver observations are not synced to the phone") and the runner never re-checks anything mid-activity. A dashboard fatigue note affects only the *server's* next suggestion (8 h window) and only while the phone is online. The patient's own "I'm tired" button does end the activity, but there is no caregiver control on the phone and no graded response (simplify vs stop). |
| S8 | Session history updates the longitudinal dashboard | **Works** | `analytics/service.py` builds every metric from stored `activity_results`, `activity_sessions` and `caregiver_observations`; WD `AnalyticsSection`; `test_analytics.py`. |
| S9 | 8–9 day report from stored data | **Works, with gaps** | `reports/service.py` + `reports/pdf.py`; `ReportRequest` enforces 8–9 days; missing days are listed, not filled. Gaps: review prompts are printed with no caregiver review status, and the report does not separate observations, automated interpretations and caregiver-confirmed concerns. |
| S10 | A concerning change goes to human review and confirmation | **Missing** | Review flags (`analytics/compute.py::review_flags`) are conservative and explained, but they are **recomputed on every request and never stored**. There is no review item, no confirm or dismiss action and no reason field. The **clinician dashboard shows unconfirmed flags directly** (`ClinicianDashboardPage.tsx:60`), so an automated prompt reaches the clinician without any caregiver confirmation. |
| S11 | Essential features work without internet | **Works** | Activities, approved memories and cached photos, on-phone engine, outbox with retry (`sync_service.dart`), offline conversation helper; Flutter `test/offline/offline_guarantee_test.dart`. Pairing, voice input and dashboard features need a connection (stated in the UI). |

---

## 2. Findings

Each finding lists the requirement, what exists, the evidence, the gap, the impact on users,
a severity, the correction and an acceptance test. They are ordered by severity, then
by the brief's repair order.

### F1. Caregiver fatigue input does not reach the active session (Critical)

- **Requirement:** 3 (fatigue-aware load reduction), 4.D. Caregiver fatigue input must
  be a real control that affects the active session and later sessions.
- **Existing:** dashboard observation with `category=fatigue`
  (`api/routes/care.py`, WD `ObservationsSection.tsx`); server engine rule
  `RECENT_FATIGUE_OBSERVATION` (`personalization/engine.py::_fatigue_signals`); patient
  "I'm tired" button (`activity_runner_screen.dart::_tired`).
- **Evidence:** observations are not a sync entity (`models/enums.py::SyncEntity`); the
  Dart engine receives `observations: const []` from `LocalFacts`
  (`recommendation_source.dart:227`); the runner has no caregiver control and no check
  between rounds.
- **Gap:** a caregiver sitting next to the patient cannot lower the load or stop the
  session from the phone. A fatigue note from the dashboard is ignored offline and never
  affects a running activity. There is no level: "a bit tired" and "exhausted" are
  treated the same.
- **Impact:** the patient keeps getting full-length, full-difficulty rounds after the
  caregiver has seen they are tired. This is the main wellbeing control in the brief.
- **Correction:** add a caregiver fatigue control to the phone, available during an
  activity and from the home screen, with two levels. *Mild* simplifies: rounds shortened,
  hints shown automatically, easiest level next time. *Severe* stops the session and
  offers a rest; this response is configurable. The phone records the report locally,
  applies it right away and syncs it as a fatigue observation with a level. Dashboard
  fatigue observations sync down to the phone (time, level and source only, never the
  note text), so the offline engine and a running activity both respect them.
- **Acceptance:** a widget test shows that a caregiver report of "mild" mid-activity
  reduces the remaining rounds and turns on automatic hints, and "severe" ends the session
  with `end_reason=fatigue_detected`. An engine test shows a pulled caregiver report leads
  to `break` or a low-effort activity offline. An API test shows the synced report is stored
  as a fatigue observation with its level.

### F2. Review prompts are not stored, not confirmable, and reach clinicians unconfirmed (Critical)

- **Requirement:** 8 (caregiver confirmation before escalating), 4.E, 9 (human oversight).
- **Existing:** `analytics/compute.py::review_flags` (conservative, explained,
  "not evaluated" list); `ReviewFlagsPanel.tsx` shows them read-only; clinician
  dashboard lists flag titles; the PDF prints them.
- **Evidence:** no table for review items in `models/`; `GET /analytics/review-flags`
  recomputes them; `ClinicianDashboardPage.tsx` shows `a.review_flags` to clinicians.
- **Gap:** no human-in-the-loop step. A caregiver cannot confirm or dismiss a prompt or
  give a reason. Nothing records who decided what. The clinician sees automated
  interpretations as if they had been escalated.
- **Impact:** the brief requires caregiver confirmation before a possible decline is
  escalated. Without it, an automated pattern can look like a clinical concern.
- **Correction:** add persisted `review_items` that snapshot the flag's evidence (rule,
  numbers, explanation, period, method and config version, linked observations).
  Status goes `awaiting_review` → `confirmed` | `dismissed`, and a reason is required for
  either decision. Dashboard panel to inspect the evidence and decide. Clinicians see
  **only confirmed** items, and unconfirmed flags are removed from their analytics. The
  report separates recorded observations, automated prompts awaiting review, and
  caregiver-confirmed concerns.
- **Acceptance:** API tests: scanning creates items; a decision without a reason gets a
  422; a clinician cannot see open or dismissed items or unconfirmed flags; a confirmed
  item appears in the clinician view and in the PDF under "caregiver-confirmed"; nothing
  is labelled a diagnosis.

### F3. No adaptation within an activity (High)

- **Requirement:** 1 (engagement-driven personalisation), 4.C.
- **Existing:** between-activity engine (above); fixed rounds in `createRounds`.
- **Evidence:** `ActivityRunnerScreen` never changes `_rounds` after `didChangeDependencies`;
  `RoundHost.attempt` only increments counters.
- **Gap:** three wrong answers in a row get no hint offer, the activity is not
  shortened and no rest is offered. The person who is struggling most does the most
  rounds. `hints_enabled` from the engine is ignored.
- **Impact:** frustration, which risks the patient disengaging. The adaptation is only
  visible on the *next* activity.
- **Correction:** add a pure, configurable in-session policy
  (`lib/adaptation/session_policy.dart`, thresholds in `personalization.toml [in_session]`,
  config-parity tested) that runs after every answer and round. Its actions are
  `continue`, `show_hint`, `shorten`, `offer_break` and `end_session`, each with reason
  codes. Stop and caregiver fatigue override everything else. Every decision is recorded
  as an event.
- **Acceptance:** unit tests show that different answer patterns lead to different,
  justified decisions. A widget test shows two wrong answers produce an automatic hint, and
  repeated struggling rounds shorten the activity.

### F4. Only per-activity aggregates are stored; no session event log (High)

- **Requirement:** 4.C (record attempts, correctness, hints, latency, completion or
  abandonment, repeated errors, help and break requests, caregiver fatigue).
- **Existing:** `activity_results` (aggregate counts, `metrics.mean_response_ms`).
- **Gap:** no per-attempt events, so no real latency, no record of *when* help or a break
  was asked for, and no record of what the system did in response. A run abandoned before
  the first answer leaves no result (by design), so only the session's `user_stopped`
  shows it.
- **Impact:** caregivers cannot inspect what happened in a session. The adaptation cannot
  be audited. "Response time" is a rough proxy.
- **Correction:** add an `activity_events` table on the phone (SQLite, written immediately)
  and on the server (migration 0009), pushed through the existing idempotent outbox as a
  new `activity_event` mutation and deduplicated by event ID. Event types: `attempt`
  (correct, latency_ms, round), `hint_requested`, `hint_shown_automatically`,
  `round_solved`, `round_skipped`, `paused`, `resumed`, `fatigue_reported` (source, level),
  `stop_requested`, `adaptation` (action plus reason codes). Results gain a real
  `median_attempt_latency_ms`. A dashboard session timeline shows the events.
- **Acceptance:** recorder tests show events are in SQLite and the outbox before any
  network call. Sync tests show a replayed push stores each event once, and an event for an
  unknown session is rejected rather than lost silently. An API test shows an outsider gets
  404 on the session timeline.

### F5. Relevant memories and hint advice from the engine are ignored by the activity (Medium)

- **Requirement:** 2 (Memory Bank used to personalise activities).
- **Existing:** `memory_retrieval.py` and the Dart engine return ranked approved memory IDs
  in `content_refs` / `memoryItemIds`.
- **Gap:** `launchActivity` does not receive them, so photo recall and familiar faces pick
  random approved memories, and the reason "uses your memories" is only loosely true.
- **Correction:** pass `memoryItemIds` and `hintsEnabled` from the suggestion to the
  launcher. Games put the referenced memories first. Hints-enabled lowers the automatic
  hint threshold.
- **Acceptance:** a game test shows referenced memories become the round targets first.

### F6. Memory metadata lacks a relationship field and a per-memory AI opt-out (Medium)

- **Requirement:** 2, 4.B (familiar relationships, consent controls), 9.
- **Existing:** kind, title, description, year, tags, photo, approval status, version,
  hard delete with media erasure (`models/memories.py`). Cloud AI needs patient-level
  `cloud_ai` consent.
- **Gap:** a person's relationship to the patient ("daughter", "neighbour") can only be
  written in free text or tags, so activities cannot say "your daughter". A caregiver
  cannot keep one sensitive memory out of AI prompts while still using it in games.
- **Correction (planned, not done in this pass):** add `relationship` (short text,
  caregiver-entered and never inferred from photos) and `allow_in_conversation` (default
  true; the conversation context builder skips memories set to false).
- **Acceptance:** a memory with `allow_in_conversation=false` is absent from the
  conversation context and present in games.

### F7. Patient home screen offers too many simultaneous choices (Medium)

- **Requirement:** 4.A (limited simultaneous choices, simple navigation, assisted use).
- **Existing:** large type (body 20 sp, labels 22 sp), 64 dp targets, high-contrast and
  reduced-motion modes, screen-reader labels (`ui/theme.dart`, FL a11y tests). The home
  screen shows a connection card, a suggestion card, a "today" card and **eight** big
  buttons (`home_screen.dart`). The runner shows five control buttons at once.
- **Gap:** settings, sync status, privacy and profile switching are caregiver tasks but sit
  at the same level as "Play".
- **Correction:** keep the suggestion and the four patient actions on the home screen. Move
  caregiver tasks (settings, sync, privacy, switch person, caregiver fatigue report) behind
  one "For caregivers" button.
- **Acceptance:** a widget test shows the home screen has at most five primary actions and
  caregiver tasks are reachable in one tap.

### F8. Voice: server-only recognition; Indic voice quality unverified (Medium, documented)

- **Requirement:** 5 (appropriate regional-language voice), 4.H.
- **Existing:** ASR with faster-whisper on the server (consent-gated, honest 503/422), and
  only the tiny English path was measured. Patient read-aloud uses Android system TTS
  with a per-language voice check, falling back to on-screen text. Server Indic
  Parler-TTS is integrated but has never been run. Activity answers are touch-only, which
  is a safe default.
- **Gap:** voice input does not work offline. Assamese, Bengali and Hindi ASR accuracy
  for older speakers is unknown. Bodo, Garo, Khasi, Mizo, Manipuri and Nagamese have no
  ASR. Whether the phone has an Assamese TTS voice depends on the device.
- **Correction in this pass:** documentation only (`docs/ai-and-ml-methods.md`), with a
  per-language support table that marks every unverified claim. The touch fallback
  already exists and is tested.
- **Acceptance:** existing `test_speech.py` (missing model → 503, unsupported language →
  422) and the Flutter speech tests (no voice → text stays on screen).

### F9. Report does not separate observation, interpretation and confirmation (High; part of F2)

- **Requirement:** 7, 4.F.
- **Existing:** a PDF built from stored data with methodology, missing days and the
  non-diagnostic notice (`reports/pdf.py`).
- **Gap:** review prompts appear as plain findings. Fatigue reports are not broken down by
  source. There are no caregiver decisions.
- **Correction:** report sections for "What was recorded", "Automated review prompts
  (interpretation, awaiting caregiver review)", "Caregiver-confirmed concerns (for
  clinician discussion)" and "Dismissed prompts", plus a fatigue-report breakdown by
  source and level. Too little data is stated plainly.
- **Acceptance:** a PDF text test checks the section order, the confirmed item's reason
  and the "insufficient data" wording for an empty period.

### Requirements that already align (no change needed now)

| Requirement | Why it aligns | Evidence |
|---|---|---|
| Only approved memories in activities and AI | Phone receives approved memories only; conversation guard drops unknown, pending and foreign IDs; model output never writes memories | `services/sync.py::_payload`, `conversation/guard.py`, `test_conversation.py` |
| Stop overrides AI | Stop is checked first in both engines; a model can only add stop, never remove it | `engine.py` step 1, `guard.py`, `test_model_cannot_hide_stop_or_fatigue` |
| No fabricated predictions | Missing scores and latency are `None` and treated as neutral; no ML model scores patients | `engine.py` (neutral outcomes), `compute.py` |
| Conservative trend detection | Baseline minimums; change must hold on ≥ 66 % of days; one bad session cannot raise a flag | `config/analytics.toml`, `test_one_bad_session_never_raises_a_flag` |
| Missing data is not low performance | Days without data are listed as missing | `compute.daily`, `DATA_GAP` rule |
| Patient isolation | Every patient route checks the relationship; outsiders get 404 | `services/access.py`, `test_authorization.py` |
| Clinician limits | Verified clinician plus valid grant plus current consent; no Memory Bank access | `access.py`, `test_access_lifecycle.py` |
| Sync without duplication | Per-mutation receipts; replay returns `duplicate` | `services/sync.py::push`, `test_sync.py` |

---

## 3. AI and ML reality check

Nothing in SNEHA is a trained model on project data. Details are in
[ai-and-ml-methods.md](ai-and-ml-methods.md).

| Feature | What it actually is | Label used before | Correct label |
|---|---|---|---|
| Activity selection and difficulty | Deterministic integer rules (TOML thresholds) | "personalization engine" | Rules-based, explainable |
| Memory retrieval | Tag, entity and relationship matching | "retrieval" | Rules-based |
| Review prompts | Descriptive statistics against the person's own baseline | "analytics" | Rules-based descriptive statistics |
| Conversation | Keyword rules by default; Gemini or local LLM optional and never run live here | "AI conversation" | Rules-based by default; pretrained LLM optional, **unverified live** |
| ASR | Pretrained Whisper (faster-whisper) on the server | "speech recognition" | Pretrained, server-side, verified only on English `tiny` |
| TTS | Android system TTS; server Parler-TTS never run | "regional voice" | Platform TTS; regional voices depend on the device and are unverified |

---

## 4. Repair plan and status

Implemented in the order the brief recommends. Status is tracked in
[implementation-progress.md](implementation-progress.md), and test evidence per acceptance
criterion is in [testing-and-validation.md](testing-and-validation.md). As of
2026-10-18, F1–F5, F7 and F9 are fixed with tests, F8 is documented, and F6 is half done:
the relationship field exists (migration 0012); the per-memory AI opt-out does not.

| Order | Finding | Increment |
|---|---|---|
| 1 | F4 | Session event log (phone SQLite → outbox → server table, dashboard timeline) |
| 2 | F3, F5 | In-session adaptation policy and runner integration; engine memory refs and hints reach the runner |
| 3 | F1 | Caregiver fatigue control on the phone; fatigue level on observations; fatigue observations synced to the phone; both engines respect caregiver severity |
| 4 | F2 | Persisted review items with caregiver confirm or dismiss; clinician sees confirmed only |
| 5 | F9 | Report sections: observations, interpretation, confirmed |
| 6 | — | Offline and sync tests for the new event and fatigue entities |
| 7 | F8 | Voice documentation (no code change) |
| 8 | F7, F6 | Home screen simplification; memory relationship and AI opt-out (if time allows) |
