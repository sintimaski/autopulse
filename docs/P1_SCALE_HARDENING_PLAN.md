# P1 scale hardening plan — pagination consistency and durable aggregate pipeline

Status: plan only (not yet implemented). Source: P1 "scale hardening" slice from the internal Cursor planning notes (not committed); see also [AutoPulse Full Gap Analysis and Roadmap](./FULL_GAP_ANALYSIS_AND_ROADMAP.md).

This document is not under documentation governance (see [DOCUMENTATION_GOVERNANCE.md](./DOCUMENTATION_GOVERNANCE.md)); it is a working plan for a follow-up sprint. Scope stays inside MVP guardrails from [DEVELOPMENT.md](../DEVELOPMENT.md) (diagnosis-first, small-team observability).

## Goals

1. Keep request, error-group, log-query and alert-dispatch listings **stable and cheap** while event volume grows from single-host SQLite to tens-of-thousands of events per minute on DuckDB/Postgres.
2. Make the async aggregate pipeline **durable by default**: no silent data loss when the worker process dies, restarts, or the queue overflows.
3. Preserve the AutoPulse "two-minute to useful diagnosis" promise — no new operator knobs in the default profile.

## Non-goals

- No new storage engines. DuckDB (event store) + SQLite/Postgres (aggregates + metadata) remain.
- No distributed tracing, no cross-cluster aggregation.
- No external queue runtime (Redis / RabbitMQ / SQS) in the default profile; plan must cover upgrade path, not force it.

## Current state (evidence)

- Request listing: [`backend/src/autopulse_backend/dashboard/routes/requests_routes.py`](../backend/src/autopulse_backend/dashboard/routes/requests_routes.py) uses offset/limit and a separate `COUNT(*)` against `Event` / DuckDB. Acceptable today, quadratic-ish as `offset` grows on large windows.
- Log queries: [`backend/src/autopulse_backend/dashboard/routes/log_query_routes.py`](../backend/src/autopulse_backend/dashboard/routes/log_query_routes.py) already uses a stable `(timestamp, id)` cursor via `encode_log_cursor`. This is the pattern to generalise.
- Error groups and alert dispatches: offset-based; fine for UI limits today but not for deep-scroll or export paths.
- Query bundle: [`backend/src/autopulse_backend/schemas/dashboard.py`](../backend/src/autopulse_backend/schemas/dashboard.py) clamps `limit`/`offset`; bundle response size grows with largest section.
- Aggregate pipeline: [`backend/src/autopulse_backend/services/ingest_aggregate_worker.py`](../backend/src/autopulse_backend/services/ingest_aggregate_worker.py) uses an in-process `asyncio.Queue` fed from [`backend/src/autopulse_backend/routes/ingest.py`](../backend/src/autopulse_backend/routes/ingest.py). On enqueue failure there is a sync fallback (`ingest.aggregate_worker.sync_fallback`). On worker death mid-payload, the payload is lost and only a counter (`ingest.aggregate_worker.failed`) + log line remain — raw events are still persisted, but metric buckets and error group aggregates for that payload are not.

## Risks the plan addresses

- **Pagination drift**: offset-based paging over a moving event stream shows duplicates/gaps when new events arrive between pages. Users cannot trust "page 3 of errors" during an active incident.
- **Hot filters**: large windows combined with high-cardinality `path_contains` can materialise millions of rows pre-LIMIT even with the current `WITH filtered AS MATERIALIZED` optimisation in [`event_store.py`](../backend/src/autopulse_backend/services/event_store.py).
- **Aggregate loss on crash**: in-memory queue empties on SIGTERM/OOM; the window around the crash has correct raw events but wrong dashboard aggregates until retention/backfill.
- **Backpressure blindness**: `/internal/metrics` now exposes `ingest_pressure` (P0 work), but we still lack a "stuck worker" signal — a consumer that is alive but falling behind.

## Plan — pagination consistency

### P1.A.1 — Shared cursor helper

- File(s) to add: `backend/src/autopulse_backend/dashboard/cursor.py` (new) — lift and generalise the `encode_log_cursor`/`decode_log_cursor` pair from `log_query_routes.py`.
- Cursor shape: base64url of `(timestamp_iso, id)`; opaque to the client.
- Helper signature: `encode_cursor(timestamp: datetime, id: int) -> str`, `decode_cursor(value: str) -> tuple[datetime, int] | None`.

### P1.A.2 — Convert offset-based list endpoints to cursor-based

Order of conversion (smallest blast radius first):

1. `/dashboard/alert-dispatches` — lowest traffic, already ordered by `triggered_at DESC, id DESC`.
2. `/dashboard/error-groups` — only when `error_group_sort=last_seen`; keep `count` sort on offset (aggregate table is bounded and `group_key` is stable).
3. `/dashboard/requests` — the highest-value conversion; align on `(timestamp DESC, id DESC)`.
4. `/dashboard/diagnosis/error-group-events` — mirror requests pattern.

Contract per endpoint:

- Accept `cursor` query parameter. When present, `offset` is ignored.
- Response adds `next_cursor: str | None` and `has_more: bool`.
- Keep `total` on the **first** page only (opt-in via `include_total=true`), because `COUNT(*)` is the expensive half of many of these calls. Fetch `LIMIT limit + 1` and derive `has_more`.
- Query bundle request (`DashboardDataQueryRequest`) gains per-section `cursor` and `include_total` flags; defaults keep behaviour identical.

### P1.A.3 — Frontend wiring

