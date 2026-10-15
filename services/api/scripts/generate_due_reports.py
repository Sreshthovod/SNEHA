"""Generate automatic 8–9 day reports for every patient who is due one.

Run daily from cron or a scheduler (from services/api):
  uv run python scripts/generate_due_reports.py            # generate
  uv run python scripts/generate_due_reports.py --dry-run  # only list who is due
  uv run python scripts/generate_due_reports.py --days 9

A patient is due when their latest (non-failed) report ended before the start of the
last N complete days, they have data-processing consent and at least one activity.
Safe to run repeatedly: a covered period is never generated twice.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings  # noqa: E402
from app.db.session import get_sessionmaker  # noqa: E402
from app.reports.service import generate_due_reports  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--days", type=int, choices=(8, 9), default=8)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    with get_sessionmaker()() as db:
        outcomes = generate_due_reports(
            db, get_settings(), period_days=args.days, dry_run=args.dry_run
        )
    failed = 0
    for o in outcomes:
        period = f" {o.period[0]}..{o.period[1]}" if o.period else ""
        print(
            f"{o.action:15} patient={o.patient_id}{period} {o.reason}"
            + (f" report={o.report_id}" if o.report_id else "")
        )
        failed += o.action == "failed"
    print(
        f"{sum(o.action == 'generated' for o in outcomes)} generated, {failed} failed, "
        f"{sum(o.action == 'skipped' for o in outcomes)} skipped"
    )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
