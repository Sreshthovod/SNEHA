# API contracts

**Source of truth:** [`packages/api_contracts/openapi.json`](../packages/api_contracts/openapi.json),
generated from the FastAPI app by `scripts/export_openapi.sh`. The test
`tests/test_contract.py` fails if the committed file drifts from the code, so a contract
change is always a reviewed diff. Interactive docs: `http://localhost:8000/docs`.

## Conventions

| Topic | Rule |
|---|---|
| Base path | `/api/v1`. Breaking changes require `/api/v2` |
| Auth | `Authorization: Bearer <opaque token>` from `/auth/login` (dashboard) or `/auth/device/pair` (patient phone) |
| IDs | UUID strings. Clients may supply IDs for offline-created records (sessions, results, conversations, memories) |
| Timestamps | ISO-8601 **with offset** on input (naive values → 422); always UTC (`Z`/`+00:00`) on output |
| Dates | `YYYY-MM-DD`, interpreted in the patient's IANA timezone (default `Asia/Kolkata`) |
| Unknown fields | Rejected (422). Prevents typos and mass assignment such as `{"status": "approved"}` |
| Request size | JSON bodies ≤ 1 MiB (`SNEHA_MAX_JSON_BODY_BYTES`); uploads ≤ 5 MiB (`SNEHA_MAX_UPLOAD_BYTES`) → 413 |
| Request ID | Send `X-Request-ID` (≤ 64 chars, `[A-Za-z0-9._-]`) or one is generated; echoed in the response and in error bodies |
| Idempotency | Session creation and result submission are idempotent by client ID (200 on replay). Sync uses `mutation_id` receipts |
| Concurrency | Memory corrections and reviews require `expected_version`; a mismatch → 409 `version_conflict` |

## Error envelope

Every error, including 404s, validation errors and 500s, has this shape:

```json
{"error": {"code": "not_found", "message": "Patient not found.", "request_id": "…", "details": []}}
```

| Status | Typical `code` | Meaning |
|---|---|---|
| 401 | `unauthorized`, `invalid_pairing_code` | Missing, expired or revoked token |
| 403 | `forbidden`, `not_paired` | Authenticated and related to the patient, but lacking this permission |
| 404 | `not_found` | Does not exist **or** the caller has no relationship to the patient (indistinguishable on purpose) |
| 409 | `consent_required`, `version_conflict`, `result_conflict`, `email_taken`, `last_manager`, `confirmation_mismatch`, `report_ready`, `not_open`, … | State conflict |
| 413 | `content_too_large`, `file_too_large` | Body or upload too large |
| 415 | `unsupported_media_type` | Upload is not JPEG/PNG/WebP (detected from bytes) |
| 422 | `validation_error` (+ `details[]`), `invalid_difficulty`, `unknown_activity`, … | Invalid input |
| 423 | `account_locked` | Too many failed logins (15 min) |
| 429 | `rate_limited` | Too many credential attempts (`Retry-After`) |
| 503 | `model_missing`, `speech_unavailable` | Optional speech model not installed |
| 503 | `database_unavailable` | Database unreachable (`Retry-After`) |

## Endpoints

