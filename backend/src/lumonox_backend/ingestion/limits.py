from __future__ import annotations

from collections import deque
from threading import Lock
from time import monotonic
from uuid import UUID


class IngestRateLimiter:
    def __init__(self, *, max_projects_tracked: int = 4096) -> None:
        self._lock = Lock()
        self._timestamps_by_project: dict[UUID, deque[float]] = {}
        self._last_seen_by_project: dict[UUID, float] = {}
        self._max_projects_tracked = max_projects_tracked
        self._max_requests = 0
        self._window_seconds = 0

    def allow(self, *, project_id: UUID, max_requests: int, window_seconds: int) -> bool:
        if max_requests <= 0:
            return True

        now = monotonic()
        cutoff = now - float(window_seconds)

        with self._lock:
            if self._max_requests != max_requests or self._window_seconds != window_seconds:
                self._timestamps_by_project.clear()
                self._last_seen_by_project.clear()
                self._max_requests = max_requests
                self._window_seconds = window_seconds

            timestamps = self._timestamps_by_project.setdefault(project_id, deque())
            while timestamps and timestamps[0] < cutoff:
                timestamps.popleft()

            if len(timestamps) >= max_requests:
                return False

            timestamps.append(now)
            self._last_seen_by_project[project_id] = now
            self._evict_idle_projects(now=now, cutoff=cutoff)
            return True

    def _evict_idle_projects(self, *, now: float, cutoff: float) -> None:
        stale_project_ids = [
            project_id
            for project_id, last_seen in self._last_seen_by_project.items()
            if last_seen < cutoff and not self._timestamps_by_project.get(project_id)
        ]
        for project_id in stale_project_ids:
            self._timestamps_by_project.pop(project_id, None)
            self._last_seen_by_project.pop(project_id, None)
        if len(self._timestamps_by_project) <= self._max_projects_tracked:
            return
        oldest_projects = sorted(self._last_seen_by_project.items(), key=lambda item: item[1])
        overflow = len(self._timestamps_by_project) - self._max_projects_tracked
        for project_id, _ in oldest_projects[:overflow]:
            self._timestamps_by_project.pop(project_id, None)
            self._last_seen_by_project.pop(project_id, None)


ingest_rate_limiter = IngestRateLimiter()
