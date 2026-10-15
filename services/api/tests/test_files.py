from app.models.files import StoredFile
from tests.helpers import PNG_BYTES, Api

JPEG_BYTES = b"\xff\xd8\xff\xe0" + b"\x00" * 200
WEBP_BYTES = b"RIFF\x24\x00\x00\x00WEBPVP8 " + b"\x00" * 100


def test_upload_and_download_png(api: Api, settings) -> None:
    owner = api.user()
    pid = api.patient(owner)
    response = api.upload(owner, pid, name="../../etc/passwd.png")
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["content_type"] == "image/png"
    assert body["size_bytes"] == len(PNG_BYTES)

    stored = api.db.get(StoredFile, body["id"])
    path = (settings.media_root / stored.storage_key).resolve()
    assert path.is_relative_to(settings.media_root.resolve())
    assert "passwd" not in stored.storage_key

    download = api.client.get(f"/api/v1/files/{body['id']}/content", headers=owner.headers)
    assert download.status_code == 200
    assert download.content == PNG_BYTES
    assert download.headers["content-type"] == "image/png"
    assert download.headers["cache-control"] == "private, no-store"
    assert download.headers["x-content-type-options"] == "nosniff"


def test_accepts_jpeg_and_webp(api: Api) -> None:
    owner = api.user()
    pid = api.patient(owner)
    assert api.upload(owner, pid, JPEG_BYTES, "a.jpg").json()["content_type"] == "image/jpeg"
    assert api.upload(owner, pid, WEBP_BYTES, "a.webp").json()["content_type"] == "image/webp"


def test_rejects_disguised_and_unsupported_files(api: Api) -> None:
    owner = api.user()
    pid = api.patient(owner)
    for data, name in [
        (b"<script>alert(1)</script>", "evil.png"),
        (b"%PDF-1.7 fake", "doc.pdf"),
        (b"GIF89a" + b"\x00" * 20, "anim.gif"),
        (b"", "empty.png"),
    ]:
        response = api.upload(owner, pid, data, name)
        assert response.status_code == 415, name
        assert response.json()["error"]["code"] == "unsupported_media_type"


def test_rejects_oversized_files_without_storing_them(api: Api, settings) -> None:
    owner = api.user()
    pid = api.patient(owner)
    big = PNG_BYTES + b"\x00" * (settings.max_upload_bytes + 1)
    response = api.upload(owner, pid, big)
    assert response.status_code == 413
    stored = list(settings.media_root.rglob("*")) if settings.media_root.exists() else []
    assert [p for p in stored if p.is_file()] == []


def test_patient_device_sees_only_media_of_approved_memories(api: Api) -> None:
    owner = api.user()
    pid = api.patient(owner)
    device = api.pair_device(owner, pid)
    loose = api.upload(owner, pid).json()["id"]
    attached = api.upload(owner, pid).json()["id"]
    api.memory(owner, pid, media_file_id=attached)

    assert (
        api.client.get(f"/api/v1/files/{attached}/content", headers=device.headers).status_code
        == 200
    )
    assert (
        api.client.get(f"/api/v1/files/{loose}/content", headers=device.headers).status_code == 404
    )


def test_missing_file_on_disk_is_410(api: Api, settings) -> None:
    owner = api.user()
    pid = api.patient(owner)
    file_id = api.upload(owner, pid).json()["id"]
    stored = api.db.get(StoredFile, file_id)
    (settings.media_root / stored.storage_key).unlink()
    response = api.client.get(f"/api/v1/files/{file_id}/content", headers=owner.headers)
    assert response.status_code == 410