| Area | Method | Path | Summary |
|---|---|---|---|
| health | GET | `/api/v1/health` | Liveness check |
| health | GET | `/api/v1/health/ready` | Readiness check |
| auth | POST | `/api/v1/auth/device/pair` | Exchange a caregiver-issued pairing code for a patient device session |
| auth | POST | `/api/v1/auth/login` | Login |
| auth | POST | `/api/v1/auth/logout` | Logout |
| auth | GET | `/api/v1/auth/me` | Me |
| auth | POST | `/api/v1/auth/register` | Create a caregiver or clinician account |
| config | GET | `/api/v1/config/status` | Config Status |
| patients | GET | `/api/v1/patients` | List Patients |
| patients | POST | `/api/v1/patients` | Create Patient |
| patients | GET | `/api/v1/patients/{patient_id}` | Get Patient |
| patients | PATCH | `/api/v1/patients/{patient_id}` | Update Patient |
| patients | GET | `/api/v1/patients/{patient_id}/caregivers` | List Caregivers |
| patients | POST | `/api/v1/patients/{patient_id}/caregivers` | Add Caregiver |
| patients | DELETE | `/api/v1/patients/{patient_id}/caregivers/{relationship_id}` | Remove Caregiver |
| patients | GET | `/api/v1/patients/{patient_id}/clinician-grants` | List Grants |
| patients | POST | `/api/v1/patients/{patient_id}/clinician-grants` | Create Grant |
| patients | DELETE | `/api/v1/patients/{patient_id}/clinician-grants/{grant_id}` | Revoke Grant |
| patients | GET | `/api/v1/patients/{patient_id}/consents` | Get Consents |
| patients | POST | `/api/v1/patients/{patient_id}/consents` | Record Consent |
| patients | POST | `/api/v1/patients/{patient_id}/devices/revoke` | Revoke Devices |
| patients | POST | `/api/v1/patients/{patient_id}/erase` | Erase Patient |
| patients | POST | `/api/v1/patients/{patient_id}/pairing-codes` | Create Pairing Code |
| memories | GET | `/api/v1/patients/{patient_id}/memories` | List Memories |
| memories | POST | `/api/v1/patients/{patient_id}/memories` | Create Memory |
| memories | DELETE | `/api/v1/patients/{patient_id}/memories/{memory_id}` | Delete Memory |
| memories | GET | `/api/v1/patients/{patient_id}/memories/{memory_id}` | Get Memory |
| memories | PATCH | `/api/v1/patients/{patient_id}/memories/{memory_id}` | Correct Memory |
| memories | POST | `/api/v1/patients/{patient_id}/memories/{memory_id}/approve` | Approve Memory |
| memories | POST | `/api/v1/patients/{patient_id}/memories/{memory_id}/reject` | Reject Memory |
| memories | GET | `/api/v1/patients/{patient_id}/memory-relationships` | List Memory Relationships |
| memories | POST | `/api/v1/patients/{patient_id}/memory-relationships` | Create Memory Relationship |
| memories | DELETE | `/api/v1/patients/{patient_id}/memory-relationships/{relationship_id}` | Delete Memory Relationship |
| personalization | GET | `/api/v1/activities/catalog` | Catalog |
| personalization | POST | `/api/v1/activities/next` | Next Activity |
| personalization | POST | `/api/v1/activities/result` | Submit Result |
| personalization | GET | `/api/v1/patients/{patient_id}/memories-retrieve` | Retrieve Memories |
| personalization | GET | `/api/v1/patients/{patient_id}/preferences` | Get Preferences |
| personalization | PUT | `/api/v1/patients/{patient_id}/preferences` | Put Preferences |
| personalization | GET | `/api/v1/patients/{patient_id}/progress` | Get Progress |
| personalization | GET | `/api/v1/patients/{patient_id}/recommendations` | List Recommendations |
| activities | GET | `/api/v1/activities` | List Activities |
| activities | GET | `/api/v1/patients/{patient_id}/history` | Get History |
| activities | GET | `/api/v1/patients/{patient_id}/sessions` | List Sessions |
| activities | POST | `/api/v1/patients/{patient_id}/sessions` | Create Session |
| activities | POST | `/api/v1/patients/{patient_id}/sessions/{session_id}/complete` | Complete Session |
| activities | GET | `/api/v1/patients/{patient_id}/sessions/{session_id}/results` | List Results |
| activities | POST | `/api/v1/patients/{patient_id}/sessions/{session_id}/results` | Submit Result |
| care | GET | `/api/v1/patients/{patient_id}/observations` | List Observations |
| care | POST | `/api/v1/patients/{patient_id}/observations` | Create Observation |
| care | DELETE | `/api/v1/patients/{patient_id}/observations/{observation_id}` | Delete Observation |
| care | GET | `/api/v1/patients/{patient_id}/observations/{observation_id}` | Get Observation |
| care | PATCH | `/api/v1/patients/{patient_id}/observations/{observation_id}` | Correct Observation |
| care | POST | `/api/v1/patients/{patient_id}/observations/{observation_id}/resolve` | Resolve Observation |
| care | POST | `/api/v1/patients/{patient_id}/observations/{observation_id}/review` | Review Observation |
| care | GET | `/api/v1/patients/{patient_id}/observations/{observation_id}/revisions` | List Observation Revisions |
| care | GET | `/api/v1/patients/{patient_id}/reports` | List Reports |
| care | POST | `/api/v1/patients/{patient_id}/reports` | Request Report |
| care | GET | `/api/v1/patients/{patient_id}/reports/{report_id}` | Get Report |
| care | POST | `/api/v1/patients/{patient_id}/reports/{report_id}/generate` | Regenerate Report |
| care | GET | `/api/v1/patients/{patient_id}/routines` | List Routines |
| care | POST | `/api/v1/patients/{patient_id}/routines` | Create Routine |
| care | DELETE | `/api/v1/patients/{patient_id}/routines/{routine_id}` | Delete Routine |
| analytics | GET | `/api/v1/patients/{patient_id}/analytics` | Get Analytics |
| analytics | GET | `/api/v1/patients/{patient_id}/analytics/review-flags` | Get Review Flags |
| conversation | POST | `/api/v1/conversation/analyze` | Analyze |
| speech | GET | `/api/v1/speech/status` | Speech Status |
| speech | POST | `/api/v1/speech/synthesize` | Synthesize |
| speech | POST | `/api/v1/speech/transcribe` | Transcribe |
| files | GET | `/api/v1/files/{file_id}/content` | Download File |
| files | POST | `/api/v1/patients/{patient_id}/media` | Upload Media |
| sync | GET | `/api/v1/sync/pull` | Pull |
| sync | POST | `/api/v1/sync/push` | Push |

