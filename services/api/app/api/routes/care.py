"""Caregiver observations (with review workflow), routine items and reports."""

from typing import Annotated

from fastapi import APIRouter, Query, Request, Response, status
from sqlalchemy import select

from app.api.deps import DbSessionDep, PrincipalDep, SettingsDep, patient_access
from app.core.errors import AppError, conflict, forbidden, not_found
from app.core.time import utc_now
from app.models.care import CaregiverObservation, ObservationRevision, Report, RoutineItem
from app.models.enums import (
    ObservationStatus,
    RecordSource,
    ReportStatus,
    SyncEntity,
    SyncOperation,
    UserRole,
)
from app.reports.service import generate as generate_report
from app.schemas.care import (
    ObservationCorrection,
    ObservationCreate,
    ObservationOut,
    ObservationResolve,
    ObservationReview,
    ObservationRevisionOut,
    ReportOut,
    ReportRequest,
    RoutineCreate,
    RoutineOut,
)
from app.schemas.common import ErrorResponse
from app.services import audit
from app.services.access import PatientAccess, Permission
from app.services.changes import log_change
from app.services.history import day_bounds

router = APIRouter(prefix="/patients/{patient_id}", tags=["care"])

_ERRORS = {
    401: {"model": ErrorResponse},
    403: {"model": ErrorResponse},
    404: {"model": ErrorResponse},
    409: {"model": ErrorResponse},
    422: {"model": ErrorResponse},
}


# ---------- observations ----------


@router.get("/observations", response_model=list[ObservationOut], responses=_ERRORS)
def list_observations(
    db: DbSessionDep,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    status_filter: Annotated[ObservationStatus | None, Query(alias="status")] = None,
    access: PatientAccess = patient_access(Permission.VIEW_OBSERVATIONS),
) -> list[CaregiverObservation]:
    query = select(CaregiverObservation).where(CaregiverObservation.patient_id == access.patient.id)
    if status_filter is not None:
        query = query.where(CaregiverObservation.status == status_filter)
    return list(db.scalars(query.order_by(CaregiverObservation.observed_at.desc()).limit(limit)))


@router.post(
    "/observations",
    response_model=ObservationOut,
    status_code=status.HTTP_201_CREATED,
    responses=_ERRORS,
)
def create_observation(
    body: ObservationCreate,
    principal: PrincipalDep,
    db: DbSessionDep,
    request: Request,
    access: PatientAccess = patient_access(Permission.WRITE_OBSERVATION),
) -> CaregiverObservation:
    obs = CaregiverObservation(
        patient_id=access.patient.id,
        author_id=principal.id,
        source=RecordSource.DEVICE
        if principal.role is UserRole.PATIENT
        else RecordSource.DASHBOARD,
        status=ObservationStatus.OPEN,
        version=1,
        **body.model_dump(),
    )
    db.add(obs)
    db.flush()
    audit.record(
        db,
        "observation.create",
        actor_id=principal.id,
        patient_id=access.patient.id,
        target_type="observation",
        target_id=obs.id,
        request=request,
    )
    db.commit()
    return obs


def _get_observation(db, access: PatientAccess, observation_id: str) -> CaregiverObservation:
    obs = db.get(CaregiverObservation, observation_id)
    if obs is None or obs.patient_id != access.patient.id:
        raise not_found("Observation")
    return obs


def _check_version(obs: CaregiverObservation, expected: int) -> None:
    if obs.version != expected:
        raise conflict(
            "version_conflict",
            f"This observation was changed by someone else (current version {obs.version}). "
            "Reload and try again.",
        )


@router.get("/observations/{observation_id}", response_model=ObservationOut, responses=_ERRORS)
def get_observation(
    observation_id: str,
    db: DbSessionDep,
    access: PatientAccess = patient_access(Permission.VIEW_OBSERVATIONS),
) -> CaregiverObservation:
    return _get_observation(db, access, observation_id)


