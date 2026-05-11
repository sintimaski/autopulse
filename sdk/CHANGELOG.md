# Changelog

All notable changes to the **Lumonox** Python SDK are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html)
for public API and packaging.

## [Unreleased]

## [0.2.3] - 2026-05-11

### Packaging

- **`[stack]`** extra depends on **`lumonox>=0.2.5`** (aligned with the **0.2.5** API wheel on PyPI).

## [0.2.2] - 2026-05-11

### Packaging

- **`[stack]`** extra depends on **`lumonox>=0.2.1`** (PyPI project **`lumonox`** for the API + bundled dashboard; replaces the prior **`lumonox-api`** distribution name).

## [0.2.1] - 2026-05-10

### Changed

- **Dashboard (bundled in `lumonox-api`):** settings composition and hooks, shared session-scoped dashboard fetches, stricter JSON guards for dashboard query responses, chart and query-toolbar accessibility improvements, extended Vitest/Playwright smoke coverage, and frontend README/ESLint contributor guardrails (see `docs/FRONTEND_MULTI_LANE_REVIEW_TASK_PLAN.md`).
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
