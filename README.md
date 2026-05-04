# AutoPulse

Opinionated observability for FastAPI applications. Product scope, architecture, and MVP definition live in **[DEVELOPMENT.md](./DEVELOPMENT.md)**.

## Repository layout

| Path | Contents |
|------|----------|
| `sdk/` | Python SDK (installable package `autopulse`) |
| `backend/` | FastAPI ingestion, dashboard read API, alert/retention jobs |
| `frontend/` | Next.js dashboard application (overview, requests, diagnosis, alerts) |
| `agents/` | Implementation, review, and analysis playbooks |
| `docs/cursor/` | Editor-specific development notes |

Contributor entry point: **[AGENTS.md](./AGENTS.md)**.
Execution guide: **[docs/DEVELOPMENT_PROCESS.md](./docs/DEVELOPMENT_PROCESS.md)**.

**Troubleshooting (DuckDB “has data” but dashboard shows zeros):** relative `AUTOPULSE_DUCKDB_PATH` is resolved against the **data root** (repo root in a checkout, or `AUTOPULSE_DATA_DIR`), not your shell cwd. If you still see mismatches, set `AUTOPULSE_DUCKDB_PATH` to an absolute file path and confirm startup logs print `Startup settings [event_store]: … duckdb_path=…`.

## Product vs local validation (read this once)

- **Hosted / split stack** is the long-term production shape: dashboard session auth, `POST /ingest` from customer apps, and multi-instance deployment concerns. Start with **[docs/ops/PRODUCTION_DEPLOYMENT.md](./docs/ops/PRODUCTION_DEPLOYMENT.md)** (canonical rollout + SLO gates), then **[docs/ops/DEPLOYMENT_MULTI_INSTANCE.md](./docs/ops/DEPLOYMENT_MULTI_INSTANCE.md)** for horizontal scale caveats.
- **Embedded + synthetic fixture** in this repo is the fastest way to validate SDK + static UI + ingest together; it is not a substitute for production operations. **[DEVELOPMENT.md](./DEVELOPMENT.md)** defines MVP scope and “done”; see **[docs/ops/BACKUP_RESTORE.md](./docs/ops/BACKUP_RESTORE.md)** for durable state.

## Local development

Single-app embedded flow (recommended for SDK + dashboard manual validation):

```bash
uv sync --group dev
npm --prefix frontend install
cp backend/.env.example backend/.env   # once; edit email etc.
# First boot creates repo-root .env.autopulse (ingest + NEXT_PUBLIC_*). Then:
npm --prefix frontend run build        # or use scripts/run_synthetic_stack.sh (sources .env.autopulse)
uv run uvicorn autopulse.fixtures.synthetic_test_app:app --host 0.0.0.0 --port 8000
```

First embedded `monitor()` boot writes **`.env.autopulse`** (gitignored) with `AUTOPULSE_EMBEDDED_API_KEY` and matching `NEXT_PUBLIC_*` for static UI. **`./scripts/run_synthetic_stack.sh`** sources `backend/.env` then **`.env.autopulse`** before `npm run build`, so the second run onward is mostly automatic. A one-shot startup ingest (`/.well-known/autopulse-onboarding`) runs unless `AUTOPULSE_EMBEDDED_STARTUP_INGEST=0`. Override path with `AUTOPULSE_ENV_AUTOPULSE_FILE`.

Embedded mode needs the **`autopulse-backend`** distribution (not yet a separate PyPI install for every workflow). Use either:

```bash
pip install "autopulse[embedded]"
```

…when your index has **both** packages (e.g. after they are published), **or** from a clone build both wheels then:

```bash
./scripts/build_sdk_release_wheels.sh
pip install dist/wheels/autopulse_backend-*.whl dist/wheels/autopulse-*.whl
```

Remote-only ingest works with **`pip install autopulse`** alone.

Then generate fixture traffic:

```bash
uv run python -m autopulse.fixtures.synthetic_load --base-url http://localhost:8000 --duration-seconds 120 --rps 8 --role-mode mixed
```

Embedded endpoints are available under `http://localhost:8000/autopulse/*`.

Split backend/frontend flow (for backend or frontend-only iteration):

Backend (from repository root):

```bash
uv sync --group dev
uv run python -m autopulse_backend.main
```

Frontend (in a separate terminal):

```bash
npm --prefix frontend install
npm --prefix frontend run dev
```

Set frontend environment variables in `frontend/.env.local`:

```bash
NEXT_PUBLIC_AUTOPULSE_API_BASE_URL=/autopulse
# Match repo-root .env.autopulse after first embedded boot, or set keys manually.
NEXT_PUBLIC_AUTOPULSE_API_KEY=ap_live_embeddedlocal_localdevsecret
```

For split mode, set:

```bash
NEXT_PUBLIC_AUTOPULSE_API_BASE_URL=http://localhost:8000
NEXT_PUBLIC_AUTOPULSE_API_KEY=<project_api_key>
```

Background jobs (`uv run python -m autopulse_backend.jobs alerts-once`) print the **number of alert dispatches** for that run. A line showing `0` means no spike or outage alert was sent in that pass (for example no projects, traffic below configured thresholds, cooldown, or `ALERTS_ENABLED=false`), not that the command crashed. The CLI process still exits with status `0`.

Operator recovery: `uv run python -m autopulse_backend.jobs replay-aggregate-dead-letters-once` reapplies aggregate payloads that exhausted the async ingest aggregate worker (see metrics/logs for `ingest.aggregate_worker.dead_lettered`).

Backend tests that touch Postgres need `BACKEND_TEST_DATABASE_URL` (the CI workflow runs both SQLite and Postgres lanes).

## MVP dashboard parity snapshot

The frontend tracks `DEVELOPMENT.md` dashboard requirements:

- Overview: requests/minute, error rate, average latency, volume chart, top failing routes, recent errors.
- Requests: time, method, path, status, latency, service, environment.
- Diagnosis: grouped errors with type/message/route/count/first/last seen and sample stack.
- Alerts: heuristic visibility and runbook actions (minimal in-app settings remain backend-dependent).
- Guardrail: advanced SQL WHERE toolbar controls are disabled by default; enable only for internal diagnostics via `NEXT_PUBLIC_AUTOPULSE_ADVANCED_QUERY_UI=1`.

## Tooling and quality gates

- Python **3.11+**, package and workspace management with **[uv](https://docs.astral.sh/uv/)**.
- Node.js for the `frontend/` dashboard.
- **pre-commit** for Ruff, Bandit, frontend lint/typecheck/build, and basic hygiene.
- **GitHub Actions** for Python and frontend CI on push and pull request.

```bash
uv sync --group dev
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run bandit -c pyproject.toml -r sdk/src/autopulse -r backend/src/autopulse_backend
uv run pytest
```

```bash
npm --prefix frontend run lint
npm --prefix frontend run typecheck
npm --prefix frontend run test
npm --prefix frontend run build
```

Install git hooks (once per clone):

```bash
uv run pre-commit install
uv run pre-commit run --all-files
```
