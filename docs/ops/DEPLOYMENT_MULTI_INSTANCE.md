# Multi-instance deployment notes

AutoPulse can run multiple API processes behind a load balancer. A few subsystems are **single-process by default** unless you add infrastructure.

## WebSocket dashboard updates

`project_websocket_hub` is in-memory. Clients connected to instance **A** will not receive ingest-triggered pushes from instance **B**.

**Mitigations**

- **Sticky sessions** (same client IP → same worker) as a short-term bridge.
- **Single replica** for deployments that rely on live WebSocket updates.
- **Proper fix**: shared pub/sub (for example Redis) between ingest handlers and WebSocket workers (post-MVP engineering).

## Ingest rate limiting

The default limiter is process-local. Enable `INGEST_DISTRIBUTED_RATE_LIMIT_ENABLED` when running multiple replicas so limits approximate the configured window across hosts. The limiter **fails open** to the in-memory limiter if the SQL-backed window is unhealthy—document expected behavior for operators.

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
