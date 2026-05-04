# Production deployment (canonical guide)

This document is the **single entry point** for shipping AutoPulse to production. It ties together topology, health checks, scaling limits, backups, and release gates. Deep dives live in linked docs.

## 1. Choose your topology

| Mode | When to use | Primary docs |
|------|----------------|--------------|
| **Embedded** (`autopulse[embedded]`, SDK `mode="embedded"`) | Solo dev, single process, fastest DX; SQLite + optional DuckDB event store next to the app. | [README.md](../../README.md), [sdk/README.md](../../sdk/README.md) |
| **Split stack** (SDK → remote `POST /ingest`, dashboard API + Next.js UI) | Hosted or self-managed API + UI, Postgres metadata, optional DuckDB for events. | [backend/.env.example](../../backend/.env.example), [README.md](../../README.md) |
| **Multi-instance API** | Horizontal scale behind a load balancer. | [DEPLOYMENT_MULTI_INSTANCE.md](./DEPLOYMENT_MULTI_INSTANCE.md) |

**Storage note:** Metadata (projects, API key hashes, aggregates, sessions) lives in the **SQL database** (`DATABASE_URL`). Raw request/error events for the MVP stack typically use **DuckDB** when enabled (`AUTOPULSE_DUCKDB_*`), not “Postgres-only raw rows” unless you operate a custom deployment. Set **`AUTOPULSE_DATA_DIR`** (or an absolute `AUTOPULSE_DUCKDB_PATH`) in production so every process agrees on the DuckDB file regardless of cwd. Align backup procedures with both stores ([BACKUP_RESTORE.md](./BACKUP_RESTORE.md)).

## 2. Environment and secrets

1. Set `AUTOPULSE_ENV=production` and run through production guardrails (dashboard auth, HTTPS ingest, origin enforcement). See [test_deployment_settings.py](../../backend/tests/test_deployment_settings.py) and `validate_deployment_settings` in [`backend/src/autopulse_backend/core/config.py`](../../backend/src/autopulse_backend/core/config.py).
2. Never commit real secrets. Use your platform’s secret manager for `DATABASE_URL`, OIDC client secrets, SMTP, and `INTERNAL_METRICS_BEARER_TOKEN`.
3. **SDK (remote ingest):** set `AUTOPULSE_API_KEY` and `AUTOPULSE_INGEST_URL`. Production-safe capture defaults are **off** for full headers/query strings unless you opt in (`capture_headers` / `capture_query_params` or `AUTOPULSE_CAPTURE_HEADERS` / `AUTOPULSE_CAPTURE_QUERY_PARAMS`). See [sdk/README.md](../../sdk/README.md).

## 3. Health checks and load balancers

| Endpoint | Purpose |
|----------|---------|
| `GET /health` | Process liveness (does **not** prove database connectivity). |
| `GET /ready` | Database (+ DuckDB when configured) readiness for traffic. |

**Load balancer:** Prefer `/ready` for readiness probes when the data plane must be available. See [DEPLOYMENT_MULTI_INSTANCE.md](./DEPLOYMENT_MULTI_INSTANCE.md) for `/ready` scope (e.g. SMTP/OIDC not fully validated here).

## 4. Multi-instance and realtime

- **WebSockets:** The dashboard WebSocket hub is in-process; multiple replicas require **sticky sessions**, a **single replica** for WS, or a future shared pub/sub design. See [DEPLOYMENT_MULTI_INSTANCE.md](./DEPLOYMENT_MULTI_INSTANCE.md).
- **Distributed ingest rate limits:** Enable `INGEST_DISTRIBUTED_RATE_LIMIT_ENABLED` when running multiple API processes; understand **fail-open** behavior to the in-memory limiter if the rate-limit table is unhealthy (documented in code + [DEPLOYMENT_MULTI_INSTANCE.md](./DEPLOYMENT_MULTI_INSTANCE.md)).

## 5. Jobs, retention, and aggregation

- Enable `JOBS_ENABLE_SCHEDULER=true` where you need scheduled alerts + retention (or use embedded defaults that start retention appropriately).
- Async aggregate worker + dead letters: see [BACKUP_RESTORE.md](./BACKUP_RESTORE.md) and backend `replay-aggregate-dead-letters-once` CLI in [`backend/src/autopulse_backend/jobs/__init__.py`](../../backend/src/autopulse_backend/jobs/__init__.py).

## 6. Observability (golden signals)

Monitor at minimum:

| Signal | Where |
|--------|--------|
| Ingest accepted / rejected | `/internal/metrics` or `/metrics` (bearer-gated) — counters such as `ingest.accepted.*`, `ingest.rejected.*`, `ingest.rate_limit.distributed_fallback` |
| Ingest pressure | `GET /ready` JSON `ingest_pressure` (queue depth, sync fallback, worker failures) |
| Scheduler | Job telemetry from internal metrics + logs |

Tune alerts on **ingest 429 rate**, **aggregate worker dead-letter growth**, and **dashboard `/ready` failures**.

## 7. SLO / SLI targets (initial release gates)

Treat these as **starting budgets**; tighten per customer tier and measured baseline after two weeks of production traffic.

| Area | SLI | Initial gate (self-serve / small team) |
|------|-----|----------------------------------------|
| Ingest API | `POST /ingest` success (2xx) excluding auth/rate-limit abuse | ≥ 99.5% monthly |
| Ingest latency | p95 server time for authenticated batches under nominal size | ≤ 300 ms at p95 (single region, warm DB) |
| Aggregation freshness | Lag from ingest time to queryable aggregates | ≤ 2 minutes p95 when async aggregate enabled |
| Dashboard reads | p95 for `/dashboard/query` bundle on overview path | ≤ 2 s p95 (uncached cold start excluded) |
| Alert delivery | Successful dispatch for configured email/webhook test | ≥ 98% per rolling 7 days (provider outages documented) |

Record your **actual** p50/p95 after launch; gates above are **release minimums**, not marketing SLAs.

## 8. Backup, restore, and drills

Follow [BACKUP_RESTORE.md](./BACKUP_RESTORE.md). Before GA:

1. Restore SQL + DuckDB snapshot to a staging cluster.
2. Run `alembic upgrade head` (if not already at head) and smoke **one** ingest + **one** dashboard overview query.
3. Run [PHASE5_INCIDENT_DRILLS.md](../runbooks/PHASE5_INCIDENT_DRILLS.md) scenarios relevant to your topology (at minimum: ingest overload + alert provider failure).
4. (Optional automation) Track a Playwright suite against the core journey using [E2E_CORE_JOURNEY.md](../testing/E2E_CORE_JOURNEY.md).

## 9. Related checklists

- [PHASE5_RELEASE_CHECKLIST.md](../runbooks/PHASE5_RELEASE_CHECKLIST.md) — broader product/release gate list.
- [agents/security-privacy.md](../../agents/security-privacy.md) — security review checklist.
- [docs/contracts/ingest-api.md](../contracts/ingest-api.md) — ingest contract and status codes.

## 10. Documentation precedence

If another doc conflicts with product scope, **[DEVELOPMENT.md](../../DEVELOPMENT.md)** wins for MVP boundaries; this file wins for **production topology and rollout ordering**.
