#!/usr/bin/env bash
# Repeatable demonstration of the corrected SNEHA workflow (SYNTHETIC data only).
# 1. API: one fictional family through every server-side acceptance criterion.
# 2. Patient app: the phone-only criteria (offline play, in-activity policy, caregiver
#    controls, sync without duplicates) as Flutter tests.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "==> API demonstration (throwaway database)"
(cd "$ROOT/services/api" && uv run python scripts/demo_alignment.py 2>&1 | grep -v -E '^INFO|httpx')

echo
echo "==> Patient app: offline, in-activity adaptation and caregiver controls"
(cd "$ROOT/apps/patient_app" && flutter test --reporter expanded \
  test/adaptation test/offline/offline_guarantee_test.dart)
