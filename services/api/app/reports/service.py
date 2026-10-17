"""Generate report PDFs from persisted data and store them as protected files.

Status lifecycle: pending → generating → ready (file_id set) | failed (error_message).
Generation is synchronous: an 8–9 day PDF takes well under a second, and doing it in
the request keeps failures visible instead of losing them in a background worker.
"""

import logging
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.analytics.compute import METHOD_VERSION
from app.analytics.config import get_analytics_config
from app.analytics.service import observations_in, summarise
from app.core.config import Settings
from app.models.activities import ActivityResult
from app.models.care import Report
from app.models.enums import (
    AuditOutcome,
    ConsentType,
    FilePurpose,
    ObservationCategory,
    RecordSource,
    ReportStatus,
)
from app.models.files import StoredFile
from app.models.patients import PatientProfile
from app.reports.pdf import (
    ObservationLine,
    ReportInput,
    ReviewItemLine,
    TirednessCounts,
    build_pdf,
)
from app.review import service as review
from app.services import audit
from app.services.access import has_consent
from app.services.files import FileStore
from app.services.history import day_bounds

logger = logging.getLogger(__name__)

FAILURE_MESSAGE = "The report could not be generated. Please try again later."


def local_period(report: Report, patient: PatientProfile) -> tuple[date, date]:
    """Inclusive local dates for a report stored as UTC [start, end) bounds."""
    tz = ZoneInfo(patient.timezone)
    start = report.period_start.astimezone(tz).date()
    end = (report.period_end.astimezone(tz) - timedelta(microseconds=1)).date()
    return start, end


def generate(
    db: Session, report: Report, settings: Settings, *, now: datetime | None = None
) -> Report:
    now = now or datetime.now(UTC)
    patient = db.get(PatientProfile, report.patient_id)
    if patient is None:  # pragma: no cover - FK cascade makes this unreachable
        raise ValueError("Report has no patient")
    report.status = ReportStatus.GENERATING
    report.error_message = None
    db.commit()

    store = FileStore(settings.media_root)
    storage_key: str | None = None
    try:
        cfg = get_analytics_config()
        from_date, to_date = local_period(report, patient)
        summary = summarise(db, patient, from_date, to_date, cfg=cfg, now=now)
        lower, upper = day_bounds(patient, from_date, to_date)
        rows = observations_in(db, patient, lower, upper)
        observations = [
            ObservationLine(
                o.observed_at,
                o.category.value,
                o.status.value,
                o.source.value,
                o.note,
                o.fatigue_level.value if o.fatigue_level else None,
            )
            for o in rows
        ]
        # Every prompt in the period becomes (or stays) a review item, so the report shows
        # each one's caregiver decision, or that it is still awaiting one.
        items = [
            ReviewItemLine(
                i.rule_id,
                i.title,
                i.explanation,
                dict(i.numbers),
                i.status.value,
                i.decided_at,
                i.decision_reason,
            )
            for i in review.scan(db, patient, from_date, to_date, actor_id=report.requested_by_id)
        ]
        pdf = build_pdf(
            ReportInput(
                report.id,
                patient.display_name,
                summary,
                observations,
                cfg,
                now,
                review_items=items,
                tiredness=_tiredness(db, patient.id, lower, upper, rows),
            ),
            font_path=settings.report_font_path,
        )
        storage_key, size, sha256 = store.save_bytes(pdf)
        stored = StoredFile(
            patient_id=patient.id,
            uploaded_by_id=report.requested_by_id,
            purpose=FilePurpose.REPORT_PDF,
            content_type="application/pdf",
            size_bytes=size,
            sha256=sha256,
            storage_key=storage_key,
        )
        db.add(stored)
        db.flush()
        report.file_id = stored.id
        report.status = ReportStatus.READY
        report.generated_at = now
        report.method_version = f"{METHOD_VERSION}/{cfg.config_version}"
        audit.record(
            db,
            "report.generate",
            actor_id=report.requested_by_id,
            patient_id=patient.id,
            target_type="report",
            target_id=report.id,
            details={"size_bytes": size},
        )
        db.commit()
    except Exception:
        logger.exception("Report generation failed for report %s", report.id)
        db.rollback()
        if storage_key:
            store.delete(storage_key)
        report = db.get(Report, report.id)
        report.status = ReportStatus.FAILED
        report.error_message = FAILURE_MESSAGE
        audit.record(
            db,
            "report.generate",
            outcome=AuditOutcome.FAILURE,
            patient_id=report.patient_id,
            target_type="report",
            target_id=report.id,
        )
        db.commit()
    return report


