#!/usr/bin/env bash
# Run every test suite and linter in the monorepo. Exits non-zero on the first failure.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "==> API (pytest, ruff, contract check)"
(cd "$ROOT/services/api" && uv sync --quiet && uv run ruff check . && uv run ruff format --check . \
  && uv run pytest -q && uv run python scripts/export_openapi.py --check)

echo "==> Web dashboard (API types, vitest, typecheck, lint, build)"
(cd "$ROOT/apps/web_dashboard" && npm ci --silent && npm run check:api && npm test && npm run lint && npm run build)

echo "==> Patient app (flutter analyze, flutter test)"
(cd "$ROOT/apps/patient_app" && flutter pub get >/dev/null && flutter analyze && flutter test)

echo "All checks passed."
