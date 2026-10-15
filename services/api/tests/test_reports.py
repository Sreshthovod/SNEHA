"""PDF report generation, download, failure handling and automation (synthetic data)."""

from datetime import UTC, date, datetime, time

import pytest
from sqlalchemy import select

from app.analytics.config import get_analytics_config
from app.analytics.service import summarise
from app.models.care import Report
from app.models.enums import ReportStatus
from app.models.files import StoredFile
from app.models.patients import PatientProfile
from app.reports import service as report_service
from app.reports.pdf import ObservationLine, ReportInput, build_pdf
from app.reports.service import generate_due_reports
from tests.analytics_fixtures import PERIOD_END, PERIOD_START, R, baseline_rows, days, observe, seed
from tests.helpers import Api

NOW = datetime(2026, 10, 15, 6, 0, tzinfo=UTC)
BODY = {"period_start": str(PERIOD_START), "period_end": str(PERIOD_END)}


@pytest.fixture
def family(api: Api):
    owner = api.user()
    pid = api.patient(owner, display_name="Synthetic Report Patient")
    seed(api.db, pid, baseline_rows())
    seed(api.db, pid, [R(d, score=0.6, rt_ms=3200) for d in days(PERIOD_START, 6)])
    observe(api.db, pid, PERIOD_START.replace(day=22), note="Synthetic: slept badly")
    return owner, pid


def pdf_text(api: Api, pid: str, name: str = "Synthetic Report Patient") -> bytes:
    """Uncompressed PDF so its text can be checked without a PDF parser."""
    api.db.expire_all()
    patient = api.db.get(PatientProfile, pid)
    summary = summarise(api.db, patient, PERIOD_START, PERIOD_END, now=NOW)
    lines = [ObservationLine(NOW, "sleep", "open", "dashboard", "Synthetic: slept badly")]
    return build_pdf(
        ReportInput("report-test", name, summary, lines, get_analytics_config(), NOW),
        compress=False,
    )


def test_request_generates_a_downloadable_pdf(api: Api, family) -> None:
    owner, pid = family
    response = api.client.post(f"/api/v1/patients/{pid}/reports", json=BODY, headers=owner.headers)
    assert response.status_code == 201
    report = response.json()
    assert report["status"] == "ready"
    assert report["generated_at"] and report["file_id"]
    assert report["method_version"].startswith("analytics-")
    assert report["automated"] is False

    download = api.client.get(f"/api/v1/files/{report['file_id']}/content", headers=owner.headers)
    assert download.status_code == 200
    assert download.headers["content-type"] == "application/pdf"
    assert download.content.startswith(b"%PDF-")
    assert download.content.rstrip().endswith(b"%%EOF")
    stored = api.db.get(StoredFile, report["file_id"])
    assert stored.purpose.value == "report_pdf" and stored.size_bytes == len(download.content)


def test_pdf_contains_required_sections(api: Api, family) -> None:
    _, pid = family
    pdf = pdf_text(api, pid)
    assert pdf.startswith(b"%PDF-")
    for text in [
        b"SNEHA activity summary",
        b"Reporting period: 20 Sep 2026",
        b"28 Sep 2026",
        b"Data completeness",
        b"Missing-data warnings",
        b"Summary",
        b"Day by day",
        b"usual pattern",
        b"Review prompts",
        b"ACCURACY_LOWER_THAN_USUAL",
        b"Caregiver observations",
        b"Synthetic: slept badly",
        b"How this summary was made",
        b"not a medical assessment",
    ]:
        assert text in pdf, text
    for banned in [b"dementia", b"decline", b"impairment", b"severity"]:
        assert banned not in pdf.lower()


def test_non_latin_names_do_not_break_generation(api: Api, family) -> None:
    _, pid = family
    pdf = pdf_text(api, pid, name="সংশ্লেষিত রোগী <script>")  # synthetic Assamese-script name
    assert pdf.startswith(b"%PDF-")
    assert b"<script>" not in pdf  # markup is escaped


def test_empty_period_still_produces_honest_report(api: Api) -> None:
    owner = api.user()
    pid = api.patient(owner)
    report = api.client.post(
        f"/api/v1/patients/{pid}/reports", json=BODY, headers=owner.headers
    ).json()
    assert report["status"] == "ready"
    api.db.expire_all()
    summary = summarise(api.db, api.db.get(PatientProfile, pid), PERIOD_START, PERIOD_END, now=NOW)
    pdf = build_pdf(
        ReportInput("r", "Synthetic", summary, [], get_analytics_config(), NOW), compress=False
    )
    assert b"No activity was recorded in this period" in pdf
    assert b"No caregiver observations were recorded" in pdf


