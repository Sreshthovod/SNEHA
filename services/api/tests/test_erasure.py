from sqlalchemy import func, select

from app.models.activities import ActivityResult
from app.models.files import StoredFile
from app.models.memories import MemoryItem
from app.models.patients import ConsentRecord, PatientProfile
from app.models.sync import AuditEvent, SyncChange
from app.models.users import User
from tests.helpers import Api, iso, now


def test_erasure_removes_everything_and_signs_out_device(api: Api, settings) -> None:
    owner = api.user()
    pid = api.patient(owner, display_name="Synthetic Erase Me")
    device = api.pair_device(owner, pid)
    file_id = api.upload(owner, pid).json()["id"]
    api.memory(owner, pid, media_file_id=file_id)
    s = api.session(device, pid)
    api.client.post(
        f"/api/v1/patients/{pid}/sessions/{s['id']}/results",
        json=api.result_body(),
        headers=device.headers,
    )
    api.client.post(
        f"/api/v1/patients/{pid}/observations",
        json={"observed_at": iso(now()), "category": "fatigue", "note": "Tired after lunch"},
        headers=owner.headers,
    )
    key = api.db.get(StoredFile, file_id).storage_key

    wrong = api.client.post(
        f"/api/v1/patients/{pid}/erase",
        json={"confirm_display_name": "nope"},
        headers=owner.headers,
    )
    assert wrong.status_code == 409
    ok = api.client.post(
        f"/api/v1/patients/{pid}/erase",
        json={"confirm_display_name": "Synthetic Erase Me"},
        headers=owner.headers,
    )
    assert ok.status_code == 204

    api.db.expire_all()
    for model in (MemoryItem, ActivityResult, StoredFile, ConsentRecord):
        assert (
            api.db.scalar(select(func.count()).select_from(model).where(model.patient_id == pid))
            == 0
        )
    assert api.db.get(PatientProfile, pid) is None
    assert api.db.get(User, device.id) is None
    assert (
        api.db.scalar(
            select(func.count()).select_from(SyncChange).where(SyncChange.patient_id == pid)
        )
        == 0
    )
    assert not (settings.media_root / key).exists()
    assert api.client.get("/api/v1/auth/me", headers=device.headers).status_code == 401
    assert api.client.get(f"/api/v1/patients/{pid}", headers=owner.headers).status_code == 404
    events = api.db.scalars(select(AuditEvent.action).where(AuditEvent.patient_id == pid)).all()
    assert "patient.erase" in events


def test_only_managers_can_erase(api: Api) -> None:
    owner, helper = api.user(), api.user()
    pid = api.patient(owner)
    api.add_caregiver(owner, pid, helper)
    response = api.client.post(
        f"/api/v1/patients/{pid}/erase",
        json={"confirm_display_name": "Synthetic Patient"},
        headers=helper.headers,
    )
    assert response.status_code == 403


def test_patient_device_can_read_but_not_change_consent(api: Api) -> None:
    owner = api.user()
    pid = api.patient(owner)
    device = api.pair_device(owner, pid)
    summary = api.client.get(f"/api/v1/patients/{pid}/consents", headers=device.headers)
    assert summary.status_code == 200
    assert summary.json()["current"]["data_processing"] == "granted"
    change = api.client.post(
        f"/api/v1/patients/{pid}/consents",
        json={"consent_type": "cloud_ai", "status": "granted", "given_by": "patient"},
        headers=device.headers,
    )
    assert change.status_code == 403
