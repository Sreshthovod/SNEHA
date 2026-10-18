# SNEHA architecture

SNEHA is an **assistive** cognitive-activity and memory-support platform for older adults
experiencing dementia-related difficulties, designed for India's North Eastern Region. It is
**not** a diagnostic system: nothing in SNEHA classifies, scores or diagnoses dementia.

## Components

```
┌──────────────────────────┐         ┌────────────────────────────┐
│ Patient app (Flutter)    │         │ Web dashboard (React/Vite) │
│ Android-first            │         │ caregivers + clinicians    │
│ SQLite on device         │         │ no local business data     │
│ offline activities       │         │                            │
└────────────┬─────────────┘         └──────────────┬─────────────┘
             │ HTTPS, bearer token (device session)  │ HTTPS, bearer token (password login)
             │ /api/v1/sync/push, /sync/pull, …      │ /api/v1/patients/…, /memories, …
             ▼                                       ▼
        ┌─────────────────────────────────────────────────────┐
        │ SNEHA API (FastAPI, Python 3.12)                    │
        │ authN/authZ · validation · business rules · audit   │
        │ sync · media storage · analytics · reports (later)  │
        │ conversation orchestration (later; Gemini optional) │
        └───────────────┬───────────────────────┬─────────────┘
                        │ SQLAlchemy 2 / Alembic│ local disk (SNEHA_MEDIA_ROOT)
                        ▼                       ▼
                 PostgreSQL (deployed)    protected media files
                 SQLite (dev/test only)
```

| Component | Path | Owns |
|---|---|---|
| Patient app | `apps/patient_app` | Local interaction, offline activity execution, on-device SQLite, sync outbox, (later) on-device personalization rules and TTS/ASR integration |
| Web dashboard | `apps/web_dashboard` | Caregiver and clinician UI. Holds no business rules; calls the API |
| API | `services/api` | Authorization, business rules, server persistence, sync, media, analytics, (later) conversation AI orchestration and PDF reports |
| Contracts | `packages/api_contracts` | `openapi.json` generated from the API (single source of truth) |
| Shared docs | `packages/shared_docs` | Glossary and terminology shared by all clients |

### Rules

- Both clients talk to the **same** versioned API (`/api/v1`). The API validates every
  request; clients never decide permissions.
- Business logic lives in the API. The one deliberate exception is the **rules-based
  personalization engine**, which must also run offline on the phone. The Python engine is
  the source of truth, and the Dart port is held to it by generated parity fixtures and a
  config-parity test (see `packages/shared_docs/personalization-rules.md`).
- The UI always distinguishes **locally available** functionality (activities, approved
  memories, routines) from **online** functionality (sharing progress, AI conversation,
  reports). `GET /api/v1/config/status` reports what the server can currently do.

## Databases

| Database | Where | Used by | Notes |
|---|---|---|---|
| SQLite | On the patient's phone | Patient app | Source of truth for offline work. Schema versioned in `lib/core/storage/local_database.dart` |
| PostgreSQL 16+ | Server | API (staging/production) | Required outside development; startup refuses SQLite in staging/production |
| SQLite | Developer machine | API (development and default tests) | Convenience only. The full test suite also runs against PostgreSQL |

**They are never automatically synchronised.** The device explicitly pushes and pulls
through the sync API. See [offline-strategy.md](offline-strategy.md).

## Backend layout (`services/api/app`)

```
main.py           create_app(): middleware (CORS, body-size limit, request ID), error handlers
core/             config, errors, security (argon2id, tokens), rate limit, body limit, time, ids
db/               Base + naming convention, UTCDateTime/enum types, sessions, migration helpers
models/           SQLAlchemy models (23 tables)
schemas/          Pydantic request/response models = the API contract
services/         access (authorization), auth, audit, activities, sync, files, history, changes
api/routes/       thin HTTP handlers, one module per area
migrations/       Alembic 0001–0015 (… 0009 activity events, 0010 fatigue level + fatigue sync, 0011 review items, 0012 memory relationship, 0013 instructions_repeated event, 0014 device pull progress, 0015 review evidence and context notes)
review/           review items: automated prompts (with evidence) → caregiver context notes and decision → clinician (confirmed only)
config/           personalization.toml, activities.toml, analytics.toml (versioned thresholds)
```

### Data model