def test_failure_is_recorded_and_can_be_retried(api: Api, family, monkeypatch) -> None:
    owner, pid = family

    def broken(*args, **kwargs):
        raise RuntimeError("synthetic renderer failure with private detail")

    monkeypatch.setattr(report_service, "build_pdf", broken)
    failed = api.client.post(f"/api/v1/patients/{pid}/reports", json=BODY, headers=owner.headers)
    assert failed.status_code == 201
    body = failed.json()
    assert body["status"] == "failed"
    assert body["file_id"] is None
    assert body["error_message"] == report_service.FAILURE_MESSAGE
    assert "private detail" not in failed.text
    api.db.expire_all()
    assert api.db.scalars(select(StoredFile).where(StoredFile.purpose == "report_pdf")).all() == []

    monkeypatch.undo()
    retry = api.client.post(
        f"/api/v1/patients/{pid}/reports/{body['id']}/generate", headers=owner.headers
    )
    assert retry.status_code == 200 and retry.json()["status"] == "ready"
    again = api.client.post(
        f"/api/v1/patients/{pid}/reports/{body['id']}/generate", headers=owner.headers
    )
    assert again.status_code == 409 and again.json()["error"]["code"] == "report_ready"


def test_report_access_control(api: Api, family) -> None:
    owner, pid = family
    report = api.client.post(
        f"/api/v1/patients/{pid}/reports", json=BODY, headers=owner.headers
    ).json()
    file_url = f"/api/v1/files/{report['file_id']}/content"

    clinician = api.user("clinician")
    assert api.client.get(file_url, headers=clinician.headers).status_code == 404
    api.grant_clinician(owner, pid, clinician)
    assert api.client.get(file_url, headers=clinician.headers).status_code == 200
    clinician_report = api.client.post(
        f"/api/v1/patients/{pid}/reports", json=BODY, headers=clinician.headers
    )
    assert clinician_report.status_code == 201  # granted clinicians may request reports

    outsider = api.user()
    assert api.client.get(file_url, headers=outsider.headers).status_code == 404
    assert (
        api.client.post(
            f"/api/v1/patients/{pid}/reports", json=BODY, headers=outsider.headers
        ).status_code
        == 404
    )
    device = api.pair_device(owner, pid)
    assert api.client.get(file_url, headers=device.headers).status_code == 403
    assert (
        api.client.post(
            f"/api/v1/patients/{pid}/reports/{report['id']}/generate", headers=outsider.headers
        ).status_code
        == 404
    )


def test_report_audience_may_see_observation_notes() -> None:
    """Reports print caregiver notes, so everyone who can view reports must also be allowed
    to view observations; otherwise the PDF would leak notes."""
    from app.services import access

    for perms in (
        access._CAREGIVER_PERMISSIONS,
        access._CLINICIAN_PERMISSIONS,
        access._PATIENT_PERMISSIONS,
    ):
        if access.Permission.VIEW_REPORTS in perms:
            assert access.Permission.VIEW_OBSERVATIONS in perms


# ---------------------------------------------------------------- automation


def test_due_reports_are_generated_once(api: Api, settings, monkeypatch) -> None:
    owner = api.user()
    due = api.patient(owner, display_name="Synthetic Due")
    no_consent = api.patient(owner, consent=False)
    unused = api.patient(owner)
    seed(api.db, due, [R(d) for d in days(date(2026, 10, 7), 7)])
    seed(api.db, no_consent, [R(date(2026, 10, 8))])

    dry = generate_due_reports(api.db, settings, now=NOW, dry_run=True)
    by_patient = {o.patient_id: o for o in dry}
    assert by_patient[due].action == "would_generate"
    assert by_patient[due].period == (date(2026, 10, 7), date(2026, 10, 14))  # last 8 full days
    assert by_patient[no_consent].reason == "no data-processing consent"
    assert by_patient[unused].reason == "no recorded activity"
    assert api.db.scalars(select(Report)).all() == []

    first = {o.patient_id: o for o in generate_due_reports(api.db, settings, now=NOW)}
    assert first[due].action == "generated"
    api.db.expire_all()
    report = api.db.get(Report, first[due].report_id)
    assert (
        report.status is ReportStatus.READY and report.automated and report.requested_by_id is None
    )

    second = {o.patient_id: o for o in generate_due_reports(api.db, settings, now=NOW)}
    assert second[due].action == "skipped"

    later = datetime(2026, 10, 23, 6, 0, tzinfo=UTC)  # 8 days later → due again
    third = {o.patient_id: o for o in generate_due_reports(api.db, settings, now=later)}
    assert third[due].action == "generated"
    assert third[due].period == (date(2026, 10, 15), date(2026, 10, 22))


def test_due_reports_script_entry_point(api: Api, settings, monkeypatch, capsys) -> None:
    import importlib.util
    from pathlib import Path

    from sqlalchemy.orm import sessionmaker

    owner = api.user()
    pid = api.patient(owner)
    seed(api.db, pid, [R(date(2026, 10, 10), at=time(9))])
    spec = importlib.util.spec_from_file_location(
        "generate_due_reports", Path(__file__).parents[1] / "scripts" / "generate_due_reports.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "get_sessionmaker", lambda: sessionmaker(bind=api.db.get_bind()))
    monkeypatch.setattr(module, "get_settings", lambda: settings)

    assert module.main(["--dry-run"]) == 0
    assert "would_generate" in capsys.readouterr().out
    assert module.main([]) == 0
    assert "1 generated, 0 failed" in capsys.readouterr().out


def test_due_reports_reject_bad_period(api: Api, settings) -> None:
    with pytest.raises(ValueError):
        generate_due_reports(api.db, settings, period_days=7)
