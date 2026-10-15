#!/usr/bin/env bash
# Start the API locally: install deps, apply migrations, run with auto-reload.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/../services/api"
[ -f .env ] || { cp .env.example .env; echo "Created services/api/.env from .env.example"; }
uv sync
uv run alembic upgrade head
exec uv run uvicorn app.main:app --reload --host "${HOST:-127.0.0.1}" --port "${PORT:-8000}"
