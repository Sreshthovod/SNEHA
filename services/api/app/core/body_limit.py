"""Reject oversized request bodies before they are read into memory.

Checks Content-Length up front and also counts streamed bytes, so chunked
requests without a Content-Length are limited too.
"""

import json

from starlette.exceptions import HTTPException
from starlette.types import ASGIApp, Message, Receive, Scope, Send


def _message(limit: int) -> str:
    return f"Request body exceeds the limit of {limit} bytes."


class BodySizeLimitMiddleware:
    def __init__(
        self, app: ASGIApp, *, default_limit: int, upload_limit: int, upload_paths: tuple[str, ...]
    ) -> None:
        self.app = app
        self.default_limit = default_limit
        self.upload_limit = upload_limit
        self.upload_paths = upload_paths

    def _limit_for(self, path: str) -> int:
        is_upload = any(path.endswith(suffix) for suffix in self.upload_paths)
        # Multipart framing adds a little overhead on top of the file itself.
        return self.upload_limit + 64 * 1024 if is_upload else self.default_limit

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        limit = self._limit_for(scope["path"])
        headers = dict(scope.get("headers") or [])
        declared = headers.get(b"content-length")
        if declared is not None:
            try:
                too_large = int(declared) > limit
            except ValueError:
                too_large = True
            if too_large:
                await self._reject(send, limit)
                return

        received = 0

        async def limited_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > limit:
                    # FastAPI re-raises Starlette HTTPExceptions from body reading,
                    # so this reaches the normal error envelope handler.
                    raise HTTPException(413, _message(limit))
            return message

        await self.app(scope, limited_receive, send)

    @staticmethod
    async def _reject(send: Send, limit: int) -> None:
        body = json.dumps(
            {
                "error": {
                    "code": "content_too_large",
                    "message": _message(limit),
                }
            }
        ).encode()
        await send(
            {
                "type": "http.response.start",
                "status": 413,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode()),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})
