# Dashboard query latency contract (FE / BE)

This document defines how the dashboard balances **low latency**, **stability**, and **observability** for DuckDB-backed reads.

## Endpoint classes

| Class        | Examples                                      | Target p95 (single-node) | Notes                                      |
| ------------ | --------------------------------------------- | ------------------------- | ------------------------------------------ |
| Interactive  | `POST /dashboard/query` (light bundle)        | ≤ 800 ms                  | Primary overview + requests path         |
| Heavy        | `POST /dashboard/query` (extended/diagnosis)  | ≤ 2500 ms                 | More slices; may queue under load          |
| Explorer     | `POST /dashboard/query-explorer/execute`      | User-initiated            | Bounded by `row_limit` + server caps       |
| Logs         | `POST /dashboard/log-query/execute`           | ≤ 1500 ms                 | Keyset pagination; bounded window            |

## Frontend behavior

- **Timeout:** `DASHBOARD_FETCH_TIMEOUT_MS` (default **18s**, overridable via `NEXT_PUBLIC_LUMONOX_DASHBOARD_FETCH_TIMEOUT_MS` in `frontend/components/dashboard/dashboardDataFetchUtils.ts`). Aborts with `AbortError` if exceeded.
- **Slow fetch backoff:** After a slow or erroring batch (`LIVE_FETCH_SLOW_MS`, aligned with timeout budget), WebSocket-driven refresh widens spacing to reduce cancel storms (`LIVE_REFRESH_BACKOFF_*` in the same module).
- **Cancellation:** User navigation or overlapping refresh passes an `AbortSignal`; aborted fetches must not surface as hard errors on the next successful load.
- **Overview home:** The client alternates **light** and **heavy** `POST /dashboard/query` bodies on `/dashboard` (heavy on interval `DASHBOARD_HEAVY_SLICES_REFRESH_INTERVAL_MS` in `dashboardDataFetchUtils.ts`). The Overview scope freshness timer resets only on **heavy** responses; `OVERVIEW_FE_DATA_STALE_AFTER_MS` marks red if a heavy bundle is overdue.

## Backend behavior

- **DuckDB reads** run on a thread pool (`run_duckdb_read_sync`). Metrics:
  - `duckdb.read.<operation>.duration_ms`, `duckdb.read.<operation>.total`
  - `duckdb.read.<operation>.cancelled_wait_total` when the asyncio waiter is cancelled before completion
  - `duckdb.read.<operation>.slow_light_total` / `slow_heavy_total` (thresholds 1s / 3s wall time)
- **`POST /dashboard/query`:** `dashboard.query.<light|heavy>.duration_ms|total|slow_total|cancelled_total` plus per-slice `dashboard.query.slice.<name>.duration_ms`.
- **Response headers (additive, non-breaking):** every `POST /dashboard/query` reply sets `X-Lumonox-Bundle-Tier` (`light`/`heavy`), `X-Lumonox-Bundle-Cache` (`hit`/`miss`), and `X-Lumonox-Bundle-Elapsed-Ms`. Slow responses also set `X-Lumonox-Bundle-Slow: 1` (light ≥ 1000 ms, heavy ≥ 3000 ms). Clients may surface these headers for diagnostic banners; absence implies a hit on a server that pre-dates the headers.
- **Dedupe shield:** `LUMONOX_DASHBOARD_QUERY_DEDUPE_USE_SHIELD` (default `1`). When `0`, duplicate waiters on the same cache key are not `asyncio.shield`ed (cancellations propagate to waiters; use only if orphan work is worse than stampede risk).
- **Concurrency defaults:** Read executor workers default to `min(64, max(4, cpu*2))`. Heavy bundle concurrency defaults to `max(2, min(8, cpu))`. Override with `LUMONOX_DUCKDB_READ_EXECUTOR_WORKERS` and `LUMONOX_DASHBOARD_QUERY_HEAVY_CONCURRENCY`.

## Operational checks

1. `GET /internal/metrics` — confirm `dashboard.query.*` and `duckdb.read.*` counters move under dashboard load.
2. Compare **p95** `dashboard.query.light.duration_ms` vs user-reported “cancelled” rate in the browser network tab.
3. If CPU is saturated, lower `LUMONOX_DUCKDB_READ_EXECUTOR_WORKERS` and/or set `LUMONOX_DUCKDB_THREADS` explicitly (every connection to the same DuckDB file must share identical connect options) to reduce oversubscription.
