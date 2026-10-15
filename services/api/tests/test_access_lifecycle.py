"""Access must end completely when it is taken away: grants, devices, codes and photos."""

from datetime import timedelta
from pathlib import Path

from sqlalchemy import select

from app.core.time import utc_now
from app.models.files import StoredFile
from app.models.patients import ClinicianAccessGrant, DevicePairingCode
from tests.helpers import Api, iso, now


def base(pid: str) -> str:
    return f"/api/v1/patients/{pid}"


# ---------- clinician grants ----------


def test_withdrawing_sharing_revokes_grants_for_good(api: Api) -> None:
    owner, clinician = api.user(), api.user("clinician")
    pid = api.patient(owner)
    grant = api.grant_clinician(owner, pid, clinician)
    assert api.client.get(base(pid), headers=clinician.headers).status_code == 200

    api.consent(owner, pid, "clinician_sharing", "withdrawn")
    assert api.db.get(ClinicianAccessGrant, grant["id"]).revoked_at is not None

    # Granting sharing again (e.g. for a different clinician) must not restore old grants.
    api.consent(owner, pid, "clinician_sharing", "granted")
    assert api.client.get(base(pid), headers=clinician.headers).status_code == 404


# ---------- devices and pairing codes ----------


def test_removing_a_caregiver_signs_out_the_phone_they_paired(api: Api) -> None:
    owner, manager = api.user(), api.user()
    pid = api.patient(owner)
    rel = api.add_caregiver(owner, pid, manager, can_manage=True)
    their_phone = api.pair_device(manager, pid)
    owner_phone = api.pair_device(owner, pid)
    unused = api.client.post(f"{base(pid)}/pairing-codes", headers=manager.headers).json()

    removed = api.client.delete(f"{base(pid)}/caregivers/{rel['id']}", headers=owner.headers)
    assert removed.status_code == 204

    assert api.client.get(base(pid), headers=their_phone.headers).status_code == 401
    assert api.client.get(base(pid), headers=owner_phone.headers).status_code == 200
    pair = api.client.post(
        "/api/v1/auth/device/pair", json={"code": unused["code"], "device_name": "Old phone"}
    )
    assert pair.status_code == 401


def test_revoking_devices_also_cancels_unused_codes(api: Api) -> None:
    owner = api.user()
    pid = api.patient(owner)
    code = api.client.post(f"{base(pid)}/pairing-codes", headers=owner.headers).json()
    assert api.client.post(f"{base(pid)}/devices/revoke", headers=owner.headers).status_code == 204
    pair = api.client.post(
        "/api/v1/auth/device/pair", json={"code": code["code"], "device_name": "Lost phone"}
    )
    assert pair.status_code == 401


def test_a_pairing_code_is_claimed_atomically(api: Api) -> None:
    # The conditional UPDATE is what makes this safe under concurrency; here we check
    # that a code whose used_at was set by another request is refused.
    owner = api.user()
    pid = api.patient(owner)
    code = api.client.post(f"{base(pid)}/pairing-codes", headers=owner.headers).json()
    row = api.db.scalar(select(DevicePairingCode).where(DevicePairingCode.patient_id == pid))
    row.used_at = utc_now()
    api.db.commit()
    pair = api.client.post(
        "/api/v1/auth/device/pair", json={"code": code["code"], "device_name": "Second phone"}
    )
    assert pair.status_code == 401


# ---------- consent and content ----------


def test_photo_upload_requires_data_processing_consent(api: Api) -> None:
    owner = api.user()
    pid = api.patient(owner, consent=False)
    response = api.upload(owner, pid)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "consent_required"


def test_replaced_photo_is_erased(api: Api, settings) -> None:
    owner = api.user()
    pid = api.patient(owner)
    first = api.upload(owner, pid).json()["id"]
    second = api.upload(owner, pid).json()["id"]
    memory = api.memory(owner, pid, media_file_id=first)
    old_path = Path(settings.media_root) / api.db.get(StoredFile, first).storage_key
    assert old_path.exists()

    response = api.client.patch(
        f"{base(pid)}/memories/{memory['id']}",
        json={"expected_version": 1, "media_file_id": second},
        headers=owner.headers,
    )
    assert response.status_code == 200
    api.db.expire_all()
    assert api.db.get(StoredFile, first).deleted_at is not None
    assert not old_path.exists()
    assert (
        api.client.get(f"/api/v1/files/{first}/content", headers=owner.headers).status_code == 404
    )


def test_one_photo_cannot_belong_to_two_memories(api: Api) -> None:
    owner = api.user()
    pid = api.patient(owner)
    photo = api.upload(owner, pid).json()["id"]
    api.memory(owner, pid, media_file_id=photo)
    response = api.client.post(
        f"{base(pid)}/memories",
        json={"kind": "place", "title": "Synthetic house", "media_file_id": photo},
        headers=owner.headers,
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_media"


def test_helper_cannot_delete_a_reviewed_observation(api: Api) -> None:
    owner, helper = api.user(), api.user()
    pid = api.patient(owner)
    api.add_caregiver(owner, pid, helper)
    obs = api.client.post(
        f"{base(pid)}/observations",
        json={"observed_at": iso(now()), "category": "mood", "note": "Synthetic calm day"},
        headers=helper.headers,
    ).json()
    url = f"{base(pid)}/observations/{obs['id']}"
    reviewed = api.client.post(f"{url}/review", json={"expected_version": 1}, headers=owner.headers)
    assert reviewed.status_code == 200

    assert api.client.delete(url, headers=helper.headers).status_code == 403
    assert api.client.get(url, headers=owner.headers).status_code == 200
    # A managing caregiver can still delete it (data correction / erasure requests).
    assert api.client.delete(url, headers=owner.headers).status_code == 204


def test_sync_never_sends_links_between_unapproved_memories(api: Api) -> None:
    owner, helper = api.user(), api.user()
    pid = api.patient(owner)
    api.add_caregiver(owner, pid, helper)
    device = api.pair_device(owner, pid)
    approved = api.memory(owner, pid, title="Synthetic house")
    pending = api.memory(helper, pid, title="Synthetic wedding")
    assert pending["status"] == "pending_approval"
    link = api.client.post(
        f"{base(pid)}/memory-relationships",
        json={
            "from_memory_id": pending["id"],
            "to_memory_id": approved["id"],
            "relation_type": "located_at",
        },
        headers=owner.headers,
    ).json()

    def link_change(since: int = 0) -> dict | None:
        body = api.client.get(f"/api/v1/sync/pull?since={since}", headers=device.headers).json()
        changes = [c for c in body["changes"] if c["entity_id"] == link["id"]]
        return changes[-1] if changes else None

    hidden = link_change()
    assert hidden is None or hidden["data"] is None

    approve = api.client.post(
        f"{base(pid)}/memories/{pending['id']}/approve",
        json={"expected_version": 1},
        headers=owner.headers,
    )
    assert approve.status_code == 200
    visible = link_change()
    assert visible is not None and visible["operation"] == "upsert"
    assert visible["data"]["relation_type"] == "located_at"


def test_grant_dates_still_validated(api: Api) -> None:
    # Regression guard for the grant code touched by revocation-on-withdrawal.
    owner, clinician = api.user(), api.user("clinician")
    pid = api.patient(owner)
    api.consent(owner, pid, "clinician_sharing", "granted")
    response = api.client.post(
        f"{base(pid)}/clinician-grants",
        json={
            "clinician_email": clinician.email,
            "expires_at": iso(now() - timedelta(days=1)),
            "purpose": "Synthetic review",
        },
        headers=owner.headers,
    )
    assert response.status_code == 422
