# ADR: Event-store scaling strategy beyond single DuckDB writer

- **Status:** Accepted (strategic path, not yet implemented)
- **Date:** 2026-05-05
- **Owners:** Platform + Backend + SRE
- **Related:** [PRODUCTION_DEPLOYMENT.md](./PRODUCTION_DEPLOYMENT.md), [AUTOPULSE_PRODUCTION_READINESS_MASTER_AUDIT.md](../AUTOPULSE_PRODUCTION_READINESS_MASTER_AUDIT.md)

## Context

AutoPulse MVP uses DuckDB as the raw event plane and treats writes as single-writer per file. This matches the MVP promise (fast diagnosis with low setup overhead), but creates a known scale and availability ceiling:

- One active writer per DuckDB file.
- Operational risk grows with write concurrency, file size, and restore windows.
- Horizontal API scaling is constrained because replicas cannot all write the same DuckDB file safely.

The product goal remains unchanged: keep the default onboarding path simple for solo and small teams. Any scaled architecture must remain optional and should not burden the default path.

## Decision

Adopt a **two-path event-store architecture**:

1. **Default path (unchanged):** single-writer DuckDB for MVP and low/medium traffic deployments.
2. **Scaled path (new):** move raw event storage to a managed, multi-writer analytical store backed by a durable ingest stream.

For the scaled path, select a deployment target with these required capabilities:

- High-concurrency ingest with horizontal writer scale.
- Columnar analytics optimized for dashboard/event queries.
- Managed HA and backup/restore support.
- Cost controls for retention and cold storage.

`ClickHouse` (managed or self-hosted) is the reference implementation target for this ADR because it best matches append-heavy ingest + analytical read patterns while preserving SQL-like operational workflows. Equivalent platforms may be used if they satisfy the same requirements.

## Compatibility with MVP goals

The scaled path is additive and must preserve MVP simplicity:

- Keep DuckDB as the default for "about two minutes to useful visibility."
- Preserve existing ingest API contract for SDKs and agents.
- Keep diagnosis-first dashboard flows unchanged from a user perspective.
- Avoid introducing mandatory observability-engineering steps for the default path.

## Options considered

| Option | Fit for MVP defaults | HA / multi-writer | Ops complexity | Cost profile at higher volume | Decision |
|--------|----------------------|-------------------|----------------|-------------------------------|----------|
| Keep single-writer DuckDB only | Excellent | Poor | Low | Poor beyond medium scale | Rejected as long-term only |
| Raw events in Postgres metadata DB | Medium | Medium | Medium | High write amplification + storage cost | Rejected |
| Stream + columnar event store (reference: ClickHouse) | Good as optional tier | Strong | Medium/High | Better at sustained high ingest | Accepted |

## Migration strategy

Use a reversible phased migration to reduce risk:

1. **Readiness instrumentation**
   - Ensure operators track ingest throughput, DuckDB growth, and writer/lock incident classes.
   - Publish threshold dashboards from `/internal/metrics` and incident labels.
2. **Shadow dual-write (limited scope)**
   - Add optional dual-write from ingest pipeline to the scaled store for selected projects/environments.
   - Keep DuckDB authoritative for production reads while validating parity.
3. **Read shadowing and parity checks**
   - Run dashboard query parity checks between DuckDB and scaled store.
   - Measure drift, latency, and failure behavior.
4. **Project-scoped cutover**
   - Enable scaled-store reads for opted-in projects.
   - Keep rollback path to DuckDB until parity/error budgets are stable.
5. **General availability for scaled tier**
   - Offer scaled path as an explicit deployment mode with documented runbooks, backup/restore drills, and SLOs.

## Trigger thresholds for adopting scaled path

Adopt the scaled path when **any one hard trigger** or **two soft triggers** are met for the same environment.

### Hard triggers

- Required topology includes multiple active ingest writers for one logical event plane.
- Required RTO/RPO or HA targets cannot be met with single-writer DuckDB operationally.
- Repeated DuckDB writer lock/corruption incidents: `>= 2` Sev2+ incidents in 30 days.

### Soft triggers

- Sustained ingest pressure attributable to writer constraints:
  - p95 `POST /ingest` latency above release gate (`> 300 ms`) for 3 consecutive peak windows, and
  - correlated ingest pressure signals (`aggregate_worker_sync_fallback_total`, queue depth pressure, or write-lock retries) in the same windows.
- Event-store growth pressure:
  - DuckDB file exceeds `200 GB`, or
  - growth exceeds `50 GB/week` for 4 consecutive weeks, or
  - restore drills exceed agreed RTO by `> 25%`.
- Operational overhead trend:
  - `>= 3` incidents in 60 days linked to single-writer constraints or event-plane maintenance burden.

Thresholds should be tuned with production benchmarks, but this ADR defines the minimum default decision gates.

## Operational cost and ownership expectations

Compared to default DuckDB, scaled path introduces:

- Additional infrastructure (stream + managed analytical store).
- New runbooks (partitioning, retention tiers, backfill, replay).
- Higher baseline spend but lower marginal cost and risk at higher volume.

Adoption must be justified by measured pressure signals, not by speculative scale planning.

## Non-goals

- Replacing DuckDB as the default MVP event store.
- Changing SDK capture defaults or requiring users to understand stream internals.
- Expanding into full APM/distributed tracing scope.
