# Deployment

Status: **not yet deployed anywhere.** This is the target topology and the checklist the
configuration already enforces.

## Topology

```
Internet ── TLS proxy (Caddy/nginx/cloud LB) ──┬── API (uvicorn, ≥2 workers) ── PostgreSQL 16+
                                               │        └── persistent volume: SNEHA_MEDIA_ROOT
                                               └── static dashboard (apps/web_dashboard/dist)
Patient app (APK/AAB) ── HTTPS ── API
```

## API

```bash
cd services/api
uv sync --no-dev --frozen
export SNEHA_ENVIRONMENT=production
export SNEHA_DATABASE_URL=postgresql://sneha:…@db:5432/sneha
export SNEHA_SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(48))")   # store in a secret manager
export SNEHA_CORS_ALLOWED_ORIGINS=https://dashboard.example.org
export SNEHA_MEDIA_ROOT=/var/lib/sneha/media
uv run alembic upgrade head            # run once per release, before starting new instances
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2 --proxy-headers --forwarded-allow-ips="<proxy ip>"
```

The app **refuses to start** in `staging`/`production` if the database is SQLite, the
secret is missing or shorter than 32 characters, debug is on, or any CORS origin is `*` or
not `https://`.

Health checks: liveness `GET /api/v1/health`; readiness `GET /api/v1/health/ready`
(database reachable **and** migrations at head, otherwise 503).

Scheduled jobs:

```bash
# Generate 8–9 day reports for every patient who is due (idempotent; exit 1 on any failure)
uv run python scripts/generate_due_reports.py          # e.g. daily at 02:00 Asia/Kolkata
```

Optional AI and speech configuration:

| Variable | Purpose |
|---|---|
| `SNEHA_GEMINI_API_KEY`, `SNEHA_GEMINI_MODEL`, `SNEHA_CONVERSATION_PROVIDER=gemini` | Online conversation understanding (consent-gated) |
| `SNEHA_LOCAL_LLM_BASE_URL`, `SNEHA_LOCAL_LLM_MODEL` | Optional self-hosted model |
| `SNEHA_ASR_MODEL_PATH` | faster-whisper model dir (`scripts/download_models.py asr --size small`) |
| `SNEHA_TTS_MODEL_PATH` | Indic Parler-TTS dir (needs PyTorch + parler-tts) |
| `SNEHA_REPORT_FONT_PATH` | TTF with Indic glyphs (e.g. Noto Sans Bengali/Devanagari) for PDF names and notes |
| `SNEHA_PERSONALIZATION_CONFIG`, `SNEHA_ACTIVITY_SPECS` | Override engine thresholds / activity specs |

Deploy without the speech dependencies using `uv sync --no-group speech` if voice is not
offered.

Operational notes:

- The login and pairing rate limiter is per process. With several workers or replicas,
  also rate-limit `/api/v1/auth/*` at the proxy.
- Set the proxy's body limit ≥ the API limits (1 MiB JSON, 5 MiB uploads plus multipart
  overhead) so the API returns its own 413 envelope.
- Back up PostgreSQL **and** the media volume together; they reference each other.
- Clinician verification and admin creation: `uv run python scripts/manage.py --help`.
- Logs contain request IDs, not request bodies. Keep it that way.

## Dashboard

```bash
cd apps/web_dashboard
VITE_API_BASE_URL=https://api.example.org npm ci && npm run build   # outputs dist/
```

Serve `dist/` as static files with an SPA fallback to `index.html` and headers
`Content-Security-Policy: default-src 'self'; connect-src https://api.example.org`,
`X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`.

## Patient app

Requires the Android SDK (not installed on the machine used to build Stage 0/2).

```bash
cd apps/patient_app
flutter build appbundle --release \
  --dart-define=SNEHA_API_BASE_URL=https://api.example.org \
  --dart-define=SNEHA_ENV=production
```

`SNEHA_ENV=production` refuses non-HTTPS API URLs. Release builds do not allow cleartext
HTTP (only the debug manifest does). Signing keys stay outside the repository.

## Local PostgreSQL for development

Any PostgreSQL 16+ works (`brew install postgresql@16`, Docker `postgres:16`, or a managed
instance). Then:

```bash
export SNEHA_DATABASE_URL=postgresql://user:pass@localhost:5432/sneha
uv run alembic upgrade head
SNEHA_TEST_POSTGRES_URL=postgresql://user:pass@localhost:5432/sneha_test uv run pytest   # whole suite on PostgreSQL
```

The test database's `public` schema is **dropped** before each test, so never point
`SNEHA_TEST_POSTGRES_URL` at a database you care about.
