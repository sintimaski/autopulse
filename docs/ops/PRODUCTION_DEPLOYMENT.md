# Production deployment (canonical guide)

This document is the **single entry point** for shipping AutoPulse to production. It ties together topology, health checks, scaling limits, backups, and release gates. Deep dives live in linked docs.

## 1. Choose your topology

| Mode | When to use | Primary docs |
|------|----------------|--------------|
| **Split stack** (SDK → remote `POST /ingest`, dashboard API + Next.js UI) | Default: hosted or self-managed API + UI, Postgres metadata, optional DuckDB for events. | [backend/.env.example](../../backend/.env.example), [README.md](../../README.md) |
| **Multi-instance API** | Horizontal scale behind a load balancer. | [DEPLOYMENT_MULTI_INSTANCE.md](./DEPLOYMENT_MULTI_INSTANCE.md) |

**Storage note:** Metadata (projects, API key hashes, aggregates, sessions) lives in the **SQL database** (`DATABASE_URL`). Raw request/error events for the MVP stack typically use **DuckDB** when enabled (`AUTOPULSE_DUCKDB_*`), not “Postgres-only raw rows” unless you operate a custom deployment. Set **`AUTOPULSE_DATA_DIR`** (or an absolute `AUTOPULSE_DUCKDB_PATH`) in production so every process agrees on the DuckDB file regardless of cwd. Align backup procedures with both stores ([BACKUP_RESTORE.md](./BACKUP_RESTORE.md)).

## 1.1 Golden path: embedded SQLite metadata + DuckDB events

Use this as the default single-node topology unless your expected traffic/ops profile requires a remote metadata DB:

| Component | Default setting | Effective default path |
|----------|------------------|------------------------|
| Metadata DB (SQLite) | `DATABASE_URL=sqlite+aiosqlite:///./.autopulse/autopulse.db` | `{AUTOPULSE_DATA_DIR or repo-root}/.autopulse/autopulse.db` |
| Event store (DuckDB) | `AUTOPULSE_EVENT_STORE=duckdb`, `AUTOPULSE_EVENT_PLANE_MODE=duckdb_single_writer`, `AUTOPULSE_DUCKDB_PATH=.autopulse/events.duckdb` | `{AUTOPULSE_DATA_DIR or repo-root}/.autopulse/events.duckdb` |
| Plan B shard log root | `AUTOPULSE_EVENT_PLANE_SHARDS_PATH=.autopulse/events-log` (used when `AUTOPULSE_EVENT_PLANE_MODE=duckdb_log_shards`) | `{AUTOPULSE_DATA_DIR or repo-root}/.autopulse/events-log` |
| Plan B snapshot root | `AUTOPULSE_EVENT_PLANE_SNAPSHOTS_PATH=.autopulse/events-duckdb` (compactor output) | `{AUTOPULSE_DATA_DIR or repo-root}/.autopulse/events-duckdb` |
| File alert outbox (optional) | `ALERT_EMAIL_FILE_OUTBOX_DIR=./.autopulse/emails` | `{AUTOPULSE_DATA_DIR or repo-root}/.autopulse/emails` |

`AUTOPULSE_DATA_DIR` re-anchors relative metadata/event paths so API, jobs, and restore tooling all target the same files independent of process cwd.

Operational assumptions for this embedded mode:

- SQLite metadata is a single-writer design in practice; avoid active-active metadata writers.
- DuckDB event writes must follow the documented single-writer pattern.
- Prefer one API writer process per DuckDB file unless/until you move to a shared event transport/store architecture.

## 2. Environment and secrets

1. Set `AUTOPULSE_ENV=production` and run through production guardrails (dashboard auth, HTTPS ingest, origin enforcement). See [test_deployment_settings.py](../../backend/tests/test_deployment_settings.py) and `validate_deployment_settings` in [`backend/src/autopulse_backend/core/config.py`](../../backend/src/autopulse_backend/core/config.py).
2. Never commit real secrets. Use your platform’s secret manager for `DATABASE_URL`, OIDC client secrets, SMTP, and `INTERNAL_METRICS_BEARER_TOKEN`.
3. **SDK (remote ingest):** set `AUTOPULSE_API_KEY` and `AUTOPULSE_INGEST_URL`. Production-safe capture defaults are **off** for full headers/query strings unless you opt in (`capture_headers` / `capture_query_params` or `AUTOPULSE_CAPTURE_HEADERS` / `AUTOPULSE_CAPTURE_QUERY_PARAMS`). See [sdk/README.md](../../sdk/README.md).

