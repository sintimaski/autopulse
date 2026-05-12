# Multi-instance deployment notes

Lumonox can run multiple API processes behind a load balancer. A few subsystems are **single-process by default** unless you add infrastructure.

**Canonical HA checklist:** use [PRODUCTION_DEPLOYMENT.md — section 1.2](./PRODUCTION_DEPLOYMENT.md#12-golden-path-horizontally-scaled-api-ha) as the single entry point; this file expands WebSocket, ingest, DuckDB, and job details.

## WebSocket dashboard updates

`project_websocket_hub` is in-memory by default. Clients connected to instance **A** will not receive ingest-triggered pushes from instance **B** unless a shared realtime bus is enabled.

**Mitigations**

- **Sticky sessions** (same client IP → same worker) as a short-term bridge.
- **Single replica** for deployments that rely on live WebSocket updates.
- **Shared realtime bus (implemented):** set `DASHBOARD_REALTIME_BUS_BACKEND=postgres_notify` on Postgres deployments so ingest-triggered realtime messages propagate across replicas via `LISTEN/NOTIFY`.
- **Future scale path:** external pub/sub (for example Redis/NATS) when Postgres-notify semantics are no longer sufficient.

### Load balancer requirement

For multi-replica deployments that keep in-process WS, configure one of:

- LB stickiness for dashboard WS traffic (`/dashboard/ws` path family), or
- Dedicated single WS-serving replica and route all WS traffic there.

If neither is configured, stale/partial live updates are expected and deployment is No-Go for live-dashboard correctness.

### Shared realtime bus configuration (Postgres)

Required for cross-replica WS freshness without stickiness:

- `DASHBOARD_REALTIME_BUS_BACKEND=postgres_notify`
- optional `DASHBOARD_REALTIME_BUS_CHANNEL=lumonox_dashboard_realtime` (letters/digits/underscore only)

Behavior/fallback:

- Bus publish/subscribe is enabled only when `DATABASE_URL` is Postgres.
- If backend is `postgres_notify` but DB is non-Postgres, the app logs a warning and continues with local in-process WS behavior (no crash).
- Large realtime payloads beyond NOTIFY limits are dropped with internal metrics increments (`dashboard.realtime_bus.publish.skipped_payload_too_large`).

### Staging validation (WS freshness)

1. Deploy with target replica count and final LB policy (stickiness or single WS replica).
2. Open dashboard in two independent browser sessions and keep Overview visible.
3. Generate ingest traffic continuously for 5-10 minutes.
4. Verify live timestamps/counters continue advancing in both sessions through page refreshes.
5. Confirm no stale-live drift when requests are routed across replicas (or intentionally pinned).

### Troubleshooting stale live updates

- **Symptom:** Overview/diagnosis "live" counters stop advancing while ingest continues.
  - **Likely cause:** non-sticky WS requests are landing on a replica that does not receive local ingest-triggered pushes.
  - **Remediation:** enable LB stickiness for WS or route WS traffic to a single dedicated replica.
- **Symptom:** Live updates resume only after full page reload.
  - **Likely cause:** WS reconnect lands on a different replica with no shared realtime bus.
  - **Remediation:** enforce sticky affinity across reconnects or move to single WS replica.

## Ingest rate limiting

The default limiter is process-local. Enable `INGEST_DISTRIBUTED_RATE_LIMIT_ENABLED` when running multiple replicas so limits approximate the configured window across hosts. The limiter **fails open** to the in-memory limiter if the SQL-backed window is unhealthy—document expected behavior for operators.

## DuckDB event-writer topology (production requirement)

DuckDB is not a shared multi-writer backend for concurrent API replicas.

Supported production patterns:

- **Single API writer replica + DuckDB file** (recommended embedded pattern).
- **External event plane** (future/shared transport architecture) if you need concurrent writers.

Unsupported / No-Go pattern:

- Multiple API replicas writing events to the same DuckDB file.

Validation for staging before go-live:

1. Deploy the intended replica count and storage wiring.
2. Run sustained ingest load for at least one retention window.
3. Confirm no DuckDB lock/corruption errors in logs.
4. Confirm `/ready` remains healthy across replicas and ingest success remains within SLO budget.

## Background jobs

The in-process scheduler uses leases for some tasks, but you should still treat “multiple pods all running schedulers” as an operational choice: verify lease TTL and DB clock skew.

## Migrations and replica startup

Do not rely on every API replica running Alembic on boot. For production rollouts:

- Run a one-shot migration step (`uv run alembic upgrade head`) before scaling replicas.
- Set `DATABASE_RUN_MIGRATIONS_ON_STARTUP=false` on steady-state API replicas.
- Keep migrate-on-boot enabled only for single-replica/dev contexts.

## Readiness

`/ready` checks SQL metadata connectivity and (when DuckDB is enabled) pings the configured DuckDB file. It does not prove end-to-end SMTP or external OIDC availability—cover those in synthetic checks or external probes.

## Operator alerts (golden signals)

Wire alerts (metrics or log-based) for at least:

- **`ingest.rate_limit.distributed_fallback`** — sustained increments mean the SQL-backed distributed limiter is failing and replicas are falling back to per-process limits (cluster-wide ingest cap accuracy degrades).
- **`/ready` failures** or ingest **5xx** from any replica — catches split-brain data paths, disk full, or migration drift.
- **Scheduler lease churn** — log lines around lease acquisition; clock skew or TTL mis-tuning can cause duplicate or missed job ticks.

Cross-check budgets in **[PRODUCTION_DEPLOYMENT.md](./PRODUCTION_DEPLOYMENT.md)** §6–7.
