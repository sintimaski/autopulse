from __future__ import annotations

from collections import deque
from threading import Lock
from time import monotonic
from uuid import UUID

from fastapi import HTTPException, status

from autopulse_backend.core.config import Settings
from autopulse_backend.metrics import service_metrics


class DashboardReadRateLimiter:
    def __init__(self, *, max_keys_tracked: int = 8192) -> None:
        self._lock = Lock()
        self._timestamps_by_key: dict[tuple[UUID, str], deque[float]] = {}
        self._last_seen_by_key: dict[tuple[UUID, str], float] = {}
        self._max_keys_tracked = max_keys_tracked
        self._max_requests = 0
        self._window_seconds = 0

    def allow(
        self, *, project_id: UUID, endpoint: str, max_requests: int, window_seconds: int
    ) -> bool:
        if max_requests <= 0:
            return True
        now = monotonic()
        cutoff = now - float(window_seconds)
        key = (project_id, endpoint)
        with self._lock:
            if self._max_requests != max_requests or self._window_seconds != window_seconds:
                self._timestamps_by_key.clear()
                self._last_seen_by_key.clear()
                self._max_requests = max_requests
                self._window_seconds = window_seconds
            timestamps = self._timestamps_by_key.setdefault(key, deque())
            while timestamps and timestamps[0] < cutoff:
                timestamps.popleft()
            if len(timestamps) >= max_requests:
                return False
            timestamps.append(now)
            self._last_seen_by_key[key] = now
            self._evict_idle_keys(cutoff=cutoff)
            return True

    def _evict_idle_keys(self, *, cutoff: float) -> None:
        stale_keys = [
            key
            for key, last_seen in self._last_seen_by_key.items()
            if last_seen < cutoff and not self._timestamps_by_key.get(key)
        ]
        for key in stale_keys:
            self._timestamps_by_key.pop(key, None)
            self._last_seen_by_key.pop(key, None)
        if len(self._timestamps_by_key) <= self._max_keys_tracked:
            return
        oldest = sorted(self._last_seen_by_key.items(), key=lambda item: item[1])
        overflow = len(self._timestamps_by_key) - self._max_keys_tracked
        for key, _ in oldest[:overflow]:
            self._timestamps_by_key.pop(key, None)
            self._last_seen_by_key.pop(key, None)


dashboard_read_rate_limiter = DashboardReadRateLimiter()


def enforce_dashboard_read_rate_limit(
    *, settings: Settings, project_id: UUID, endpoint: str
) -> None:
    max_requests = settings.dashboard_read_rate_limit_requests_per_window
    window_seconds = settings.dashboard_read_rate_limit_window_seconds
    if max_requests <= 0:
        return
    allowed = dashboard_read_rate_limiter.allow(
        project_id=project_id,
        endpoint=endpoint,
        max_requests=max_requests,
        window_seconds=window_seconds,
    )
    if allowed:
        return
    service_metrics.increment("dashboard.read_rate_limit.rejected")
    service_metrics.increment(f"dashboard.read_rate_limit.rejected.{endpoint}")
    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail=f"Dashboard query rate limit exceeded. Try again in {window_seconds} seconds.",
        headers={"Retry-After": str(window_seconds)},
    )