### Internal metrics auth boundary

- `GET /internal/metrics` and `/metrics` are guarded by `INTERNAL_METRICS_BEARER_TOKEN` (operator token).
- Dashboard auth credentials (session cookie or dashboard API key fallback when explicitly enabled) do **not** authorize `/internal/metrics`.
- Keep `DASHBOARD_AUTH_ALLOW_API_KEY_FALLBACK=false` by default in production; only enable temporarily for controlled troubleshooting.

## 2.1 Dashboard auth modes (production)

AutoPulse supports two production-ready dashboard auth modes:

### Mode A — Basic first-party magic-link auth

Use this when AutoPulse owns sign-in directly.

Required:

- `DASHBOARD_AUTH_ENABLED=true`
- At least one identity gate:
  - `DASHBOARD_AUTH_ALLOWED_EMAIL=<exact-address>`, or
  - `DASHBOARD_ALLOWED_EMAIL_DOMAINS=<comma-separated-domains>`
- `DASHBOARD_ENFORCE_ORIGIN_FOR_MUTATIONS=true`

Recommended validation:

1. Request magic link for an allowed address and confirm successful dashboard session.
2. Attempt sign-in with a disallowed address and confirm rejection.
3. Confirm protected routes (`/dashboard/...`) reject unauthenticated access.

### Mode B — Host-integrated / OIDC auth

Use this when your IdP/host controls identity.

Required:

- `DASHBOARD_AUTH_ENABLED=true`
- `DASHBOARD_OIDC_ENABLED=true`
- `DASHBOARD_OIDC_ISSUER_URL`, `DASHBOARD_OIDC_CLIENT_ID`, `DASHBOARD_OIDC_CLIENT_SECRET`
- `DASHBOARD_OIDC_REDIRECT_URI`, `DASHBOARD_OIDC_STATE_SECRET`
- `DASHBOARD_ENFORCE_ORIGIN_FOR_MUTATIONS=true`

Recommended validation:

1. Complete login through IdP and verify dashboard session issuance.
2. Verify unauthorized users cannot access protected dashboard routes.
3. Verify logout clears dashboard session cookie and access is revoked.

### Auth No-Go warning

If dashboard ingress is externally reachable, `DASHBOARD_AUTH_ENABLED=false` is a release **No-Go** unless protected by an equivalent upstream auth gateway with documented enforcement evidence.

## 2.2 Reverse proxy, forwarded headers, and HTTPS trust

Route **all browser and SDK traffic through TLS** at the edge. The backend relies on correct **request scheme** for secure cookies, CSRF-style origin checks on mutations, and optional `INGEST_REQUIRE_HTTPS` enforcement.

| Check | Why it matters |
|-------|----------------|
| **`X-Forwarded-Proto: https`** (or terminate TLS at the proxy and speak HTTP only to the app on a private socket) | Ensure the ASGI stack sees HTTPS when clients use it (forward proto/host through your LB; use Starlette/FastAPI forwarded-header / trusted-proxy configuration appropriate for your deployment). Wrong scheme → insecure cookies, blocked ingest, or broken redirects. |
| **`X-Forwarded-For`** (optional, for logs only by default) | Preserve client IP when needed; do not treat as auth. |
| **Cookie `Secure` behavior** | Dashboard session cookies must be issued for HTTPS in production; verify in browser devtools after deploy. |

**Misconfiguration symptoms**

| Symptom | Likely cause |
|---------|----------------|
| Ingest rejected with HTTPS / scheme errors while clients use `https://` | Missing or wrong `X-Forwarded-Proto`; TLS terminated at LB but headers not set. |
| Redirect loops or wrong OAuth/OIDC redirect base URL | Host/proto headers inconsistent with `DASHBOARD_OIDC_REDIRECT_URI` / public URL. |
| Session works over HTTP in prod | TLS not enforced at edge or scheme forwarded as `http`. |

