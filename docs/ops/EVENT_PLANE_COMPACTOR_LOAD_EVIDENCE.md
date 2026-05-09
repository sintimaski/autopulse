# Event-plane compactor load evidence

This document tracks lightweight throughput evidence for compactor fairness/concurrency controls.

## Probe command

From repo root:

```bash
scripts/event_plane_compactor_load_probe.sh
```

Optional env overrides:

- `LUMONOX_EVENT_PLANE_LOAD_SHARDS` (default `200`)
- `LUMONOX_EVENT_PLANE_LOAD_MAX_SHARDS_PER_RUN` (default `25`)
- `LUMONOX_EVENT_PLANE_LOAD_LOW_RUNS` (default `1`)
- `LUMONOX_EVENT_PLANE_LOAD_HIGH_RUNS` (default `4`)

## Latest run evidence

| Date (UTC) | low_runs | high_runs | low_compacted | high_compacted | low_rate | high_rate | Improvement |
|------------|----------|-----------|---------------|----------------|----------|-----------|-------------|
| 2026-05-06 | 1 | 4 | 25 | 100 | 651.58/s | 675.57/s | +3.68% |

Result string:

```text
compactor_load_probe shards=200 max_shards_per_run=25 low_runs=1 low_compacted=25 low_rate=651.58/s high_runs=4 high_compacted=100 high_rate=675.57/s improvement_pct=3.68
```