| Area | Tables |
|---|---|
| Identity | `users`, `auth_sessions`, `device_pairing_codes` |
| Patients and access | `patient_profiles`, `caregiver_relationships`, `clinician_access_grants`, `consent_records` |
| Activities | `activity_definitions`, `activity_sessions`, `activity_results`, `activity_events` (per answer, hint, pause, tiredness, stop and in-activity decision), `personalization_states` |
| Memory Bank | `memory_items`, `memory_relationships`, `stored_files` |
| Care | `routine_items`, `caregiver_observations`, `conversation_records` (metadata only), `reports` |
| Personalization | `patient_preferences`, `activity_recommendations` (every recommendation with its explanation) |
| Observation workflow | `observation_revisions` (append-only correction history); `caregiver_observations.fatigue_level` |
| Human review | `review_items` (snapshot of an automated prompt's evidence + caregiver decision and reason) |
| Sync and audit | `sync_changes` (outbound log), `sync_mutations` (inbound receipts), `audit_events` |

Conventions: UUID string primary keys (clients may generate them offline); timezone-aware
UTC timestamps everywhere (`UTCDateTime` rejects naive values); enums stored as
`VARCHAR` + named `CHECK` constraints; deterministic constraint names so migrations behave
identically on SQLite and PostgreSQL; database `CHECK`s back up Pydantic validation (score
in [0,1], correct ≤ attempts, difficulty range, period order, and so on).

## Authentication and authorization

See [privacy-and-safety.md](privacy-and-safety.md#authentication) for details.

- **Dashboard users** (caregiver, clinician) sign in with email and password, hashed with
  argon2id. Login returns an **opaque 256-bit bearer token**; only its SHA-256 is stored, so
  logout and revocation are immediate.
- **Patients never type passwords.** A managing caregiver issues a single-use, 15-minute
  pairing code; the phone exchanges it for a long-lived device session.
- **Authorization** is centralised in `services/access.py`. Each patient-scoped endpoint
  declares the permission it needs; the caller's role and relationships come from the
  database.

| Role | Access |
|---|---|
| patient | Own profile, approved memories, routines; record activities; sync |
| caregiver | Patients with an active relationship: view, propose memories, observe, record, reports |
| managing caregiver | + edit profile, approve/correct/delete memories, add caregivers, grant clinicians, record consent, pair devices |
| clinician | Verified, valid unexpired grant, **and** current clinician-sharing consent: read-only profile, history, sessions, observations, reports. **No Memory Bank content** |
| admin | No patient data. Account operations via `scripts/manage.py` only |

No relationship → **404** (patient IDs cannot be probed). Relationship without the
permission → **403**. Every denial is audited.

## Core workflow after the alignment work (2026-10-18)

```
Caregiver (dashboard)                Phone (offline-first)                         Server
──────────────────────               ─────────────────────                         ──────
memories → approve ──── pull ──────▶ approved memories + photos
fatigue note (level) ── pull ──────▶ fatigue_reports (level, time; no note)
                                     engine (Dart port): next activity, level,
                                       hints, preferred memory IDs, rest
                                     runner: every answer/hint/pause/report ──▶ activity_events
                                       → session_policy: hint · shorten ·         (push, deduped
                                         offer rest · end   (stop always wins)     by event ID)
                                     caregiver button: a little / very tired ──▶ fatigue observation
                                     results + sessions ─────────────── push ──▶ analytics (own baseline)
analytics → review items ◀───────────────────────────────────────────────────── scan (rules)
confirm / dismiss + reason ──────────────────────────────────────────────────▶ clinician sees confirmed only
8–9 day PDF: Part 1 recorded · Part 2 automated prompts · Part 3 caregiver-confirmed
```

What runs where and why is in [ai-and-ml-methods.md](ai-and-ml-methods.md); safety rules in
[safety-and-privacy.md](safety-and-privacy.md).

## Memory-based activities (2026-10-18)

```
Caregiver: memory (kind, title, description, year, relationship*, tags, photo) + links
      │ approve                              * person memories only, never inferred
      ▼
Server ── pull (approved only) ──▶ Phone SQLite: memories (+ cached photo path), memory_links
                                          │
                                          ▼
            engine (unchanged): which activity + preferred memory IDs
                                          │
                                          ▼
      lib/activities/memory_content.dart: per activity, personal or generic + reason codes
        photo recall · familiar faces (relationship hint) · picture pairs (family photos)
        · sorting by type · story time (prompts from approved fields and links)
                                          │
                                          ▼
      runner / story time ── activity_started {memory_ids, content_source, reason_codes}
                          ── attempt / round_* {memory_id} ──▶ push ──▶ activity_events
                                                                          │
      Dashboard timeline: memory titles for the family; "a family memory" for clinicians ◀┘
```

Only content that is on the phone is used. A photo counts only once its file is cached, so
offline behaviour matches the cache.

## Adaptation loop (engine 1.2.0)

```
run (phone): answers, hints, "Read aloud" presses, tiredness, stop ──▶ events + result (SQLite → sync)
        ▲                                                                   │
        │ difficulty → level parameters (fewer options when easier)         ▼
        │ hints_enabled → first hint after 1 wrong answer          engine (phone offline / server)
        │ read_aloud_first → each question read aloud              stop > tiredness > support > variety
        └──────────────────── suggestion + reason codes ◀───────────────────┘
                              (recorded on activity_started with decided_on)
```

## Session safety lifecycle (fatigue-safety-plan.md)

```
start ──▶ in_progress ──┬─ Stop (asked once) ─────────────▶ abandoned / user_stopped
          │  ▲          ├─ I'm tired / very tired ─────────▶ abandoned / fatigue_detected + rest
          │  │          ├─ last round / shortened ─────────▶ completed
          ▼  │          └─ app killed ─▶ (next home) ──────▶ abandoned / timeout (at last step)
        paused (Pause, or the screen is left) ─ "Carry on" ─┘
Ending is written once; an ended session never restarts. Caregiver notes: phone button →
applied at once; dashboard → phone sync (≤ 1/min during an activity) → applied at the next
round; delivery shown on the dashboard from each device's last pull.
```
