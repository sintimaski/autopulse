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

## Readiness

`/ready` checks SQL metadata connectivity and (when DuckDB is enabled) pings the configured DuckDB file. It does not prove end-to-end SMTP or external OIDC availability—cover those in synthetic checks or external probes.
