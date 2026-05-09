# Contributing

Thanks for contributing to Lumonox.

## First read

- `DEVELOPMENT.md` (product + engineering source of truth)
- `docs/DEVELOPMENT_PROCESS.md` (execution and release gates)
- `docs/DOCUMENTATION_GOVERNANCE.md` (governed docs policy)
- `AGENTS.md` (workflow pointers)

## Local setup

From repository root:

```bash
make setup
```

## Validation before PR

```bash
make check
```

Release candidate validation:

```bash
make release-gates
```

## Automated tests (where they live)

- **Python (SDK + backend):** `uv run pytest` from `sdk/` or `backend/` (see `pyproject.toml` `testpaths`).
- **Backend Parquet / object storage:** `backend/tests/test_parquet_*.py` (export, lifecycle, object storage, and `test_parquet_config_paths.py` for path normalization), `backend/tests/test_event_store_duckdb.py`, `backend/tests/test_backend_jobs.py`.
- **Frontend (Vitest):** `npm --prefix frontend test` — tests live next to code as `*.test.ts` / `*.test.tsx` under `frontend/` (see `frontend/vitest.config.ts`).
- **Browser smoke (Playwright):** `npm --prefix frontend run test:e2e` — see `docs/testing/E2E_CORE_JOURNEY.md`.

## PR expectations

- Keep changes small and focused.
- Include tests (or explicit manual verification notes) for behavior changes.
- Call out security-sensitive changes (auth, keys, scrubbing, ingestion limits) in PR description.
- Do not expand scope beyond requested task without explicit approval.

## Ownership and dependency hygiene

- Sensitive paths are protected by `.github/CODEOWNERS`; expect maintainer review on auth, ingest, ops/runbook, and release gate changes.
- Dependabot creates weekly update PRs for Python, frontend npm, and GitHub Actions dependencies via `.github/dependabot.yml`.
- Treat dependency PRs like normal code changes: CI must pass before merge.

## Scope guardrails

Lumonox MVP is diagnosis-first and low-config. If a change adds observability-engineering complexity, discuss it before implementation.
