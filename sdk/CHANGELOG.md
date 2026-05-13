# Changelog

All notable changes to the **Lumonox** Python SDK are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html)
for public API and packaging.

## [Unreleased]

## [0.2.7] - 2026-05-13

### Added

- **Reliable `sdk_version`:** monitor now resolves the installed distribution version (`importlib.metadata`) so ingest records receive a concrete `sdk_version` instead of `unknown` for standard `lumonox-sdk` installs.
- **Batch byte budget (`LUMONOX_INGEST_MAX_BATCH_BYTES` / `ingest_max_batch_bytes`):** dispatcher splits serialized batches that exceed the configured client cap to avoid 413s from the server `ingest_max_request_bytes` limit; documented split policy in `sdk/README.md`.
- **Bounded concurrent sends (`LUMONOX_MAX_CONCURRENT_SENDS` / `max_concurrent_sends`):** asyncio semaphore caps in-flight POSTs, reducing head-of-line blocking on a single slow request; per-POST idempotency keys are preserved.
- **Opt-in ingest circuit breaker (`LUMONOX_CIRCUIT_FAILURE_THRESHOLD` / `LUMONOX_CIRCUIT_OPEN_SECONDS`):** fail-fast after N consecutive terminal failures for a configured cooldown window; disabled by default; never blocks the host app.
- **Telemetry observer hook (`telemetry_observer` kwarg):** opt-in callable receives a small read-only dict per ingest batch outcome (`kind`, `ok`, `events`, `attempt`, `duration_ms`, `queue_depth`, …) for export to OpenTelemetry / app logger; no overhead when unset.
- **Release/git metadata (`LUMONOX_RELEASE` / `LUMONOX_GIT_SHA`):** monitor attaches `release` and `git_sha` to captured events so dashboard overview and diagnosis charts can render release markers.

### Packaging

- **`[stack]`** extra depends on **`lumonox>=0.2.10`** (aligned with the **0.2.10** API wheel that ships the operator-health surface, incident server persistence, alert lifecycle controls, team bookmarks, scoped export, and release markers).

## [0.2.6] - 2026-05-12

### Added

- **Correlation IDs:** middleware prefers incoming **`X-Request-ID`** or **`X-Correlation-ID`** for the captured **`request_id`**, and echoes **`X-Request-ID`** on the HTTP response when the client did not send one.
- **Background jobs:** when **`correlated_request_id`** is omitted, **`capture_background_job`** can inherit the active correlation from request context (contextvar set by the middleware).

### Packaging

- **`[stack]`** extra depends on **`lumonox>=0.2.9`** (aligned with the **0.2.9** API wheel).

## [0.2.5] - 2026-05-12

### Added

- Expanded **`lumonox._monitor`** unit test coverage (scrub defaults, partial-batch flush on worker stop, HTTP 408 retry path).

### Packaging

- **`[stack]`** extra depends on **`lumonox>=0.2.8`** (aligned with the **0.2.8** API wheel).

## [0.2.4] - 2026-05-11

### Added

- **`create_app`** / **`mount_on_app`** on **`lumonox`** via lazy **`__getattr__`** when the **`lumonox`** API distribution is installed (for example **`lumonox-sdk[stack]`**), so one import path stays consistent with **`pip install lumonox`** alone.

### Packaging

- **`[stack]`** extra depends on **`lumonox>=0.2.6`** (API wheel ships the **`lumonox`** facade module alongside **`lumonox_backend`**).

## [0.2.3] - 2026-05-11

### Packaging

- **`[stack]`** extra depends on **`lumonox>=0.2.5`** (aligned with the **0.2.5** API wheel on PyPI).

## [0.2.2] - 2026-05-11

### Packaging

- **`[stack]`** extra depends on **`lumonox>=0.2.1`** (PyPI project **`lumonox`** for the API + bundled dashboard; replaces the prior **`lumonox-api`** distribution name).

## [0.2.1] - 2026-05-10

### Changed

- **Dashboard (bundled in `lumonox-api`):** settings composition and hooks, shared session-scoped dashboard fetches, stricter JSON guards for dashboard query responses, chart and query-toolbar accessibility improvements, extended Vitest/Playwright smoke coverage, and frontend README/ESLint contributor guardrails (see `frontend/README.md`).
- **Release tooling:** `/dashboard` first-load uncompressed JS bundle budget headroom updated to match current Next.js output (`frontend/scripts/checkRouteBundleBudgets.mjs`).

### Packaging

- **`[stack]`** extra requires **`lumonox-api>=0.2.1`**.

## [0.2.0] - 2026-05-09

### Changed

- **Branding and packaging:** project and PyPI distributions are **Lumonox** (`lumonox-sdk`, `lumonox-api`); Python packages are **`lumonox`** (SDK) and **`lumonox_backend`** (API). Environment variables use the **`LUMONOX_`** prefix; dashboard static export mounts at **`/lumonox/ui/`**.

### Breaking

- **Database migrations:** Alembic history is replaced by a **single `initial` revision** that creates the full schema from current ORM models. Existing SQLite dev databases with stale `alembic_version` rows may be **recreated** on startup when migrations cannot resolve the old revision (see `upgrade_to_head` in `lumonox_backend.database.migrations`). Plan Postgres upgrades explicitly (`alembic stamp` / dump-restore) before deploying.

### Packaging

- **`[stack]`** extra requires **`lumonox-api>=0.2.0`**.

## [0.1.4] - 2026-05-08

### Packaging

- **`[stack]`** extra requires **`lumonox-api>=0.1.5`** (aligned with the current API wheel release train).

## [0.1.3] - 2026-05-08

### Packaging

- **`[stack]`** extra now depends on **`lumonox-api>=0.1.4`** (PyPI name for the API + bundled dashboard).

## [0.1.2] - 2026-05-08

### Added

- Optional extra **`[stack]`**: depends on the API distribution so `pip install "lumonox-sdk[stack]"` installs the API (with bundled dashboard) plus this SDK.

### Packaging

- **PyPI distribution name** for the SDK remains **`lumonox-sdk`** (import package **`lumonox`**).

### Security

- **Breaking / privacy:** `monitor()` now defaults `capture_headers` and `capture_query_params` to **off** unless enabled via kwargs or `LUMONOX_CAPTURE_HEADERS` / `LUMONOX_CAPTURE_QUERY_PARAMS`. Reduces accidental PII in events.
- **Embedded:** if `.env.lumonox` cannot be written, the SDK no longer falls back to a repo-known API key; it uses the generated key from the failed write attempt for that process and logs remediation steps.

### Fixed

- Middleware tests using a stub dispatcher no longer assume a private `_send_enabled` attribute on arbitrary dispatcher objects (`getattr` fallback).
