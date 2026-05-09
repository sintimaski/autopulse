#!/usr/bin/env bash
# Compare compactor per-tick throughput across run budgets.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

SHARDS="${LUMONOX_EVENT_PLANE_LOAD_SHARDS:-200}"
MAX_SHARDS_PER_RUN="${LUMONOX_EVENT_PLANE_LOAD_MAX_SHARDS_PER_RUN:-25}"
LOW_RUNS="${LUMONOX_EVENT_PLANE_LOAD_LOW_RUNS:-1}"
HIGH_RUNS="${LUMONOX_EVENT_PLANE_LOAD_HIGH_RUNS:-4}"
export SHARDS MAX_SHARDS_PER_RUN LOW_RUNS HIGH_RUNS

uv run python - <<'PY'
from __future__ import annotations

import json
import os
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path

from lumonox_backend.services.event_plane_compactor import EventPlaneCompactor
from lumonox_backend.services.event_plane_manifest import ShardManifestState, SqliteShardManifest

shards = max(1, int(os.environ["SHARDS"]))
max_shards_per_run = max(1, int(os.environ["MAX_SHARDS_PER_RUN"]))
low_runs = max(1, int(os.environ["LOW_RUNS"]))
high_runs = max(1, int(os.environ["HIGH_RUNS"]))


def prepare(root: Path) -> tuple[SqliteShardManifest, Path]:
    manifest = SqliteShardManifest(root / "events-index" / "manifest.sqlite")
    snapshots_root = root / "events-duckdb"
    now = datetime.now(tz=UTC).isoformat()
    for idx in range(shards):
        shard_path = root / "events-log" / "probe-project" / "2026/05/06/12" / f"{idx}.jsonl"
        shard_path.parent.mkdir(parents=True, exist_ok=True)
        shard_path.write_text(
            json.dumps(
                {
                    "project_id": "probe-project",
                    "timestamp": now,
                    "received_at": now,
                    "sdk_version": "1.0",
                    "type": "request",
                    "service_name": "api",
                    "environment": "test",
                    "method": "GET",
                    "path": f"/probe/{idx}",
                    "status_code": 200,
                    "latency_ms": 1.0,
                    "payload": {},
                },
                separators=(",", ":"),
            )
            + "\n",
            encoding="utf-8",
        )
        manifest.register_open_shard(
            shard_id=f"probe-{idx}",
            project_id="probe-project",
            shard_path=str(shard_path),
        )
        manifest.transition_state(
            shard_id=f"probe-{idx}",
            to_state=ShardManifestState.SEALED,
        )
    return manifest, snapshots_root


def run_probe(run_budget: int) -> tuple[int, float]:
    with tempfile.TemporaryDirectory(prefix="lumonox-compactor-probe-") as tmp:
        root = Path(tmp)
        manifest, snapshots_root = prepare(root)
        compactor = EventPlaneCompactor(
            manifest=manifest,
            snapshots_root=snapshots_root,
            max_shards_per_run=max_shards_per_run,
            max_runs_per_tick=run_budget,
        )
        started = time.perf_counter()
        tick = compactor.compact_tick()
        elapsed = max(0.000001, time.perf_counter() - started)
        manifest.close()
        return tick.compacted_shards, elapsed


low_shards, low_elapsed = run_probe(low_runs)
high_shards, high_elapsed = run_probe(high_runs)
low_rate = low_shards / low_elapsed
high_rate = high_shards / high_elapsed
improvement = ((high_rate - low_rate) / low_rate * 100.0) if low_rate > 0 else 0.0
print(
    "compactor_load_probe "
    f"shards={shards} max_shards_per_run={max_shards_per_run} "
    f"low_runs={low_runs} low_compacted={low_shards} low_rate={low_rate:.2f}/s "
    f"high_runs={high_runs} high_compacted={high_shards} high_rate={high_rate:.2f}/s "
    f"improvement_pct={improvement:.2f}"
)
PY