_73 operations._

## Key flows

**Onboarding.** Caregiver `POST /auth/register` → `POST /auth/login` → `POST /patients`
(the creator becomes a managing caregiver) → `POST /patients/{id}/consents`
(`data_processing`) → `POST /patients/{id}/pairing-codes` → enter the code on the phone →
`POST /auth/device/pair`.

**Clinician access.** The clinician registers; an operator verifies them out of band
(`scripts/manage.py verify-clinician`). A managing caregiver records `clinician_sharing`
consent, then `POST /patients/{id}/clinician-grants` (≤ 180 days). Access ends at expiry,
on revoke, on consent withdrawal, or if the clinician is unverified.

**Memory Bank.** Non-managers (and the patient) propose memories → `pending_approval`.
Managers create approved memories directly, or approve/reject proposals. Corrections use
`PATCH` with `expected_version`. `DELETE` removes the content and photo permanently.

**Erasure.** `POST /patients/{id}/erase` with `{"confirm_display_name": "<exact name>"}`
(managing caregivers only) permanently deletes the profile and every patient-scoped row
and file, and the patient's device login. Only an audit entry (IDs, no content) remains.

**Activity data.** Online:
1. `POST /patients/{id}/sessions`
2. `POST /activities/next` returns a recommendation: activity, difficulty, level
   parameters, reason codes, supporting records, algorithm and config versions, fallback
   status.
3. `POST /activities/result` stores the result (idempotent by ID), updates the
   personalization state and returns `next`.

Offline: the same records via `POST /sync/push`. `stop_requested` always yields
`action: "stop"`; reported tiredness yields `action: "break"` with an easy alternative.

**Conversation.** `POST /conversation/analyze` returns:
- a validated extraction, with each mention marked `stored_fact` or `uncertain`
- resolved **approved** memories
- memory candidates (never saved)
- safety (distress → fixed message, no activity)
- a suggestion from the personalization engine
- a template reply

`provider` and `fallback.reason` say which engine answered.

**Speech.**
- `GET /speech/status` reports per-language support.
- `POST /speech/transcribe` (multipart WAV + `patient_id` + `language`, needs
  `voice_processing` consent) returns the transcript, which is not stored.
- `POST /speech/synthesize` returns `audio/wav`.
- Missing model → 503 `model_missing`; unsupported language → 422
  `language_unsupported`; bad audio → 422 `invalid_audio`.

**Analytics and reports.**
- `GET /patients/{id}/analytics?from&to` returns descriptive metrics, a baseline
  comparison (only when minimum observations are met), completeness and review flags.
- `POST /patients/{id}/reports` (8–9 days) **generates the PDF immediately** and returns
  201 with `status: "ready"` and `file_id`, or `failed`.
- `POST …/reports/{rid}/generate` retries a failed report.
- Download with `GET /files/{file_id}/content`.

**Observations.**
- `POST` creates, recording the source and author.
- `PATCH` corrects, and needs `expected_version` plus `reason`; revision history is at
  `GET …/revisions`.
- `POST …/review` and `…/resolve` are for managing caregivers.
- 409 codes: `version_conflict`, `observation_resolved`, `not_open`,
  `already_resolved`.

## Client types

- **Dashboard**: types are **generated** from `openapi.json` (`npm run gen:api`), and
  `npm run check:api` fails if they are stale.
- **Patient app**: typed Dart models in `lib/data/api/` mirror the schemas it uses, and
  its tests are built from the contract's field names.
