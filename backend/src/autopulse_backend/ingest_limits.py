from __future__ import annotations

from collections import deque
from threading import Lock
from time import monotonic


class IngestRateLimiter:
    def __init__(self) -> None:
        self._lock = Lock()
        self._timestamps: deque[float] = deque()
        self._max_requests = 0
        self._window_seconds = 0

    def allow(self, *, max_requests: int, window_seconds: int) -> bool:
        if max_requests <= 0:
            return True

        now = monotonic()
        cutoff = now - float(window_seconds)

        with self._lock:
            if self._max_requests != max_requests or self._window_seconds != window_seconds:
                self._timestamps.clear()
                self._max_requests = max_requests
                self._window_seconds = window_seconds

            while self._timestamps and self._timestamps[0] < cutoff:
                self._timestamps.popleft()

            if len(self._timestamps) >= max_requests:
                return False

            self._timestamps.append(now)
            return True


ingest_rate_limiter = IngestRateLimiter()
