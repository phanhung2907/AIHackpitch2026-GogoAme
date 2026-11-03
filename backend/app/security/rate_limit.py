"""In-memory rate limiting and per-principal SSE stream connection cap."""

from __future__ import annotations

import math
import time
from collections import deque
from collections.abc import Generator
from contextlib import contextmanager
from threading import Lock

from app.config import get_settings
from app.errors import AppError


class RateLimiter:
    def __init__(self) -> None:
        self._lock = Lock()
        self._buckets: dict[str, deque[float]] = {}
        self._sse_counts: dict[str, int] = {}

    def reset(self) -> None:
        with self._lock:
            self._buckets.clear()
            self._sse_counts.clear()

    def check(self, bucket_key: str, limit: int, window_seconds: float = 60.0) -> None:
        if not get_settings().rate_limit_enabled:
            return
        now = time.monotonic()
        cutoff = now - window_seconds
        with self._lock:
            q = self._buckets.setdefault(bucket_key, deque())
            while q and q[0] <= cutoff:
                q.popleft()
            if len(q) >= limit:
                retry_after = max(1, math.ceil(window_seconds - (now - q[0])))
                raise AppError(
                    status_code=429,
                    code="RATE_LIMITED",
                    message="Bạn thao tác quá nhanh. Vui lòng thử lại sau ít giây.",
                    details={"retry_after_seconds": retry_after},
                    headers={"Retry-After": str(retry_after)},
                )
            q.append(now)

    @contextmanager
    def acquire_sse_slot(self, principal_key: str) -> Generator[None, None, None]:
        max_conns = get_settings().sse_max_connections_per_principal
        with self._lock:
            current = self._sse_counts.get(principal_key, 0)
            if current >= max_conns:
                raise AppError(
                    status_code=429,
                    code="RATE_LIMITED",
                    message="Đã vượt quá số kết nối SSE tối đa cho phiên hiện tại.",
                    details={"max_connections": max_conns},
                    headers={"Retry-After": "5"},
                )
            self._sse_counts[principal_key] = current + 1
        try:
            yield
        finally:
            with self._lock:
                remaining = self._sse_counts.get(principal_key, 1) - 1
                if remaining <= 0:
                    self._sse_counts.pop(principal_key, None)
                else:
                    self._sse_counts[principal_key] = remaining


rate_limiter = RateLimiter()

