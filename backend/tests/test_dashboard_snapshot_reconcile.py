from __future__ import annotations

from uuid import uuid4

from lumonox_backend.realtime.dashboard_snapshot_reconcile import reconcile_project_snapshot
from lumonox_backend.realtime.dashboard_snapshot_store import DashboardSnapshotStore


def test_reconcile_rebuilds_when_snapshot_missing() -> None:
    store = DashboardSnapshotStore(max_projects=4, ttl_seconds=300)
    project_id = uuid4()

    result = reconcile_project_snapshot(
        project_id=project_id,
        canonical_version=7,
        max_drift_versions=10,
        store=store,
    )

    snapshot = store.get(project_id)
    assert result.action == "rebuilt"
    assert result.drift_versions == 7
    assert snapshot is not None
    assert snapshot.snapshot_version == 7


def test_reconcile_repairs_drift_and_marks_partial() -> None:
    store = DashboardSnapshotStore(max_projects=4, ttl_seconds=300)
    project_id = uuid4()
    store.upsert(project_id=project_id, snapshot_version=3, updated_slices=("overview",))

    result = reconcile_project_snapshot(
        project_id=project_id,
        canonical_version=9,
        max_drift_versions=5,
        store=store,
    )

    snapshot = store.get(project_id)
    assert result.action == "drift_repair"
    assert result.drift_versions == 6
    assert snapshot is not None
    assert snapshot.snapshot_version == 9
    assert snapshot.is_partial is True
    assert snapshot.degraded_reason == "reconciled_drift"


def test_reconcile_noop_when_versions_match() -> None:
    store = DashboardSnapshotStore(max_projects=4, ttl_seconds=300)
    project_id = uuid4()
    store.upsert(project_id=project_id, snapshot_version=5, updated_slices=("overview",))

    result = reconcile_project_snapshot(
        project_id=project_id,
        canonical_version=5,
        max_drift_versions=5,
        store=store,
    )

    snapshot = store.get(project_id)
    assert result.action == "noop"
    assert result.drift_versions == 0
    assert snapshot is not None
    assert snapshot.snapshot_version == 5
    assert snapshot.is_partial is False
