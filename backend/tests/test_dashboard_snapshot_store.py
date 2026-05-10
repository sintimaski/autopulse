from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from lumonox_backend.realtime.dashboard_snapshot_store import DashboardSnapshotStore


def test_snapshot_store_monotonic_version_on_upsert() -> None:
    store = DashboardSnapshotStore(max_projects=4, ttl_seconds=300)
    project_id = uuid4()

    first = store.upsert(
        project_id=project_id,
        snapshot_version=2,
        updated_slices=("overview",),
        updated_at=datetime.now(tz=UTC),
    )
    second = store.upsert(
        project_id=project_id,
        snapshot_version=1,
        updated_slices=("requests",),
        updated_at=datetime.now(tz=UTC),
    )

    assert first.snapshot_version == 2
    assert second.snapshot_version == 3


def test_snapshot_store_lru_eviction_keeps_recent_project() -> None:
    store = DashboardSnapshotStore(max_projects=2, ttl_seconds=300)
    a = uuid4()
    b = uuid4()
    c = uuid4()

    store.upsert(project_id=a, snapshot_version=1, updated_slices=())
    store.upsert(project_id=b, snapshot_version=1, updated_slices=())
    assert store.get(a) is not None
    store.upsert(project_id=c, snapshot_version=1, updated_slices=())

    assert store.get(a) is not None
    assert store.get(b) is None
    assert store.get(c) is not None


def test_snapshot_store_ttl_expiry() -> None:
    store = DashboardSnapshotStore(max_projects=2, ttl_seconds=5)
    project_id = uuid4()
    store.upsert(
        project_id=project_id,
        snapshot_version=1,
        updated_slices=(),
        updated_at=datetime.now(tz=UTC) - timedelta(seconds=6),
    )

    assert store.get(project_id) is None
