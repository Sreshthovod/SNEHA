"""The committed OpenAPI contract must match what the code serves.

If this fails, run `uv run python scripts/export_openapi.py` and commit the result.
"""

import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).parents[1] / "scripts" / "export_openapi.py"


def _load_exporter():
    spec = importlib.util.spec_from_file_location("export_openapi", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_committed_openapi_contract_is_current() -> None:
    exporter = _load_exporter()
    assert exporter.CONTRACT_PATH.exists(), "Run scripts/export_openapi.py to create the contract"
    assert exporter.CONTRACT_PATH.read_text() == exporter.render(), (
        "packages/api_contracts/openapi.json is stale; run "
        "`uv run python scripts/export_openapi.py`"
    )


def test_contract_exposes_health_endpoints() -> None:
    import json

    paths = json.loads(_load_exporter().render())["paths"]
    assert "/api/v1/health" in paths
    assert "/api/v1/health/ready" in paths