@router.patch("/observations/{observation_id}", response_model=ObservationOut, responses=_ERRORS)
def correct_observation(
    observation_id: str,
    body: ObservationCorrection,
    principal: PrincipalDep,
    db: DbSessionDep,
    request: Request,
    access: PatientAccess = patient_access(Permission.WRITE_OBSERVATION),
) -> CaregiverObservation:
    """Correct an observation (author or managing caregiver). The old content is kept."""
    obs = _get_observation(db, access, observation_id)
    if obs.author_id != principal.id and not access.can(Permission.REVIEW_OBSERVATION):
        raise forbidden("Only the author or a managing caregiver can correct this observation.")
    _check_version(obs, body.expected_version)
    if obs.status is ObservationStatus.RESOLVED:
        raise conflict("observation_resolved", "Resolved observations cannot be changed.")
    changes = body.model_dump(exclude_unset=True, exclude={"expected_version", "reason"})
    changes = {k: v for k, v in changes.items() if v is not None}
    if not changes:
        raise AppError(422, "validation_error", "Nothing to correct.")
    db.add(
        ObservationRevision(
            observation_id=obs.id,
            patient_id=obs.patient_id,
            version=obs.version,
            observed_at=obs.observed_at,
            category=obs.category,
            note=obs.note,
            corrected_by_id=principal.id,
            correction_reason=body.reason,
        )
    )
    for field, value in changes.items():
        setattr(obs, field, value)
    obs.version += 1
    obs.updated_at = utc_now()
    audit.record(
        db,
        "observation.correct",
        actor_id=principal.id,
        patient_id=access.patient.id,
        target_type="observation",
        target_id=obs.id,
        request=request,
        details={"version": obs.version},
    )
    db.commit()
    return obs


@router.get(
    "/observations/{observation_id}/revisions",
    response_model=list[ObservationRevisionOut],
    responses=_ERRORS,
)
def list_observation_revisions(
    observation_id: str,
    db: DbSessionDep,
    access: PatientAccess = patient_access(Permission.VIEW_OBSERVATIONS),
) -> list[ObservationRevision]:
    obs = _get_observation(db, access, observation_id)
    return list(
        db.scalars(
            select(ObservationRevision)
            .where(ObservationRevision.observation_id == obs.id)
            .order_by(ObservationRevision.version)
        )
    )


@router.post(
    "/observations/{observation_id}/review", response_model=ObservationOut, responses=_ERRORS
)
def review_observation(
    observation_id: str,
    body: ObservationReview,
    principal: PrincipalDep,
    db: DbSessionDep,
    request: Request,
    access: PatientAccess = patient_access(Permission.REVIEW_OBSERVATION),
) -> CaregiverObservation:
    """Mark an open observation as reviewed (managing caregivers)."""
    obs = _get_observation(db, access, observation_id)
    _check_version(obs, body.expected_version)
    if obs.status is not ObservationStatus.OPEN:
        raise conflict("not_open", f"This observation is already {obs.status.value}.")
    now = utc_now()
    obs.status = ObservationStatus.REVIEWED
    obs.reviewed_by_id = principal.id
    obs.reviewed_at = now
    obs.review_note = body.note
    obs.version += 1
    obs.updated_at = now
    audit.record(
        db,
        "observation.review",
        actor_id=principal.id,
        patient_id=access.patient.id,
        target_type="observation",
        target_id=obs.id,
        request=request,
    )
    db.commit()
    return obs


@router.post(
    "/observations/{observation_id}/resolve", response_model=ObservationOut, responses=_ERRORS
)
def resolve_observation(
    observation_id: str,
    body: ObservationResolve,
    principal: PrincipalDep,
    db: DbSessionDep,
    request: Request,
    access: PatientAccess = patient_access(Permission.REVIEW_OBSERVATION),
) -> CaregiverObservation:
    """Resolve an open or reviewed observation with a note (managing caregivers)."""
    obs = _get_observation(db, access, observation_id)
    _check_version(obs, body.expected_version)
    if obs.status is ObservationStatus.RESOLVED:
        raise conflict("already_resolved", "This observation is already resolved.")
    now = utc_now()
    obs.status = ObservationStatus.RESOLVED
    obs.resolved_by_id = principal.id
    obs.resolved_at = now
    obs.resolution_note = body.note
    obs.version += 1
    obs.updated_at = now
    audit.record(
        db,
        "observation.resolve",
        actor_id=principal.id,
        patient_id=access.patient.id,
        target_type="observation",
        target_id=obs.id,
        request=request,
    )
    db.commit()
    return obs


@router.delete(
    "/observations/{observation_id}", status_code=status.HTTP_204_NO_CONTENT, responses=_ERRORS
)
def delete_observation(
    observation_id: str,
    principal: PrincipalDep,
    db: DbSessionDep,
    request: Request,
    access: PatientAccess = patient_access(Permission.WRITE_OBSERVATION),
) -> Response:
    obs = db.get(CaregiverObservation, observation_id)
    if obs is None or obs.patient_id != access.patient.id:
        raise not_found("Observation")
    if obs.author_id != principal.id and not access.can(Permission.MANAGE_PATIENT):
        raise forbidden("Only the author or a managing caregiver can delete this observation.")
    if obs.status is not ObservationStatus.OPEN and not access.can(Permission.MANAGE_PATIENT):
        # Once reviewed, the note and its history belong to the care record.
        raise forbidden("Only a managing caregiver can delete a reviewed observation.")
    db.delete(obs)
    audit.record(
        db,
        "observation.delete",
        actor_id=principal.id,
        patient_id=access.patient.id,
        target_type="observation",
        target_id=observation_id,
        request=request,
    )
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------- routines ----------


