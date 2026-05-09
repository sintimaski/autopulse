# Phase 5 Incident Drills

This document defines first-class drill scenarios required for release-hardening readiness.

Use [PHASE5_DRILL_CYCLE.md](./PHASE5_DRILL_CYCLE.md) for cadence and append each run to [PHASE5_DRILL_EVIDENCE_LOG.md](./PHASE5_DRILL_EVIDENCE_LOG.md).

## Required drill catalog (minimum set)

Each required drill must include pass/fail result and a linked artifact.

| Drill id | Scenario | Frequency | Owner |
| --- | --- | --- | --- |
| `replay-recovery` | SQL-tail replay queue recovery after induced SQL-side failure | Weekly in staging; mandatory before prod promotion for ingest-path changes | Backend + Ops |
| `scheduler-absence` | Scheduler outage / missing scheduler in required env profile | Weekly in staging; mandatory before prod promotion for scheduler/topology changes | Ops owner |
| `realtime-degradation` | WebSocket/realtime degradation and recovery in multi-instance routing | Weekly in staging where multi-replica/live updates are enabled | Frontend + Ops |
| `migration-rollback` | Migration rollback / failed migration recovery path | Monthly and before rollout that changes migration strategy | Backend lead |
| `stale-aggregate-recovery` | Aggregate staleness detection and repair to freshness target | Weekly in staging | Backend + Ops |

## Drill: replay-recovery

- Trigger: induce SQL-side persistence failure after ingest accepted events, then restore DB health.
- Pass criteria:
  - `replay_queue.pending_sql_tail_repairs` decreases after replay.
  - `replay_queue.oldest_pending_age_seconds` trends down and recovery completes in <10 minutes.
  - `sql_tail_repair_dead_lettered_total` does not increase after remediation.
- Evidence:
  - `/dashboard/system-diagnostics` replay queue snapshot before/after.
  - Replay command output: `uv run python -m autopulse_backend.jobs replay-sql-tail-repairs-once`.

## Drill: scheduler-absence

- Trigger: run staging profile with scheduler intentionally disabled/unavailable.
- Pass criteria:
  - startup fails closed for unsafe profile, or `/ready` degrades with explicit guardrail reason.
  - once scheduler restored, `/ready` returns healthy.
- Evidence:
  - startup/ready output containing scheduler guardrail status.
  - `/internal/metrics` topology guardrail snapshot.

## Drill: realtime-degradation

- Trigger: remove WS stickiness/shared bus in multi-replica staging, then restore supported routing.
- Pass criteria:
  - stale live-update behavior is observable during fault.
  - after remediation, live counters advance in concurrent sessions.
- Evidence:
  - two-session dashboard check notes and remediation action.
  - topology/realtime backend markers from `/internal/metrics`.

## Drill: migration-rollback

- Trigger: apply migration in staging, then execute rollback path for a controlled failure scenario.
- Pass criteria:
  - rollback command path is successful.
  - app returns to healthy `/ready` and expected schema state.
- Evidence:
  - migration command transcript and rollback transcript.
  - post-rollback health checks (`/health`, `/ready`).

## Drill: stale-aggregate-recovery

- Trigger: create aggregate lag (worker pause or SQL tail failure), then resume repair path.
- Pass criteria:
  - dashboard aggregate freshness recovers to target window.
  - no sustained growth in aggregate dead-letter backlog.
- Evidence:
  - freshness lag snapshot (`ingestion_freshness.lag_seconds`) before/after.
  - aggregate/replay counters from `/internal/metrics`.

## Optional supplemental drills

- `ingest-overload`
- `alert-delivery-failure`
- `retention-archive-failure`
- `auth-session-scope`
- `scheduler-lease-handoff`

## Escalation and rollback template

- Severity: `SEV-2` or higher if ingest/replay freshness SLO is breached for more than 15 minutes.
- Escalate to: on-call backend owner, then ops owner, then product owner if customer impact persists.
- Rollback:
  1. Disable async aggregate processing (`INGEST_ASYNC_AGGREGATE_ENABLED=0`) if queue/worker is unhealthy.
  2. Disable lease mode (`JOBS_SCHEDULER_LEASE_ENABLED=0`) if lock backend is unstable.
  3. Re-deploy previous release tag and confirm `/ready` plus diagnostics surfaces.
