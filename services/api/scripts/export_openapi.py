"""Write the OpenAPI document to packages/api_contracts/openapi.json.

Usage (from services/api): uv run python scripts/export_openapi.py [--check]
With --check, exits non-zero if the committed file is out of date.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import Environment, Settings  # noqa: E402
from app.main import create_app  # noqa: E402

CONTRACT_PATH = Path(__file__).resolve().parents[3] / "packages" / "api_contracts" / "openapi.json"


def render() -> str:
    app = create_app(Settings(_env_file=None, environment=Environment.TEST))
    return json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail if the contract is stale")
    args = parser.parse_args()

    rendered = render()
    if args.check:
        current = CONTRACT_PATH.read_text() if CONTRACT_PATH.exists() else ""
        if current != rendered:
            print(f"{CONTRACT_PATH} is out of date. Run: uv run python scripts/export_openapi.py")
            return 1
        print("OpenAPI contract is up to date.")
        return 0

    CONTRACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONTRACT_PATH.write_text(rendered)
    print(f"Wrote {CONTRACT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
