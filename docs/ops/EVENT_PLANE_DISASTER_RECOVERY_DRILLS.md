# Event-plane disaster recovery drills

This document defines repeatable disaster recovery drills for Plan B shard/snapshot assets and records the latest successful run evidence.

## Declared targets

- **RTO target:** 30 minutes to restore a readable snapshot and repoint `CURRENT`.
- **RPO target:** 5 minutes (bounded by compactor interval and pending shard replay window).

## Drill command

From repo root:

```bash
scripts/event_plane_disaster_recovery_drill.sh
```

Modes:

- `LUMONOX_EVENT_PLANE_DRILL_MODE=simulate` (default): builds synthetic snapshot assets, restores them, and verifies readable row count.
- `LUMONOX_EVENT_PLANE_DRILL_MODE=real`: restores from an operator-provided snapshot root:
  - `LUMONOX_EVENT_PLANE_DRILL_SOURCE_SNAPSHOTS_ROOT`
  - `LUMONOX_EVENT_PLANE_DRILL_RESTORE_ROOT`

## Evidence log

| Date (UTC) | Mode | Result | Notes |
|------------|------|--------|-------|
| 2026-05-06 | simulate | success | Restored `CURRENT` pointer and verified `restored_events=1` from recovered snapshot. |

For broader release-hardening cadence (monthly/quarterly scheduling and shared evidence), see [PHASE5_DRILL_CYCLE.md](../runbooks/PHASE5_DRILL_CYCLE.md).
