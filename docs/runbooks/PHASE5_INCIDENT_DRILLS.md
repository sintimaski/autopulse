# Phase 5 Incident Drills

This document defines rehearsal drills required for release-hardening readiness.

**Cadence and evidence:** use [PHASE5_DRILL_CYCLE.md](./PHASE5_DRILL_CYCLE.md) and append outcomes to [PHASE5_DRILL_EVIDENCE_LOG.md](./PHASE5_DRILL_EVIDENCE_LOG.md).

## Drill 1: Ingest Overload

- Trigger: send sustained oversized or high-rate ingest requests.
- Expected signal: `POST /ingest` starts returning explicit overload responses.
- Evidence:
  - `/ready` remains healthy.
  - `/internal/metrics` and `/metrics` counters increase for ingest rejections.
  - No scheduler crash.
  - Aggregate freshness recovers inside target window after load stops.

## Drill 2: Alert Delivery Failure

- Trigger: set invalid alert provider credentials and run `alerts-once`.
- Expected signal:
  - Alert dispatch row includes `status=failed`.
  - Guided troubleshooting panel surfaces alert delivery failure.
- Evidence:
  - Failed dispatch reason code is visible in Alerts and stored.
  - Recovery after credentials fix is confirmed.

## Drill 3: Retention Backlog / Archive Failure

- Trigger: enable archival and induce archival write failure.
- Expected signal:
  - Retention status transitions to `failed`.
  - Last error is recorded in retention settings.
- Evidence:
  - Archived rows are not duplicated on retry.
  - Cleanup resumes after configuration fix.

## Drill 5: Scheduler Lease / Leader Handoff

- Trigger: run two backend instances with scheduler enabled and lease mode on.
- Expected signal:
  - Only one instance executes each periodic job at a time.
  - Lease handoff occurs when leader instance is terminated.
- Evidence:
  - Job counters increase once per interval (no duplicate bursts).
  - `/internal/metrics` shows continued progress after failover.

## Escalation and rollback template

- Severity: `SEV-2` or higher if ingest SLO is breached for more than 15 minutes.
- Escalate to: on-call backend owner, then product owner if customer impact persists.
- Rollback:
  1. Disable async aggregate processing (`INGEST_ASYNC_AGGREGATE_ENABLED=0`) if queue/worker is unhealthy.
  2. Disable lease mode (`JOBS_SCHEDULER_LEASE_ENABLED=0`) if lock backend is unstable.
  3. Re-deploy previous release tag and confirm `/ready` and `/metrics`.

## Drill 4: Auth and Session Scope

- Trigger: validate org/member access with both owner and member accounts.
- Expected signal:
  - Member cannot run owner-only governance actions.
  - Owner can invite and update roles.
- Evidence:
  - Audit events are written for invite/role changes.
  - Session payload includes organization and role context.
