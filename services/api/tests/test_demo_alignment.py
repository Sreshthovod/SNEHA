"""The alignment demonstration (scripts/demo_alignment.py) must keep passing."""

import importlib.util
from pathlib import Path


def test_alignment_demo_passes_every_check(tmp_path: Path) -> None:
    path = Path(__file__).resolve().parents[1] / "scripts" / "demo_alignment.py"
    spec = importlib.util.spec_from_file_location("demo_alignment", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.run(tmp_path) is True
