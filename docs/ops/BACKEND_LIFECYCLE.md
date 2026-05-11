# Backend lifespan responsibilities

This document is the operational map for `backend/src/lumonox_backend/lifespan.py`. It exists because
that single `@asynccontextmanager` orchestrates many independent async concerns; understanding which
piece owns which signal makes incident response and future refactors safer.

## Startup order

When the FastAPI app starts, `lifespan` runs the following in order:

1. **Logging bootstrap** — `_ensure_lumonox_backend_logging` makes sure `lumonox_backend` INFO logs
   reach stderr even under uvicorn defaults.
2. **Effective-settings dump** — `_log_grouped_startup_settings` logs grouped, non-secret config so
   incidents can be diagnosed without re-reading `.env` files.
3. **Metadata DB migrations** — when `DATABASE_RUN_MIGRATIONS_ON_STARTUP=true`, applies Alembic to
   head. SQLite metadata also runs `Base.metadata.create_all` to cover new tables.
4. **Database warm-up** — `warm_database_connections` opens initial connections so the first
   request does not pay the pool warm-up cost.
5. **Event store warm-up** — when `event_store_enabled(settings)` is true, materializes the DuckDB
   event store so `/ready` does not race the first ingest.
6. **Scheduler** — `start_scheduler` (when `JOBS_ENABLE_SCHEDULER=true`) or
   `start_retention_only_scheduler` for the workspace SQLite default.
   - If `scheduler_required_for_env(settings)` says the scheduler is required but it did not start,
     **startup fails fast** rather than silently degrading retention.
7. **Ingest aggregate worker** — `start_ingest_aggregate_worker` if
   `INGEST_ASYNC_AGGREGATE_ENABLED=true`; otherwise the worker is `None` and ingest persists
   inline.
8. **Retention pressure poll** — `start_retention_pressure_poll` when
   `retention_pressure_poll_should_run(settings)` returns True.
9. **Dashboard WS live tick** — runs `run_dashboard_ws_live_tick_loop` when realtime + WS are
   enabled and `dashboard_ws_live_tick_seconds > 0`.
10. **Realtime bus subscriber** — `run_postgres_realtime_subscriber` when
    `DASHBOARD_REALTIME_BUS_BACKEND=postgres_notify`.
11. **Snapshot reconcile loop** — `run_dashboard_snapshot_reconcile_loop` when realtime + WS are
    enabled.
12. **Event-plane compactor worker** — always started; bounded by
    `LUMONOX_COMPACTOR_*` settings.
13. **Ingest fan-out tracking** — initializes an empty `set` on
    `app.state` keyed by `_INGEST_FANOUT_TASKS_STATE_KEY` so shutdown can drain in-flight tasks.

After step 13, `yield` returns control to FastAPI and the app serves requests.

## Shutdown order

Reverse-order tear-down, all best-effort to avoid blocking shutdown:

1. `drain_ingest_fanout_tasks(app, timeout_seconds=5.0)` — wait briefly for any in-flight
   realtime fan-out work spawned by `POST /ingest`.
2. Stop the scheduler (`SchedulerHandle.stop`).
3. Stop the ingest aggregate worker.
4. Stop the retention pressure poll handle.
5. Cancel the dashboard WS live-tick task.
6. Cancel the realtime bus subscriber task.
7. Cancel the snapshot reconcile task.
8. Stop the event-plane compactor worker.
9. Shut down DuckDB executors and shard writer; release the event store.

## Why this order matters

- **Migrations before connection warm-up** so warm-up does not race ALTERs.
- **Scheduler before workers** so workers have somewhere to enqueue retention/aggregate work
  on startup.
- **Realtime subsystems last** so dashboard pushes do not start before backing data is ready.
- **Fan-out drain first on shutdown** so in-flight realtime work completes (or times out) before
  the snapshot loop and WS tick tasks are cancelled.

## Operational signals

- `GET /ready` — fails 503 if topology guardrails or replay queue health are degraded
  (`_topology_guardrail_status`, `_build_replay_queue_readiness`).
- `GET /internal/metrics` — full snapshot including `scheduler_running`,
  `retention_pressure_poll_running`, `dashboard_ws_tick_running`,
  `dashboard_realtime_bus_subscriber_running`, and the new
  `dashboard.query.<tier>.slow_total` counters.
- `GET /metrics` — Prometheus rendering of the same data.

## When to split this module

The lifespan is concentrated by design — one place to read for incident response. Consider
splitting only if **at least one** of the following becomes a chronic pain point:

- A subsystem needs distinct startup ordering relative to others (e.g. depending on a future
  bus that must be live before workers).
- Targeted tests struggle because the full lifespan must boot for unrelated assertions.
- Operational toggles for one subsystem leak into others.

In every case, keep the canonical startup/shutdown manifest documented here so the
"single place to read" property survives the refactor.
