from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from threading import Lock
from uuid import UUID


@dataclass(frozen=True, slots=True)
class ProjectDashboardSnapshot:
    project_id: UUID
    snapshot_version: int
    updated_at: datetime
    updated_slices: tuple[str, ...]
    is_partial: bool = False
    degraded_reason: str | None = None
    window_policy: dict[str, object] | None = None


class DashboardSnapshotStore:
    """Per-project in-memory dashboard snapshot metadata (single-node).

    The first rollout keeps only versioned metadata so WS clients can coordinate
    resumable snapshot/delta delivery while `/dashboard/query` remains the source
    of truth for full slice payloads.
    """

    def __init__(self, *, max_projects: int, ttl_seconds: int) -> None:
        self._max_projects = max(1, int(max_projects))
        self._ttl = timedelta(seconds=max(5, int(ttl_seconds)))
        self._lock = Lock()
        self._items: OrderedDict[str, ProjectDashboardSnapshot] = OrderedDict()

    def _key(self, project_id: UUID) -> str:
        return str(project_id)

    def _evict_expired_locked(self, now: datetime) -> None:
        expired: list[str] = []
        for key, snapshot in self._items.items():
            if snapshot.updated_at + self._ttl <= now:
                expired.append(key)
        for key in expired:
            self._items.pop(key, None)

    def get(self, project_id: UUID) -> ProjectDashboardSnapshot | None:
        now = datetime.now(tz=UTC)
        key = self._key(project_id)
        with self._lock:
            self._evict_expired_locked(now)
            snapshot = self._items.get(key)
            if snapshot is None:
                return None
            self._items.move_to_end(key)
            return snapshot

    def upsert(
        self,
        *,
        project_id: UUID,
        snapshot_version: int,
        updated_slices: tuple[str, ...],
        updated_at: datetime | None = None,
        is_partial: bool = False,
        degraded_reason: str | None = None,
        window_policy: dict[str, object] | None = None,
    ) -> ProjectDashboardSnapshot:
        at = (updated_at or datetime.now(tz=UTC)).astimezone(UTC)
        key = self._key(project_id)
        with self._lock:
            existing = self._items.get(key)
            next_version = int(snapshot_version)
            if existing is not None and next_version <= existing.snapshot_version:
                next_version = existing.snapshot_version + 1
            snapshot = ProjectDashboardSnapshot(
                project_id=project_id,
                snapshot_version=next_version,
                updated_at=at,
                updated_slices=tuple(updated_slices),
                is_partial=bool(is_partial),
                degraded_reason=degraded_reason,
                window_policy=window_policy,
            )
            self._items[key] = snapshot
            self._items.move_to_end(key)
            self._evict_expired_locked(at)
            while len(self._items) > self._max_projects:
                self._items.popitem(last=False)
            return snapshot


def _read_int_env(name: str, default: int, *, minimum: int, maximum: int) -> int:
    from os import getenv

    raw = getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = int(raw.strip())
    except ValueError:
        return default
    return max(minimum, min(maximum, value))


dashboard_snapshot_store = DashboardSnapshotStore(
    max_projects=_read_int_env(
        "LUMONOX_DASHBOARD_REALTIME_SNAPSHOT_MAX_PROJECTS",
        512,
        minimum=16,
        maximum=50_000,
    ),
    ttl_seconds=_read_int_env(
        "LUMONOX_DASHBOARD_REALTIME_SNAPSHOT_TTL_SECONDS",
        900,
        minimum=5,
        maximum=86_400,
    ),
)
