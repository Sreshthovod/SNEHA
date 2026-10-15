# Stage 8: security, testing and validation report

Date: 2026-10-15. Everything below was measured or run on the machine and phone listed in
"Test environment". Nothing here is a clinical validation. **SNEHA is not production-ready**:
see [Remaining risks](#remaining-risks) and [Unverified requirements](#unverified-requirements).

## Summary

- Three code audits (authentication/authorization, files/validation/configuration, AI
  safety) found **no high-severity issue** and no cross-patient data access. They found
  27 medium/low defects. **22 are fixed with tests**; 5 remain open (listed below).
- The most serious defects were in **stop requests**: "No, stop", polite Hindi/Bengali/
  Assamese stop words and a model-reported stop intent were all ignored, and the phone's
  offline helper had no stop handling. All are fixed; a model can now only add a stop,
  never hide one.
- The new security and AI-safety API tests were also run against the original code: **34
  of them fail there** (12 security, 22 AI safety) and pass now. The remaining new cases
  are regression guards for behaviour that was already correct (for example stop phrases
  the old code already caught).
- All suites pass on SQLite and PostgreSQL 16. No known vulnerable dependency (pip-audit,
  npm audit, OSV scanner across 343 locked packages).

## Test environment

| Item | Value |
|---|---|
| Computer | Apple M4, 10 cores, 16 GB RAM, macOS 26.2 (25C56) |
| Phone | Samsung Galaxy A21s (SM-A217F), Android 12 (API 31), USB with `adb reverse` |
| Python / uv | 3.12.12 / 0.11.25; FastAPI 0.143.1, SQLAlchemy 2.1.4, ReportLab 5.0.1, faster-whisper 1.2.1, argon2-cffi 25.1.0 |
| Node | 26.4.0; Vite 8.3.4, Vitest 5.0.4 |
| Flutter | 3.41.2 stable; Gradle 8.14 on OpenJDK 21.0.12 (Android Studio's bundled Java 25 cannot run Gradle 8.14) |
| PostgreSQL | 16.2 via the `pgserver` Python package (no Docker or system PostgreSQL here) |

## Test results

| Suite | Command | Before Stage 8 | After Stage 8 |
|---|---|---|---|
| API on SQLite | `uv run pytest` | 267 passed, 2 skipped | **325 passed**, 3 skipped (2 PostgreSQL-only, 1 live Gemini) |
| API on PostgreSQL 16 | `SNEHA_TEST_POSTGRES_URL=… uv run pytest` | 268 passed, 1 skipped | **327 passed**, 1 skipped (live Gemini) |
| API lint, format, contract | `ruff check`, `ruff format --check`, `export_openapi.py --check` | pass | pass |
| Database migrations | `tests/test_migrations.py` | up/down on SQLite and PostgreSQL | plus **new model-vs-migration drift check** on both |
| Dashboard | `npm test`, `npm run lint`, `npm run build` | 56 passed, 2 skipped | 56 passed, 2 skipped (the live test, run separately below) |
| Dashboard API types | `npm run check:api` (newly added to `scripts/test_all.sh`) | not run | pass |
| Dashboard live end-to-end | `VITE_LIVE_API_URL=http://127.0.0.1:8770 npx vitest run live-api` against a real server | not run this stage | **2 passed** |
| Patient app | `flutter analyze`, `flutter test` | 165 passed | **172 passed**, no analyzer issues |
| Whole repo | `./scripts/test_all.sh` | — | **pass** (131 s wall clock) |

End-to-end workflow tests (`tests/test_e2e_workflows.py`) and offline/sync tests
(`tests/test_sync.py`, Flutter `test/offline`, `test/data`) are part of these totals.

**On the real phone:** a debug build was installed and run, paired with a dashboard code,
and attempted a sync; the server correctly refused to store data until data-processing
consent was recorded. A successful sync after consent was not confirmed during this stage.

## Security findings

Severity is the auditor's rating after the finding was re-checked against the code.

### Fixed

| # | Severity | Finding | Fix | Test |
|---|---|---|---|---|
| S1 | Medium | On PostgreSQL, a NUL character in free text caused a 500, and the logged exception contained the SQL parameters, i.e. the memory text. Integrity errors also logged emails. Reproduced. | Request models reject control characters (tab, newline, CR still allowed); the engine uses `hide_parameters=True`; database errors log only the error class and constraint name; a `DataError` returns 422. | `test_control_characters_are_rejected_before_the_database`, `test_database_errors_never_log_bound_values`, `test_ordinary_whitespace_is_still_allowed` |
| S2 | Medium | Withdrawing `clinician_sharing` blocked clinicians only while it stayed withdrawn; granting it again silently restored every old grant. | Withdrawal revokes all active grants (audited). | `test_withdrawing_sharing_revokes_grants_for_good` |
| S3 | Medium | A removed caregiver's paired phone and unused pairing codes kept working (up to 90 days). | Device sessions now record their pairing code (migration 0008). Removing a caregiver signs out phones they paired and cancels codes they issued. | `test_removing_a_caregiver_signs_out_the_phone_they_paired` |
| S4 | Medium | Replaced memory photos stayed on disk and downloadable; one photo could be attached to two memories. | A replaced photo is erased (row and file); a photo can belong to only one memory. | `test_replaced_photo_is_erased`, `test_one_photo_cannot_belong_to_two_memories` |
| S5 | Medium | Patient app data (local database, cached photos) was included in Android cloud backup. | `allowBackup="false"`, `fullBackupContent="false"` and data-extraction rules excluding everything. Verified in the built release APK manifest. | Manual APK inspection (`aapt2 dump xmltree`) |
| S6 | Low–Medium | Photos could be uploaded without data-processing consent. | Upload requires the consent. | `test_photo_upload_requires_data_processing_consent` |
| S7 | Low | A helper could delete an observation after it was reviewed, wiping its history. | Only managing caregivers can delete reviewed or resolved observations. | `test_helper_cannot_delete_a_reviewed_observation` |
| S8 | Low | Sync sent the phone links between pending/rejected memories. | Links are sent only while both memories are approved, and are re-sent when approval changes. | `test_sync_never_sends_links_between_unapproved_memories` |
| S9 | Low | Two concurrent requests could redeem one pairing code. | The code is claimed with one conditional `UPDATE`. | `test_a_pairing_code_is_claimed_atomically` (sequential guard; true concurrency not tested) |
| S10 | Low | "Sign out all devices" left unused pairing codes valid. | Also cancels unused codes. | `test_revoking_devices_also_cancels_unused_codes` |
| S11 | Low | `SNEHA_DATABASE_ECHO` (logs every statement with patient data) was allowed in production; `/docs` and `/openapi.json` were public in production. | Production refuses echo and serves no interactive docs or schema. | `test_production_rejects_sql_echo`, `test_production_hides_interactive_docs` |
| S12 | Low | Removing a profile on the phone left its server session valid. | The phone calls `/auth/logout` first (best effort; removal still works offline). | Flutter: "removing a profile signs the phone out on the server", "…still works offline" |
| S13 | Low | The rate limiter's memory grew with every distinct client. | Idle keys are evicted above 10 000 entries. | `test_rate_limiter_forgets_idle_clients` |
| S14 | Low | CORS allowed credentials although only bearer tokens are used. | `allow_credentials=False`. | Existing CORS tests |
| S15 | Low | The documented dashboard CSP blocked protected photos (`blob:` URLs), inviting operators to weaken it. | `docs/deployment.md` CSP now adds `img-src 'self' blob:`, `object-src 'none'`, `base-uri 'none'`, `frame-ancestors 'none'`. | Documentation |
| S16 | Low | The release build was always signed with the debug key. | Gradle reads `android/key.properties` (git-ignored); without it, it warns and falls back to the debug key. | Manual build; the release APK built here is debug-signed (no key exists) |

### Open

| # | Severity | Finding | Why not fixed now |
|---|---|---|---|
| O1 | Medium if an owner tier is wanted | Any managing caregiver can remove other managers (including the patient's creator) and erase the patient. | Needs a product decision: should there be an owner role? |
| O2 | Low | Login reveals that an account exists after 5 failed attempts (423 for real accounts, 401 otherwise); anyone can lock an account for 15 minutes. Inviting a caregiver or clinician also reveals whether an email is registered. | Fixing it means dropping the "account locked" message or tracking unknown emails; needs a UX decision. Login is rate-limited. |
| O3 | Low | Rate limits are per process and per IP; pairing codes have about 40 bits of entropy. | Needs a shared limiter (proxy or Redis) at deployment. |
| O4 | Low | No storage quotas: every `POST /reports` creates a PDF and there is no report deletion; uploaded photos never attached to a memory are not cleaned up. | Needs a retention policy. |
| O5 | Low | Deploying without `SNEHA_ENVIRONMENT=production` silently uses development rules (development pairing secret, SQLite and http CORS allowed). | Changing the default affects every developer; documented in deployment instead. |

Checked and sound: argon2id hashing with rehash on login; 256-bit session tokens stored as
SHA-256; per-request expiry, revocation and active checks; every patient-scoped route
re-checks ownership of child resources; clinicians need verification, a valid grant and
current consent on every request; file type from bytes, random storage names, path
containment, `nosniff` / `no-store` / `default-src 'none'` on downloads; PDF text escaped
before ReportLab; no committed secrets; `SecretStr` for keys; audit details allow-listed;
no `dangerouslySetInnerHTML` in the dashboard; tokens in secure storage on the phone;
cleartext HTTP only in the debug manifest (confirmed absent from the release APK).

## AI safety

| Scenario | Result | Tests |
|---|---|---|
| Fabricated memories | Sound. Only this patient's approved memories reach the model; the guard drops unknown, foreign and pending IDs; replies are templates plus stored titles; model-suggested memories are saved as pending. | Existing guard tests, plus `test_prompt_injection_in_memory_title_and_text` |
| Invalid model output | Sound. Malformed or schema-invalid output falls back to the deterministic engine; extra or overlong fields are rejected. | `test_gemini_failures_fall_back_to_deterministic`, `test_overlong_or_extra_field_model_output_falls_back_but_stop_still_works` |
| **Stop requests** | **Fixed.** "No, stop", "I don't want to do this anymore", रुकिए, बस करो, থামুন, ৰখক and similar now stop. Negation never cancels a stop. The model's flags, the model's intents and keyword detection are OR-ed, so a model cannot hide a stop. The offline helper now handles stop. | `test_stop_variants_are_respected` (17 cases), `test_model_cannot_hide_stop_or_fatigue` (5), Flutter "stop always wins…" |
| Fatigue false positives | **Fixed.** "No, I'm tired" is tired; "मैं थका नहीं हूँ" is not. One "I'm tired" press was counted twice in analytics (once on the result, once on the session), so two presses could raise "repeated tiredness"; now counted once. Breaks are time-limited, never permanent. | `test_fatigue_negation` (9), `test_one_tired_press_counts_once` |
| Distress | Distress is never negated in Indic text. Offline, feeling unwell, scared or lost now reply with "call a family member… 112", even if the person also says stop (matching the server). | `test_not_scared_stays_negated_but_never_hides_stop`, Flutter safety-reply tests |
| Repeated errors | Sound. Two struggles lower difficulty and turn hints on; no discouraging or diagnostic wording. | Existing engine tests |
| Unsupported languages | Sound: 422 `language_unsupported`. Draft Hindi/Assamese/Bengali reply sets fall back to English for some replies, so one reply can mix languages. | Existing speech and conversation tests |
| Offline fallback | Sound. Gemini needs both configuration and `cloud_ai` consent; any failure goes to the deterministic engine. The docs wrongly described a Gemini → local → deterministic chain; the code uses one provider, and the docs now say so. | `test_no_cloud_consent_means_no_gemini_call`, `test_deterministic_path_needs_no_network` |
| Missing model weights | **Fixed.** Speech status said "available" when weights existed but the package was not installed; corrupt weights gave a 500; the TTS loader could download a tokenizer from the internet at runtime. Now status checks packages too, load errors are a clean 503, and everything loads with `local_files_only=True`. | `test_status_is_honest_when_package_is_missing`, `test_corrupt_asr_weights_are_503_without_internal_details`, `test_corrupt_tts_weights_are_a_clean_unavailable_error`, `test_tts_never_downloads_the_description_tokenizer` |
| Authorization bypass via models | Sound. Every AI endpoint authorizes the patient; model output never writes memories. | `test_outsiders_get_404_everywhere_and_change_nothing`, conversation and speech consent tests |
| Fabricated clinical findings | Sound. No language model writes analytics or reports; review prompts are descriptive; every PDF page carries the non-diagnostic notice; the guard blocks diagnostic words in model output. Caregiver-written notes are printed verbatim in reports. | `test_pdf_contains_required_sections`, `test_one_bad_session_never_raises_a_flag` |

Deliberate trade-offs: "don't stop" also stops, and Hindi "बंद" anywhere in a sentence
stops. Over-triggering stop is the safe direction.

## Performance

Measured with a sequential client on the same machine (loopback), one uvicorn worker, a
fresh database seeded with 30 memories and 36 sessions over 9 days. Script:
`bench_api.py` (synthetic data only). These are single-client latencies, **not** a load
test.

| Endpoint | n | SQLite p50 / p95 (ms) | PostgreSQL 16 p50 / p95 (ms) |
|---|---|---|---|
| `POST /auth/login` (argon2id verify) | 8 | 30.3 / 39.8 | 27.0 / 29.2 |
| `GET /auth/me` | 50 | 0.8 / 1.0 | 0.9 / 1.1 |
| `POST /patients/{id}/memories` | 30 | 2.1 / 2.3 | 2.2 / 2.6 |
| `GET /patients/{id}/memories` (30 items) | 30 | 1.4 / 1.8 | 1.7 / 2.1 |
| `POST /activities/next` | 36 | 2.8 / 3.0 | 3.5 / 3.7 |
| `POST /activities/result` | 36 | 3.8 / 4.0 | 5.0 / 5.2 |
| `GET /sync/pull?since=0` | 20 | 6.1 / 6.3 | 9.1 / 9.7 |
| `POST /conversation/analyze` (deterministic) | 30 | 4.0 / 4.5 | 4.8 / 5.1 |
| `GET /patients/{id}/analytics` (9 days) | 15 | 11.3 / 11.6 | 12.1 / 12.4 |
| `POST /patients/{id}/reports` (8-day PDF, 8.6 KB) | 5 | 24.9 / 26.1 | 25.7 / 31.0 |
| `POST /speech/transcribe`, faster-whisper **tiny**, CPU, 2.6 s clip, first call (model load) | 1 | 553 | 413 |
| `POST /speech/transcribe`, same, warm | 5 | 145 / 168 | 144 / 168 |

The tiny model transcribed the synthetic English clip ("Good morning. I would like a cup of
tea.") correctly. It is for testing only; the recommended `small` model, Indic speech and
real older voices were not measured.

| Build | Result |
|---|---|
| Dashboard production build | 1.6 s; JS 414 KB (126 KB gzip), CSS 15 KB (3.6 KB gzip) |
| Patient app release APK | 69 s with a warm Gradle cache; 53.5 MB (universal APK, not split per ABI) |
| Patient app first debug build | about 10 minutes, mostly a one-time NDK and CMake download |
| Full `test_all.sh` | 131 s |

Not measured: performance on the phone (activity start, on-device engine, database size),
concurrent users, the Gemini and local LLM providers, and server TTS.

## Offline capability

Unchanged by this stage except the offline helper. On the phone without a connection:
activities, story time, suggestions (on-phone engine), approved memories and cached
photos, progress, settings, and the conversation helper (now with stop, rest and safety
replies) all work. Results queue in the outbox with retry and backoff. Pairing, voice
input, caregiver observations and server suggestions need a connection. The offline paths
are covered by Flutter tests; on the real phone only pairing and a sync attempt were
exercised.

## Model limitations

- **Deterministic engine:** keyword rules. Hindi, Assamese and Bengali keywords are drafts
  written without native-speaker review. Bodo, Garo, Khasi, Manipuri, Mizo and Nagamese
  have no keywords and no speech recognition.
- **Gemini and local LLM:** integrated behind the guard but not run live in this stage.
- **Speech recognition:** only the tiny English path was measured. Accuracy for older
  speakers, Indic languages and noisy rooms is unknown.
- **Server TTS (Indic Parler-TTS):** never run on this machine; the tests use fake modules.
- **Personalization and analytics:** rule-based and descriptive. They have not been
  validated with patients or clinicians and make no clinical claims.

## Remaining risks

- The open security findings O1–O5 above.
- No release signing key exists, so the release APK built here is debug-signed and must
  not be distributed.
- The phone's local database is not encrypted (it relies on the Android app sandbox).
- The dashboard keeps its token in `sessionStorage`, so cross-site scripting would expose
  it; the CSP is the main protection.
- Caregiver-written notes appear verbatim in clinician PDFs.
- Some draft-language replies mix languages.

## Unverified requirements

- Clinical validation of any kind, and an accessibility study with older users.
- Native-speaker review of all non-English text.
- Load, concurrency and soak testing; the pairing race is guarded but not tested
  concurrently.
- A successful phone sync after consent, microphone recording and system TTS on a real
  device, behaviour across Android versions and low-end phones.
- Live Gemini, the local LLM and server TTS.
- Deployment behind a real proxy with TLS, a shared rate limiter and backups.
