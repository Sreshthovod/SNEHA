"""Protected file storage on local disk.

Files are stored under SNEHA_MEDIA_ROOT with random names (never the uploaded name),
their type is detected from content (not the client's Content-Type) and only an
allow-list of image types is accepted for uploads. Bytes are only ever served
through the authorised /files/{id}/content endpoint.
"""

import hashlib
import os
import secrets
from pathlib import Path

from fastapi import UploadFile

from app.core.errors import AppError

ALLOWED_UPLOAD_TYPES = ("image/jpeg", "image/png", "image/webp")
_CHUNK = 64 * 1024


def sniff_content_type(head: bytes) -> str | None:
    if head.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if len(head) >= 12 and head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "image/webp"
    if head.startswith(b"%PDF-"):
        return "application/pdf"
    return None


class FileStore:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    def path_for(self, storage_key: str) -> Path:
        path = (self.root / storage_key).resolve()
        if not path.is_relative_to(self.root):  # defence in depth; keys are server-generated
            raise AppError(400, "invalid_storage_key", "Invalid file reference.")
        return path

    async def save_upload(self, upload: UploadFile, max_bytes: int) -> tuple[str, str, int, str]:
        """Stream an upload to disk. Returns (storage_key, content_type, size, sha256)."""
        head = await upload.read(16)
        content_type = sniff_content_type(head)
        if content_type not in ALLOWED_UPLOAD_TYPES:
            raise AppError(
                415,
                "unsupported_media_type",
                "Only JPEG, PNG or WebP images can be uploaded.",
            )

        name = secrets.token_hex(16)
        storage_key = f"{name[:2]}/{name}"
        final = self.path_for(storage_key)
        final.parent.mkdir(parents=True, exist_ok=True)
        tmp = final.with_suffix(".part")

        digest = hashlib.sha256()
        size = 0
        try:
            with open(tmp, "xb") as out:
                chunk = head
                while chunk:
                    size += len(chunk)
                    if size > max_bytes:
                        raise AppError(
                            413,
                            "file_too_large",
                            f"File exceeds the maximum size of {max_bytes} bytes.",
                        )
                    digest.update(chunk)
                    out.write(chunk)
                    chunk = await upload.read(_CHUNK)
            os.replace(tmp, final)
        finally:
            tmp.unlink(missing_ok=True)

        return storage_key, content_type, size, digest.hexdigest()

    def save_bytes(self, data: bytes) -> tuple[str, int, str]:
        name = secrets.token_hex(16)
        storage_key = f"{name[:2]}/{name}"
        path = self.path_for(storage_key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return storage_key, len(data), hashlib.sha256(data).hexdigest()

    def delete(self, storage_key: str) -> None:
        self.path_for(storage_key).unlink(missing_ok=True)
