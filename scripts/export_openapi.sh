#!/usr/bin/env bash
# Regenerate packages/api_contracts/openapi.json from the FastAPI app.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/../services/api"
uv run python scripts/export_openapi.py "$@"
