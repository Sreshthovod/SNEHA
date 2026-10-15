# Implementation roadmap

Each stage ends with passing tests on SQLite **and** PostgreSQL, a regenerated and
committed OpenAPI contract, and updated docs. "Done" means implemented and tested, not
scaffolded.

| Stage | Scope | Status |
|---|---|---|
| 0 | Monorepo, three apps, config, health, migrations, tests, docs | ✅ |
| 1 | Patient app screens (17) and caregiver/clinician dashboard (13 areas), design systems | ✅ |
| 2 | Database, auth (password + device pairing), authorization, consent, Memory Bank, activities, sync, media, audit | ✅ |
| 3 | Deterministic personalization engine, activity specs, memory retrieval, explainable recommendations | ✅ |
| 4 | Conversation: Gemini / local / deterministic providers with guards, `/conversation/analyze` | ✅ |
| 5 | Speech (faster-whisper ASR verified; Indic Parler-TTS integrated; phone TTS), offline engine on the phone, sync retry/backoff | ✅ (TTS model not run here) |
| 6 | Analytics (pandas/NumPy), review-flag rules, observation workflow, ReportLab PDFs, report automation | ✅ |
| 7 | Integration across the apps, typed contracts, end-to-end workflows, feature matrix | ✅ |
| Next | Device and emulator testing, native-speaker review of non-English content, Indic font for PDFs, proxy rate limits, accessibility study with older users, deployment | |

See [feature-matrix.md](feature-matrix.md) for every feature's screen, endpoint, storage,
provider, offline support and tests.

## Known gaps (tracked, not hidden)

- **No Android build or device run.** The Android SDK is not installed on the build
  machine. The microphone (`record`) and system TTS (`flutter_tts`) are untested on real
  devices.
- **Non-English content is draft.** Hindi, Assamese and Bengali UI strings, conversation
  keywords and reply templates need native-speaker review. Catalog instructions are
  English only. Bodo, Garo, Khasi, Manipuri, Mizo and Nagamese have no ASR.
- **Server TTS not run here.** Indic Parler-TTS needs PyTorch, parler-tts and gated
  weights; it was not run on this machine.
- **PDFs need an Indic font.** Indic-script names and notes need `SNEHA_REPORT_FONT_PATH`;
  without it, non-Latin characters are replaced.
- **Caregiver observations stay on the server.** They are not synced to phones, so the
  on-phone engine ignores them; the server engine uses them when online.
- **No password reset or email verification.** Clinicians are verified by an operator
  (`scripts/manage.py`).
- **Rate limiting is per process.** Add proxy limits when running several workers.
- **No data export yet.** The dashboard shows the button disabled with a reason.
