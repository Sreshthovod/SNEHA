"""Small in-process sliding-window rate limiter for credential endpoints.

This is per-process. With several API replicas, put a shared limiter (reverse proxy
or Redis) in front as well; see docs/deployment.md. Account lockout in the auth
service is the second, database-backed layer.
"""

import threading
import time
from collections import defaultdict, deque

from fastapi import Request

from app.core.errors import AppError

_MAX_KEYS = 10_000


class RateLimiter:
    def __init__(self, limit: int, window_seconds: float) -> None:
        self.limit = limit
        self.window = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str) -> None:
        now = time.monotonic()
        with self._lock:
            hits = self._hits[key]
            while hits and now - hits[0] > self.window:
                hits.popleft()
            if len(hits) >= self.limit:
                retry_after = max(1, int(self.window - (now - hits[0])))
                raise AppError(
                    429,
                    "rate_limited",
                    "Too many attempts. Please wait and try again.",
                    headers={"Retry-After": str(retry_after)},
                )
            hits.append(now)
            if len(self._hits) > _MAX_KEYS:
                self._evict_stale(now)

    def _evict_stale(self, now: float) -> None:
        # Bound memory when many different clients pass through (e.g. IPv6 scans).
        stale = [k for k, h in self._hits.items() if not h or now - h[-1] > self.window]
        for key in stale:
            del self._hits[key]

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


def client_key(request: Request) -> str:
    return request.client.host if request.client else "unknown"


login_limiter = RateLimiter(limit=10, window_seconds=60)
pairing_limiter = RateLimiter(limit=10, window_seconds=60)
