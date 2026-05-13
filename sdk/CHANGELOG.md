# Changelog

All notable changes to the **Lumonox** Python SDK are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html)
for public API and packaging.

## [Unreleased]

### Added — Django adapter

- **``lumonox.django`` async middleware adapter.** Install via ``pip install "lumonox-sdk[django]"``. Single-line wire-up:
  ```python
  # settings.py
  MIDDLEWARE = ["lumonox.django.middleware.LumonoxMiddleware", ...]
  # asgi.py
  from lumonox.django import monitor, wrap_asgi
  monitor(api_key="...", ingest_url="...")
  application = wrap_asgi(get_asgi_application())
  ```
  ``wrap_asgi`` drives ``await dispatcher.start()`` / ``stop()`` from the ASGI lifespan so the user does not have to manage SDK lifecycle by hand. The adapter is ASGI/async-only; classic WSGI Django is out of scope for v1.
- **Rich error events for Django 500s.** Because Django's exception middleware catches view exceptions before outer middleware sees them and converts them to 500 responses, the adapter hooks ``django.core.signals.got_request_exception`` and attaches the exception to ``request._lumonox_exception``. When the middleware sees a 500 it pulls the exception details (type, message, stack trace, error hash) onto a ``type=error`` event — same shape as the FastAPI adapter emits.
- **Synthetic Django ASGI fixture.** ``sdk/src/lumonox/fixtures/synthetic_django_app.py`` mirrors ``synthetic_test_app.py`` (healthy route, parameterized route, view that raises). Exercised by ``sdk/tests/test_django_middleware.py`` (3 cases) through ``httpx.ASGITransport``.
- **``[django]`` extra** in ``sdk/pyproject.toml``: ``django>=4.2`` (LTS, supports our ``>=3.10`` Python floor).

### Changed — shared config builder

- **``build_monitor_config(**kwargs) -> _MonitorConfig``** in ``lumonox.core.config`` consolidates the ~140-line env-var / kwargs / defaults plumbing that used to live inside ``fastapi.middleware.monitor()``. Both adapters now funnel through it, so the contract (which ``LUMONOX_*`` env vars are honored, what the defaults are, which scrub keys ship by default) cannot drift between adapters.

### Install ease (no functional regression)

- **Python floor widened to `>=3.10`** (was `>=3.11`). Tested across 3.10 – 3.13 on linux/amd64 and linux/arm64, in both glibc-slim and musl-alpine images via the new install-matrix workflow. ``datetime.UTC`` (3.11+) was replaced with ``datetime.timezone.utc`` to keep the SDK code 3.10-compatible.
- **Dependency floors loosened** to reduce resolver conflicts with apps pinned to older lines (no upper caps):
  - ``fastapi>=0.115.0`` → ``fastapi>=0.100.0``
  - ``httpx>=0.27.0`` → ``httpx>=0.24.0``
  - ``psutil>=6.0.0`` → ``psutil>=5.9.0``

  Floors are the lowest releases that still expose the API surface the SDK uses (Starlette ``BaseHTTPMiddleware``, ``httpx.AsyncClient`` + ``HTTPStatusError`` semantics, the psutil counters in ``_infrastructure.py``). Documented in ``sdk/README.md`` Compatibility table.
- **Install-matrix CI** (``.github/workflows/sdk-install-matrix.yml``): builds the SDK wheel once, installs + smoke-tests it across {3.10, 3.11, 3.12, 3.13} × {amd64, arm64} × {slim, alpine}, plus a ``python:3.10-slim`` cell that pins each dependency at its declared floor. Each cell asserts that ``InfrastructureSampler().sample()`` returns the full psutil-backed counter set (no silent feature loss) and that ``python -c "import lumonox"`` finishes under a 300 ms cold-import budget (the budget is wall-clock around a subprocess, so it includes Python interpreter startup; sized for slow CI cells like musl/QEMU while still catching real import-graph regressions).

### Changed

- **Internal core/adapter split** (no public API change). The implementation now lives under ``lumonox.core.*`` and ``lumonox.fastapi.*``:
  - ``lumonox.fastapi.middleware`` — Starlette-specific glue: ``_LumonoxMiddleware``, ``_resolve_route_path``, FastAPI startup/shutdown handler registration, ``monitor()`` factory (~430 LOC, down from the original 1128).
  - ``lumonox.core.dispatcher`` — ``_EventDispatcher`` (bounded queue, batched gzip POSTs with idempotency keys, retries with exponential backoff + ``Retry-After`` honoring, optional circuit breaker, telemetry observer hook).
  - ``lumonox.core.config`` — ``_MonitorConfig`` dataclass.
  - ``lumonox.core.events`` — event-shape helpers: ``_utc_now_iso``, ``_stable_error_hash``, ``_split_events_for_ingest_json_budget``, ``_build_infrastructure_widget_payload``, ``_merge_widget_payloads``, ``_merge_release_git_into_event``.
  - ``lumonox.core.scrubbing`` — ``DEFAULT_SCRUB_KEYS`` + ``_scrub_value``.
  - ``lumonox.core.env`` — ``LUMONOX_*`` env-var parsers.
  - ``lumonox.core.paths`` — mount-prefix normalization + ``LUMONOX_IGNORE_PATH_PREFIXES`` logic.
  - ``lumonox.core.sampling`` — deterministic request sampling.
  - ``lumonox.core.infrastructure`` — ``InfrastructureSampler`` (was ``lumonox._infrastructure``).
  - ``lumonox.core.jobs`` — ``capture_background_job`` (was ``lumonox._jobs``).
  - ``lumonox.core.runtime_context`` — correlation-id context vars (was ``lumonox._runtime_context``).

  The previous underscore module paths (``lumonox._monitor``, ``lumonox._infrastructure``, ``lumonox._jobs``, ``lumonox._runtime_context``) are now re-export shims and continue to work unchanged for callers that imported from them. There is no deprecation warning; the shims are part of the stability contract.

  ``lumonox.core.*`` is intentionally Starlette-free — a future framework adapter (Django, Flask, Litestar, …) can reuse the dispatcher / scrubbing / event-shape / infrastructure-sampling primitives as a single new file under ``lumonox.<framework>.middleware``. See ``sdk/docs/adapters.md`` for the adapter contract and the minimum import set a non-FastAPI adapter would target. No second adapter ships today; the split is enabling work, not a product commitment.
- **No public API change.** ``from lumonox import monitor, lumonox, capture_background_job`` and the widget classes are identical objects whether reached via canonical or legacy paths. Object identity is locked in by ``sdk/tests/test_canonical_paths.py``.

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
