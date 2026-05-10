from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from lumonox_backend.dashboard.routes.query_bundle import get_project_dashboard_version
from lumonox_backend.metrics import service_metrics
from lumonox_backend.realtime import project_websocket_hub
from lumonox_backend.realtime.dashboard_snapshot_store import (
    DashboardSnapshotStore,
    dashboard_snapshot_store,
)


@dataclass(frozen=True, slots=True)
class SnapshotReconcileResult:
    action: str
    drift_versions: int


def reconcile_project_snapshot(
    *,
    project_id: UUID,
    canonical_version: int,
    max_drift_versions: int,
    store: DashboardSnapshotStore | None = None,
) -> SnapshotReconcileResult:
    target_store = store or dashboard_snapshot_store
    snapshot = target_store.get(project_id)
    if snapshot is None:
        target_store.upsert(
            project_id=project_id,
            snapshot_version=max(0, int(canonical_version)),
            updated_slices=(),
            updated_at=datetime.now(tz=UTC),
            is_partial=False,
            degraded_reason=None,
        )
        service_metrics.increment("dashboard.realtime.snapshot.rebuild_total")
        return SnapshotReconcileResult(
            action="rebuilt", drift_versions=max(0, int(canonical_version))
        )

    drift = max(0, int(canonical_version) - int(snapshot.snapshot_version))
    if drift == 0:
        return SnapshotReconcileResult(action="noop", drift_versions=0)

    service_metrics.increment("dashboard.realtime.snapshot.drift_detected_total")
    if drift >= max(1, int(max_drift_versions)):
        service_metrics.increment("dashboard.realtime.snapshot.rebuild_total")
    target_store.upsert(
        project_id=project_id,
        snapshot_version=int(canonical_version),
        updated_slices=snapshot.updated_slices,
        updated_at=datetime.now(tz=UTC),
        is_partial=True,
        degraded_reason="reconciled_drift",
        window_policy=snapshot.window_policy,
    )
    service_metrics.increment("dashboard.realtime.snapshot.drift_repaired_total")
    return SnapshotReconcileResult(action="drift_repair", drift_versions=drift)


async def run_dashboard_snapshot_reconcile_loop(
    *,
    interval_seconds: float,
    max_drift_versions: int,
) -> None:
    if interval_seconds <= 0:
        return
    while True:
        await asyncio.sleep(interval_seconds)
        project_ids = project_websocket_hub.connected_project_ids()
        if not project_ids:
            continue
        for project_id in project_ids:
            canonical = await get_project_dashboard_version(project_id)
            reconcile_project_snapshot(
                project_id=project_id,
                canonical_version=canonical,
                max_drift_versions=max_drift_versions,
            )