Validate in staging: issue a real dashboard login and one SDK ingest batch through the **same** LB/proxy path you use in production; confirm `GET /ready` is healthy and `/internal/metrics` `ingest_pressure` shows no unexpected `non_https_rejected_total` spikes.

## 3. Health checks and load balancers

| Endpoint | Purpose |
|----------|---------|
| `GET /health` | Process liveness (does **not** prove database connectivity). |
| `GET /ready` | Database (+ DuckDB when configured) readiness for traffic. |

**Load balancer:** Prefer `/ready` for readiness probes when the data plane must be available. See [DEPLOYMENT_MULTI_INSTANCE.md](./DEPLOYMENT_MULTI_INSTANCE.md) for `/ready` scope (e.g. SMTP/OIDC not fully validated here).

## 4. Multi-instance and realtime

- **WebSockets:** Default hub is in-process. For multi-replica freshness, either enable shared bus (`DASHBOARD_REALTIME_BUS_BACKEND=postgres_notify` on Postgres), configure LB stickiness, or route WS to a single replica. See [DEPLOYMENT_MULTI_INSTANCE.md](./DEPLOYMENT_MULTI_INSTANCE.md).
- **Distributed ingest rate limits:** Enable `INGEST_DISTRIBUTED_RATE_LIMIT_ENABLED` when running multiple API processes; understand **fail-open** behavior to the in-memory limiter if the rate-limit table is unhealthy (documented in code + [DEPLOYMENT_MULTI_INSTANCE.md](./DEPLOYMENT_MULTI_INSTANCE.md)).
- **DuckDB writer rule:** treat DuckDB as **single-writer**. Running multiple API replicas that write to the same DuckDB file is a production **No-Go**.
- **WS correctness rule:** for multi-replica live dashboard correctness, require LB stickiness for WS traffic or route WS to one dedicated replica.

## 5. Jobs, retention, and aggregation

- Enable `JOBS_ENABLE_SCHEDULER=true` where you need scheduled alerts + retention.
- Auto-enable on unset `JOBS_ENABLE_SCHEDULER` only applies to local default SQLite metadata files under `.autopulse/` (`autopulse.db` / `autopulse_embedded.db`).
- For non-default SQLite paths and Postgres metadata, treat missing scheduler as a release **No-Go** unless you run equivalent external cron jobs for alerts/retention.
- Validate scheduler state after deploy:
  - `GET /ready` should report `jobs_enable_scheduler=true` and `scheduler_running=true` (or your documented external-cron mode).
  - `/internal/metrics` and `/metrics` should expose scheduler and job counters.
- Async aggregate worker + dead letters: see [BACKUP_RESTORE.md](./BACKUP_RESTORE.md) and backend `replay-aggregate-dead-letters-once` CLI in [`backend/src/autopulse_backend/jobs/__init__.py`](../../backend/src/autopulse_backend/jobs/__init__.py).

## 5.1 When to move metadata DB off SQLite

Move metadata from SQLite to Postgres (or equivalent managed SQL) when any of these become true:

- You are running multiple API replicas that need consistent metadata writes.
- You need stronger write concurrency than a single host-local SQLite file can provide.
- Your operational model requires remote managed backups/failover for metadata.
- Deployment constraints make shared durable local disk for SQLite impractical.

If you move metadata off SQLite:

- Keep DuckDB single-writer constraints explicit in your deployment runbook.
- Set `JOBS_ENABLE_SCHEDULER=true` (or document/operate equivalent external cron).
- Use one-shot migrations (`alembic upgrade head`) and disable migrate-on-boot on steady-state replicas (`DATABASE_RUN_MIGRATIONS_ON_STARTUP=false`).

## 5.2 Migration strategy for multi-replica API

- Prefer a one-shot migration step in deploy orchestration (`uv run alembic upgrade head`) before scaling API replicas.
- Set `DATABASE_RUN_MIGRATIONS_ON_STARTUP=false` on steady-state API replicas to avoid concurrent DDL races.
- Keep startup migrations enabled (`true`) only for single-replica/dev environments where one process controls schema upgrades.

