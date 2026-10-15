# Privacy and safety

SNEHA handles sensitive health-adjacent data about people who may have reduced capacity to
consent. The design assumes India's Digital Personal Data Protection Act, 2023 applies
(children's and guardian provisions, consent, purpose limitation, erasure). This document
is engineering guidance, not legal advice; get a legal review before any real deployment.

## Not a medical device

- SNEHA provides activities and memory support. It does **not** diagnose, screen, stage or
  predict any condition.
- History, analytics and report endpoints return **descriptive** statistics with a fixed
  disclaimer. There is no "cognitive score". Review prompts say only that a sustained
  change *may be worth reviewing* with a caregiver or clinician; they never state decline.
- Caregiver observations are free-text notes about the day, not clinical assessments.

## Data minimisation

| Data | Decision |
|---|---|
| Date of birth | Not collected. Only `birth_year` (optional) |
| Patient login | No email or password. Device pairing only |
| Conversation transcripts and audio | **Not stored on the server.** Metadata only; the schema has no transcript field, and pushing one is a 422 |
| Activity metrics | Numeric only, ≤ 20 keys, `snake_case` names; free text is rejected |
| Uploaded photos | JPEG/PNG/WebP only, type detected from bytes, random storage names, original filename discarded |
| Real patient data in code, tests or demos | Forbidden. Fixtures are labelled synthetic (`is_synthetic`, "Synthetic …" names, `example.org` emails) |

## Consent

`consent_records` is an append-only ledger. The latest record per type is the current
state, and each record stores who gave it (`patient`, `legal_representative`,
`caregiver_on_behalf`) and the policy version.

| Consent | Enforced by |
|---|---|
| `data_processing` | Required to create memories, sessions or results, and to sync |
| `clinician_sharing` | Required to create a grant **and** checked on every clinician request; withdrawing it cuts off access immediately |
| `cloud_ai` | Required before any text is sent to Gemini (otherwise the deterministic engine is used) |
| `voice_processing` | Required for `/speech/transcribe` |

## Authentication

- Passwords: argon2id (argon2-cffi defaults, RFC 9106), 12–128 characters, rehashed on
  login when parameters change. Timing is equalised for unknown accounts.
- Brute force: per-account lockout (5 failures → 15 min, `423`), plus a per-IP limiter on
  login, registration and pairing (`429`). The limiter is per process; with multiple
  replicas also rate-limit at the proxy.
- Tokens: opaque 256-bit random values; the DB stores only SHA-256. Dashboard sessions last
  12 h, device sessions 90 days. Logout revokes; caregivers can revoke all devices (lost
  phone); deactivating a user invalidates their tokens immediately.
- Pairing codes: 8 characters from a 31-symbol alphabet (~40 bits), single use, 15-minute
  expiry, stored as an HMAC-SHA-256 with `SNEHA_SECRET_KEY`, rate limited. Issuing a new
  code invalidates older ones.
- Tokens are bearer headers, not cookies, so CSRF does not apply. The dashboard must keep
  tokens in memory or `sessionStorage`, never in `localStorage` (Stage 4).

## Authorization

Server-enforced in `services/access.py` (see [architecture.md](architecture.md#authentication-and-authorization)).
Client-supplied roles and IDs are never trusted: the role is read from the database, the
patient ID in the URL is checked against the caller's relationships, and records are
re-checked against the patient (a session ID from another patient → 404). Tests in
`tests/test_authorization.py` exercise every patient-scoped endpoint for four kinds of
outsider and assert 404 with no data change, plus a positive control.

## Protected files

Stored under `SNEHA_MEDIA_ROOT` (outside any web root), served only via
`GET /files/{id}/content` after the same authorization as the owning record. Patients see
only photos attached to approved memories. Responses send `Cache-Control: private,
no-store`, `X-Content-Type-Options: nosniff` and `Content-Security-Policy: default-src
'none'`. Deleting a memory deletes its photo bytes.

## Audit

`audit_events` records actor, action, outcome, patient, target and request ID for logins,
pairing, every write, and every authorization denial. Detail keys are **allow-listed** in
code (`services/audit.py`), so passwords, tokens, pairing codes, memory content, notes and
transcripts cannot be logged; a test asserts none of them appear.

## Conversation and speech

- Conversation text is processed in memory to produce a validated extraction and is
  **never stored or logged**. Only metadata is kept: provider, language, turn count,
  coarse intents and fallback flag.
- Gemini receives text only with current `cloud_ai` consent, and only minimal context
  (stored memory titles and tags needed to resolve mentions).
- Voice audio is accepted only with `voice_processing` consent, decoded in memory and
  discarded. Transcripts are returned to the caller only. Tests check that text never
  appears in logs.
- Memory candidates from conversation are never saved automatically. A patient may
  propose one; it is `pending_approval` until a managing caregiver approves it.

## Analytics and reports

- Metrics are descriptive and compared only with the person's **own** earlier activity,
  and only when minimum observation counts are met.
- Review prompts follow conservative, configured rules (`config/analytics.toml`): never
  from a single session, require a consistent change across days, and treat missing data
  as missing, never as decline. Each prompt carries its rule, numbers and a "not a
  finding" disclaimer.
- PDFs are generated from stored data only, with no LLM, and include methodology and a
  non-diagnostic disclaimer. Everyone who can view a report may also view the
  observations it contains (enforced by a test).

## Erasure (right to be forgotten)

`POST /api/v1/patients/{id}/erase` (managing caregivers, typed-name confirmation) deletes
the patient and all their data, including photo bytes and the patient's device account,
in one transaction (database `ON DELETE CASCADE`). Audit entries keep only IDs and the
fact that erasure happened. A patient's phone also offers "Remove this profile from this
phone", which deletes the local copy only. Data export is not implemented yet.

## Errors

Every error uses the same envelope. Database and unexpected errors return generic messages;
details go to server logs only. Constraint violations never echo SQL or values.

## Safety in the patient experience

- Never test or quiz in a way that shames: always show the answer, praise effort, and offer
  to stop.
- "I'm tired" in any game ends it gently. The engine then offers a break and an easy
  activity, and a stop request always wins.
- Unapproved or rejected memories are never shown to the patient. Only caregivers curate
  the Memory Bank, which protects against distressing or incorrect content.
- The conversation assistant does not give medical advice. Distress (detected
  deterministically, even if a model misses it) gets a fixed safety message (call family;
  emergency 112) and no activity.