def _tiredness(db: Session, patient_id: str, lower, upper, observations) -> TirednessCounts:
    def level_count(source: RecordSource, level: str | None) -> int:
        return sum(
            1
            for o in observations
            if o.category is ObservationCategory.FATIGUE
            and o.source is source
            and (o.fatigue_level.value if o.fatigue_level else None) == level
        )

    patient_button = db.scalar(
        select(func.count())
        .select_from(ActivityResult)
        .where(
            ActivityResult.patient_id == patient_id,
            ActivityResult.fatigue_reported.is_(True),
            ActivityResult.completed_at >= lower,
            ActivityResult.completed_at < upper,
        )
    )
    return TirednessCounts(
        patient_button=patient_button or 0,
        caregiver_phone_mild=level_count(RecordSource.DEVICE, "mild"),
        caregiver_phone_severe=level_count(RecordSource.DEVICE, "severe"),
        dashboard_mild=level_count(RecordSource.DASHBOARD, "mild"),
        dashboard_severe=level_count(RecordSource.DASHBOARD, "severe"),
        dashboard_no_level=level_count(RecordSource.DASHBOARD, None),
    )


# ---------------------------------------------------------------- automation


@dataclass(frozen=True)
class DueOutcome:
    patient_id: str
    action: str  # "generated" | "failed" | "skipped" | "would_generate"
    reason: str
    report_id: str | None = None
    period: tuple[date, date] | None = None


def due_period(patient: PatientProfile, now: datetime, period_days: int) -> tuple[date, date]:
    """The last `period_days` complete local days, ending yesterday."""
    today = now.astimezone(ZoneInfo(patient.timezone)).date()
    end = today - timedelta(days=1)
    return end - timedelta(days=period_days - 1), end


def generate_due_reports(
    db: Session,
    settings: Settings,
    *,
    now: datetime | None = None,
    period_days: int = 8,
    dry_run: bool = False,
) -> list[DueOutcome]:
    """Create one automatic report per patient whose latest report ended ≥ `period_days` ago.

    Skips patients without data-processing consent or without any recorded activity.
    """
    if period_days not in (8, 9):
        raise ValueError("period_days must be 8 or 9")
    now = now or datetime.now(UTC)
    outcomes: list[DueOutcome] = []
    for patient in db.scalars(select(PatientProfile).order_by(PatientProfile.id)):
        if not has_consent(db, patient.id, ConsentType.DATA_PROCESSING):
            outcomes.append(DueOutcome(patient.id, "skipped", "no data-processing consent"))
            continue
        if not db.scalar(
            select(func.count())
            .select_from(ActivityResult)
            .where(ActivityResult.patient_id == patient.id)
        ):
            outcomes.append(DueOutcome(patient.id, "skipped", "no recorded activity"))
            continue
        start, end = due_period(patient, now, period_days)
        lower, upper = day_bounds(patient, start, end)
        latest_end = db.scalar(
            select(func.max(Report.period_end)).where(
                Report.patient_id == patient.id, Report.status != ReportStatus.FAILED
            )
        )
        if latest_end is not None and latest_end > lower:
            outcomes.append(
                DueOutcome(patient.id, "skipped", "a recent report already covers this time")
            )
            continue
        if dry_run:
            outcomes.append(DueOutcome(patient.id, "would_generate", "due", period=(start, end)))
            continue
        report = Report(
            patient_id=patient.id,
            period_start=lower,
            period_end=upper,
            status=ReportStatus.PENDING,
            automated=True,
        )
        db.add(report)
        db.commit()
        report = generate(db, report, settings, now=now)
        outcomes.append(
            DueOutcome(
                patient.id,
                "generated" if report.status is ReportStatus.READY else "failed",
                "due",
                report.id,
                (start, end),
            )
        )
    return outcomes