## 5.3 Cross-store consistency (DuckDB events vs SQL aggregates/widgets)

In typical deployments, **raw events** land in DuckDB (when enabled) while **rollups, error-group aggregates, and dashboard widget metadata** update in the metadata SQL database. Those writes are **not a single distributed transaction** across engines.

**Operational model**

1. **Happy path:** ingest commits DuckDB inserts (when enabled), then applies SQL-side widget + aggregate updates — inline or via the async aggregate worker queue (`INGEST_ASYNC_AGGREGATE_ENABLED`).
2. **Partial failure:** if SQL-side persistence fails after DuckDB succeeded, the request may still return `200` with accepted events while aggregates lag; the service increments `ingest.persist_sql_tail_failed` and logs `ingest_persist_sql_tail_failed`.
3. **Async aggregate backlog:** if the aggregate worker queue drops work (`ingest.aggregate_worker.enqueue_failed`) or repeatedly fails (`ingest.aggregate_worker.failed`), payloads can land in aggregate dead letters for replay (`replay-aggregate-dead-letters-once`). Watch **`ingest_pressure`** on `/internal/metrics`: `aggregate_worker_sync_fallback_total`, `aggregate_worker_enqueue_failed_total`, `aggregate_worker_failed_total`, `persist_sql_tail_failed_total`, and **`ingest_aggregate_queue`** depth vs max.

**Recovery**

- Fix underlying SQL connectivity or disk pressure, then replay dead-letter rows when appropriate.
- Expect **event timeline** in DuckDB to remain authoritative for raw rows; SQL aggregates catch up as retries/replays succeed.

## 6. Observability (golden signals)

Monitor at minimum:

| Signal | Where |
|--------|--------|
| Ingest accepted / rejected | `/internal/metrics` or `/metrics` (bearer-gated) — counters such as `ingest.accepted.*`, `ingest.rejected.*`, `ingest.rate_limit.distributed_fallback` |
| Ingest pressure | `GET /ready` JSON `ingest_pressure` (queue depth, sync fallback, worker failures) |
| Scheduler | Job telemetry from internal metrics + logs |

Tune alerts on **ingest 429 rate**, **aggregate worker dead-letter growth**, and **dashboard `/ready` failures**.

## 6.1 Dashboard read-path protection (expensive queries)

High-cost read endpoints are protected by an app-level per-project rate limiter:

- `POST /dashboard/query`
- `POST /dashboard/query-explorer/execute`

Configuration:

- `DASHBOARD_READ_RATE_LIMIT_REQUESTS_PER_WINDOW` (default `120`, set `0` to disable)
- `DASHBOARD_READ_RATE_LIMIT_WINDOW_SECONDS` (default `60`)

When exceeded, endpoints return `429` with `Retry-After`.

## 6.2 Optional frontend RUM (privacy-first)

Dashboard client telemetry is **opt-in** and disabled by default.

Enable only when you need browser-side runtime/perf visibility:

- `NEXT_PUBLIC_AUTOPULSE_RUM_ENABLED=1`
- `NEXT_PUBLIC_AUTOPULSE_RUM_ENDPOINT=<URL>` (optional override; default is backend `POST /autopulse/rum`)
- `NEXT_PUBLIC_AUTOPULSE_RUM_SAMPLE_RATE=<0..1>` (default `1`)
- `NEXT_PUBLIC_AUTOPULSE_RUM_DEBUG=1` (optional debug logging; keep `0` in production)

Backend endpoint defaults:

- `POST /autopulse/rum` (also reachable at `/rum` on the unprefixed router)
- `DASHBOARD_RUM_MAX_REQUEST_BYTES` (default `8192`, minimum clamp `256`)
- `DASHBOARD_RUM_LOG_PAYLOADS=true` for temporary staging validation only

Default capture is intentionally conservative:

- Route path only (query/hash stripped, id-like segments masked)
- Runtime error message + short stack preview (scrubbed for emails/token-like fragments)
- Session-level navigation timings (`dom_content_loaded_ms`, `load_event_ms`)

