# SNEHA

An assistive cognitive-activity and memory-support platform for older adults experiencing
dementia-related difficulties, designed for India's North Eastern Region. **SNEHA is not a
diagnostic system.**

| Part | Path | Stack |
|---|---|---|
| Patient app (Android-first) | `apps/patient_app` | Flutter 3.41 / Dart 3.11, sqflite, http, flutter_secure_storage, flutter_tts, record |
| Caregiver and clinician dashboard | `apps/web_dashboard` | React 19, TypeScript 6, Vite 8, React Router 7, Vitest 5 |
| Backend API | `services/api` | Python 3.12, FastAPI 0.143, Pydantic 2.14, SQLAlchemy 2.1, Alembic 1.20, argon2-cffi, psycopg 3, pandas 3, NumPy 2.5, ReportLab 5, google-genai 2.31, faster-whisper 1.2 |
| API contract | `packages/api_contracts/openapi.json` | Generated from the API |
| Docs | `docs/`, `packages/shared_docs/` | Architecture, offline/sync, privacy, AI, deployment, roadmap |

**Status:** Stages 0–8 are implemented: patient app, dashboard, API, personalization,
conversation, speech, analytics, PDF reports, and a security/testing audit. **Not
production-ready.** See [docs/stage8-validation-report.md](docs/stage8-validation-report.md)
for test results, open findings and unverified requirements, plus
[docs/feature-matrix.md](docs/feature-matrix.md) and
[docs/implementation-roadmap.md](docs/implementation-roadmap.md).

## Prerequisites

| Tool | Version used | Install |
|---|---|---|
| uv | 0.11+ | `brew install uv` (fetches Python 3.12 automatically) |
| Node.js | 20.19+ (tested on 26) | `brew install node` |
| Flutter | 3.41 stable | <https://docs.flutter.dev/get-started/install> |
| Android SDK | for device and APK builds only | Android Studio, then `flutter doctor --android-licenses` |
| PostgreSQL | 16+, optional locally | `brew install postgresql@16` or Docker `postgres:16` |

## Backend API

```bash
cd services/api
uv sync                                  # creates .venv with locked dependencies
cp .env.example .env                     # local config; defaults to SQLite ./sneha_dev.db
uv run alembic upgrade head              # create schema + seed activity catalog
uv run uvicorn app.main:app --reload     # http://localhost:8000/docs
```

Or run `./scripts/dev_api.sh` to do all of the above.

```bash
uv run pytest                            # 325 tests on SQLite (PostgreSQL-only and live-Gemini tests skip)
SNEHA_TEST_POSTGRES_URL=postgresql://u:p@localhost:5432/sneha_test uv run pytest   # same suite on PostgreSQL (drops that DB's schema!)
uv run ruff check . && uv run ruff format --check .
uv run python scripts/export_openapi.py  # after any API change; commit the result
uv run python scripts/manage.py verify-clinician <email>
uv run python scripts/generate_due_reports.py --dry-run           # automated 8–9 day reports
uv run python scripts/download_models.py asr --size small         # optional speech model (explicit)
```

Optional AI: set `SNEHA_GEMINI_API_KEY` (used only with the patient's cloud-AI consent) and
`SNEHA_ASR_MODEL_PATH`. Without them everything still works using the deterministic
engines and touch input. See [docs/ai-models.md](docs/ai-models.md).

Check it: `curl localhost:8000/api/v1/health` and `curl localhost:8000/api/v1/health/ready`.

## Web dashboard

```bash
cd apps/web_dashboard
cp .env.example .env.local               # VITE_API_BASE_URL=http://localhost:8000
npm ci
npm run dev                              # http://localhost:5173
npm test                                 # Vitest + Testing Library
npm run lint && npm run build            # oxlint, tsc, production build
```

## Patient app

```bash
cd apps/patient_app
flutter pub get
flutter analyze && flutter test
flutter run --dart-define=SNEHA_API_BASE_URL=http://10.0.2.2:8000   # Android emulator → host API
```

On a physical phone, use your computer's LAN IP (e.g. `http://192.168.1.20:8000`) and start
the API with `--host 0.0.0.0`.

## Everything at once

```bash
./scripts/test_all.sh
```

## Rules for contributors

- Secrets only in environment variables or git-ignored `.env` files. Never in code.
- Synthetic data only: no real patient information anywhere in the repository.
- Timezone-aware timestamps only; UUID record IDs.
- An API change requires regenerating `packages/api_contracts/openapi.json`; a test enforces it.
- Model weights are never committed or downloaded at startup.