- `frontend/components/dashboard/DashboardDataContext.tsx` — paging state switches from `(limit, offset)` to `(limit, cursorStack: string[])` per slice.
- URL persistence keeps `page=N` for backward compatibility but maps it to a cursor stack; deep links stay legal across releases.
- First load avoids `include_total` except on pages that actually render a count badge.

### P1.A.4 — DuckDB hot-window optimisation

- In `event_store.fetch_events_with_total`, add a cursor-aware branch that drops the `COUNT(*)` CTE when `include_total=false` (matches `/dashboard/requests?include_total=false`).
- Add a `MAX_LIMIT` guard (current 250 for requests, 100 for error_groups) already clamps; no additional clamp needed.

### Acceptance criteria (P1.A)

- All four endpoints accept `cursor` and return `next_cursor` and `has_more`; `total` is only computed when requested.
- Deep-scroll regression test: seeding 50k events, the second page returned by cursor paging does not include any row from the first page and does not skip any row inserted **before** the initial request timestamp.
- Frontend deep link with `page=5` still works (round-trips through the new context without blank states).
- `/internal/metrics` gains `dashboard_query_total_requested` / `dashboard_query_total_skipped` counters so we can see how often operators request expensive counts.

## Plan — durable aggregate pipeline

### P1.B.1 — Outbox table for pending aggregate deltas

- New table `ingest_aggregate_outbox(id, project_id, enqueued_at, metric_bucket_payload JSONB, error_group_payload JSONB, attempt_count, last_error, processed_at NULL)`.
- Written **inside the same DB transaction** as the raw event insert in `persist_ingest_batch` (when `ingest_async_aggregate_enabled=true`). Raw events + outbox row commit or fail together.
- In-memory queue stays, but now carries only the `outbox.id`. Payload is reloaded by the worker.

### P1.B.2 — Worker contract

- On success: mark outbox row `processed_at`, delete or mark-for-retention.
- On `upsert_*` failure: increment `attempt_count`, persist `last_error`, re-enqueue with exponential backoff up to `ingest_aggregate_outbox_max_attempts` (default 5). After max, mark row `failed`; do not silently drop.
- Worker startup scans for `processed_at IS NULL AND attempt_count < max` and re-enqueues — this is the **crash-safe** path that the current queue lacks.

### P1.B.3 — Backpressure signals

- Expose via `/internal/metrics` and Prometheus (extending today's `ingest_pressure` view):
  - `ingest_aggregate_outbox_pending` (gauge, by project).
  - `ingest_aggregate_outbox_failed` (counter).
  - `ingest_aggregate_worker_lag_seconds` (gauge; oldest unprocessed `enqueued_at`).
- Alert hook: reuse `alert_service` to fire an internal self-alert when lag > threshold for > cooldown (keeps operator on existing alert UX rather than inventing a new surface).

### P1.B.4 — Worker lifecycle

- Graceful shutdown: on `stop_event` set, drain the in-memory queue but leave outbox rows for the next process — they are durable.
- Startup barrier: when outbox pending > `ingest_aggregate_outbox_replay_batch`, log a one-line replay summary so operators see "we are catching up" rather than silence.

### P1.B.5 — Upgrade path to an external queue

- Keep the outbox as the source of truth. Replace the in-memory `asyncio.Queue` with a Redis / NATS / Postgres-LISTEN adapter behind a single `AggregateQueueDriver` interface. No other code changes.
- Default deployment stays on the in-memory driver; small teams do not pay the operational cost of running Redis.

### Acceptance criteria (P1.B)

- Kill -9 of the backend process during load testing does not leave dashboard aggregates behind raw events by more than the configured replay interval.
- Outbox failure path is covered by a test that forces `upsert_metric_buckets` to raise; the row ends up `failed` with a real `last_error`, not silently dropped.
- `/internal/metrics` exposes `ingest_aggregate_outbox_pending` and `ingest_aggregate_worker_lag_seconds`.
- Prometheus scrape contains the above gauges.

## Plan — operator observability for job lag

Not a separate workstream — folds into P1.B.3 plus these additions:

- Scheduler job records already track `last_run_at`, `last_error`. Add a `/internal/metrics` `scheduler_job_lag_seconds{job=...}` gauge.
- Retention job emits a "retention-complete" log with bytes reclaimed (see `.cursor/rules/autopulse-debugging.mdc` guidance — prefer logging over prints).

## Delivery cadence (suggested)

- Sprint A: P1.A.1 and P1.A.2 items 1 and 2 (alert-dispatches, error-groups), plus frontend context refactor to cursor stack while keeping offset callers working.
- Sprint B: P1.A.2 items 3 and 4 (requests, diagnosis), plus `include_total` opt-in. Ship the DuckDB branch.
- Sprint C: P1.B.1 and P1.B.2 (outbox + worker rewrite behind feature flag `INGEST_AGGREGATE_OUTBOX_ENABLED`).
- Sprint D: flip the flag on by default; P1.B.3 and P1.B.4 metrics and lifecycle; P1.B.5 driver interface documented but default driver unchanged.

## Release gates

- Pagination gate: deep-scroll correctness test passes on DuckDB and on the SQLite fallback; no endpoint silently returns `total=0` when `include_total=false`.
- Durability gate: crash test (SIGKILL mid-aggregate) reconciles within `ingest_aggregate_outbox_replay_interval` seconds.
- Observability gate: `/internal/metrics` response includes the four new ingest/aggregate signals and the scheduler lag gauge.

## Out of scope (push to P2)

- Multi-region storage, shard routing, or cross-project fan-in.
- UI for viewing outbox failures beyond the existing alert-dispatch history.
- Automatic backfill of failed outbox rows from the raw event store.