No cookies, local storage values, full URLs with query strings, request/response bodies, or auth tokens are collected by this path.

Operator validation:

1. Deploy with RUM disabled and confirm no RUM requests are emitted from dashboard sessions.
2. Enable RUM and set `NEXT_PUBLIC_AUTOPULSE_RUM_SAMPLE_RATE=1` (default sink `/autopulse/rum` unless overridden).
3. Trigger one handled page load and one synthetic browser error (`throw new Error("rum-smoke")` in devtools).
4. Verify endpoint receives scrubbed payloads (no raw emails/tokens/query strings), then disable debug mode.

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

## 7.1 SQLite/Postgres CI policy parity

Policy for metadata DB confidence signals:

- **SQLite path is full gate baseline** (linters, typing, security checks, full pytest/coverage, frontend gates).
- **Postgres path is required optional-path gate** for backend behavior (`backend/tests` in CI).
- If Postgres gate scope changes from this policy, document the exact delta in the same PR (no silent coverage drift).

References:

- CI matrix: `.github/workflows/ci.yml` (`python-sqlite`, `python-postgres`).
- Local release gate script: `scripts/release_gates.sh` (set `AUTOPULSE_RELEASE_GATES_POSTGRES=1` to run optional-path Postgres backend tests locally).

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
- [`../../Dockerfile`](../../Dockerfile) and [`./docker-compose.autopulse.yml`](./docker-compose.autopulse.yml) — official container artifact and minimal compose example.

## 9.1 No-Go triggers (topology)

Do not promote to production if any of the following are true:

- Planned topology has multiple API replicas writing events to one DuckDB file.
- Staging load validation shows DuckDB lock/corruption-class errors.
- You cannot demonstrate the supported writer pattern for your chosen event plane.

## 9.2 Event-store scaling decision triggers

When single-writer DuckDB constraints become operationally limiting, follow the ADR for scaled event storage:

- [ADR_EVENT_STORE_SCALING.md](./ADR_EVENT_STORE_SCALING.md)

Adopt the scaled path when either:

- Any **hard trigger** is met (for example multi-writer HA requirement or repeated Sev2+ DuckDB writer incidents), or
- At least two **soft triggers** are sustained (for example ingest latency pressure tied to writer contention plus restore/file-growth pressure).

Keep DuckDB as the default path unless measured thresholds justify migration.

## 10. Documentation precedence

If another doc conflicts with product scope, **[DEVELOPMENT.md](../../DEVELOPMENT.md)** wins for MVP boundaries; this file wins for **production topology and rollout ordering**.

## 11. Official container artifact (backend + static dashboard)

AutoPulse ships an official `Dockerfile` at repo root that:

- Builds the Next static export (`frontend/out`) in a Node build stage.
- Installs backend dependencies and runs `uvicorn` for `autopulse_backend.main:app`.
- Serves the static dashboard from `AUTOPULSE_FRONTEND_STATIC_DIR=/app/frontend/out`.
- Root [`.dockerignore`](../../.dockerignore) limits build context (for example `.git`, local `node_modules`, `.venv`, `.autopulse`, and trees not used by the Dockerfile) so `docker build` stays fast.

### Build and smoke test

```bash
docker build -t autopulse:local .
docker run --rm -p 8000:8000 \
  -e AUTOPULSE_ENV=production \
  -e DASHBOARD_AUTH_ENABLED=true \
  -e DASHBOARD_AUTH_ALLOWED_EMAIL=you@example.com \
  -e DASHBOARD_ENFORCE_ORIGIN_FOR_MUTATIONS=true \
  -e INTERNAL_METRICS_BEARER_TOKEN=change-me \
  autopulse:local
```

In another terminal:

```bash
curl -s http://127.0.0.1:8000/health
curl -s http://127.0.0.1:8000/ready
```

Expected:

- `/health` returns `{"status":"ok"}`
- `/ready` returns `{"status":"ready", ...}` when DB/event store are reachable

From repo root, a non-interactive equivalent is `bash scripts/docker_smoke.sh` (requires Docker running).

For a persistent local deployment example, use `docs/ops/docker-compose.autopulse.yml`.