@router.get("/routines", response_model=list[RoutineOut], responses=_ERRORS)
def list_routines(
    db: DbSessionDep, access: PatientAccess = patient_access(Permission.VIEW_ROUTINES)
) -> list[RoutineItem]:
    return list(
        db.scalars(
            select(RoutineItem)
            .where(RoutineItem.patient_id == access.patient.id)
            .order_by(RoutineItem.local_time)
        )
    )


@router.post(
    "/routines", response_model=RoutineOut, status_code=status.HTTP_201_CREATED, responses=_ERRORS
)
def create_routine(
    body: RoutineCreate,
    principal: PrincipalDep,
    db: DbSessionDep,
    access: PatientAccess = patient_access(Permission.MANAGE_ROUTINES),
) -> RoutineItem:
    item = RoutineItem(
        patient_id=access.patient.id, created_by_id=principal.id, **body.model_dump()
    )
    db.add(item)
    db.flush()
    log_change(db, SyncEntity.ROUTINE_ITEM, item.id, SyncOperation.UPSERT, access.patient.id)
    db.commit()
    return item


@router.delete("/routines/{routine_id}", status_code=status.HTTP_204_NO_CONTENT, responses=_ERRORS)
def delete_routine(
    routine_id: str,
    db: DbSessionDep,
    access: PatientAccess = patient_access(Permission.MANAGE_ROUTINES),
) -> Response:
    item = db.get(RoutineItem, routine_id)
    if item is None or item.patient_id != access.patient.id:
        raise not_found("Routine")
    log_change(db, SyncEntity.ROUTINE_ITEM, item.id, SyncOperation.DELETE, access.patient.id)
    db.delete(item)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------- reports ----------


@router.get("/reports", response_model=list[ReportOut], responses=_ERRORS)
def list_reports(
    db: DbSessionDep, access: PatientAccess = patient_access(Permission.VIEW_REPORTS)
) -> list[Report]:
    return list(
        db.scalars(
            select(Report)
            .where(Report.patient_id == access.patient.id)
            .order_by(Report.period_end.desc())
        )
    )


@router.post(
    "/reports", response_model=ReportOut, status_code=status.HTTP_201_CREATED, responses=_ERRORS
)
def request_report(
    body: ReportRequest,
    principal: PrincipalDep,
    db: DbSessionDep,
    settings: SettingsDep,
    request: Request,
    access: PatientAccess = patient_access(Permission.REQUEST_REPORT),
) -> Report:
    """Create an 8–9 day report and generate its PDF now.

    The response has status `ready` (download via `/files/{file_id}/content`) or `failed`
    (with `error_message`; retry with `POST /reports/{report_id}/generate`).
    """
    start, end = day_bounds(access.patient, body.period_start, body.period_end)
    report = Report(
        patient_id=access.patient.id,
        period_start=start,
        period_end=end,
        status=ReportStatus.PENDING,
        requested_by_id=principal.id,
    )
    db.add(report)
    db.flush()
    audit.record(
        db,
        "report.request",
        actor_id=principal.id,
        patient_id=access.patient.id,
        target_type="report",
        target_id=report.id,
        request=request,
    )
    db.commit()
    return generate_report(db, report, settings)


@router.post("/reports/{report_id}/generate", response_model=ReportOut, responses=_ERRORS)
def regenerate_report(
    report_id: str,
    db: DbSessionDep,
    settings: SettingsDep,
    access: PatientAccess = patient_access(Permission.REQUEST_REPORT),
) -> Report:
    """Retry generation of a `pending` or `failed` report. Ready reports are never replaced."""
    report = db.get(Report, report_id)
    if report is None or report.patient_id != access.patient.id:
        raise not_found("Report")
    if report.status is ReportStatus.READY:
        raise conflict("report_ready", "This report is already ready to download.")
    if report.status is ReportStatus.GENERATING:
        raise conflict("report_generating", "This report is being generated.")
    return generate_report(db, report, settings)


@router.get("/reports/{report_id}", response_model=ReportOut, responses=_ERRORS)
def get_report(
    report_id: str,
    db: DbSessionDep,
    access: PatientAccess = patient_access(Permission.VIEW_REPORTS),
) -> Report:
    report = db.get(Report, report_id)
    if report is None or report.patient_id != access.patient.id:
        raise not_found("Report")
    return report
