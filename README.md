# AutoPulse

Opinionated observability for FastAPI applications. Product scope, architecture, and MVP definition live in **[DEVELOPMENT.md](./DEVELOPMENT.md)**.

## Repository layout

| Path | Contents |
|------|----------|
| `sdk/` | Python SDK (installable package `autopulse`) |
| `backend/` | FastAPI ingestion, dashboard read API, alert/retention jobs |
| `frontend/` | Next.js dashboard application (overview, logs, diagnosis, alerts) |
| `agents/` | Implementation, review, and analysis playbooks |
| `docs/cursor/` | Editor-specific development notes |

Contributor entry point: **[AGENTS.md](./AGENTS.md)**.
Execution guide: **[docs/DEVELOPMENT_PROCESS.md](./docs/DEVELOPMENT_PROCESS.md)**.

## Local development

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
NEXT_PUBLIC_AUTOPULSE_API_BASE_URL=http://localhost:8000
NEXT_PUBLIC_AUTOPULSE_API_KEY=<project_api_key>
```

Background jobs (`uv run python -m autopulse_backend.jobs alerts-once`) print the **number of alert dispatches** for that run. A line showing `0` means no spike or outage alert was sent in that pass (for example no projects, traffic below configured thresholds, cooldown, or `ALERTS_ENABLED=false`), not that the command crashed. The CLI process still exits with status `0`.

Backend tests that touch Postgres need `BACKEND_TEST_DATABASE_URL` (see CI workflow services).

## MVP dashboard parity snapshot

The frontend tracks `DEVELOPMENT.md` dashboard requirements:

- Overview: requests/minute, error rate, average latency, volume chart, top failing routes, recent errors.
- Logs: time, method, path, status, latency, service, environment.
- Diagnosis: grouped errors with type/message/route/count/first/last seen and sample stack.
- Alerts: heuristic visibility and runbook actions (minimal in-app settings remain backend-dependent).

## Tooling and quality gates

- Python **3.11+**, package and workspace management with **[uv](https://docs.astral.sh/uv/)**.
- Node.js for the `frontend/` dashboard.
- **pre-commit** for Ruff, Bandit, and basic hygiene.
- **GitHub Actions** for Python and frontend CI on push and pull request.

```bash
uv sync --group dev
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run bandit -c pyproject.toml -r sdk/src/autopulse
uv run pytest
```

```bash
npm --prefix frontend run lint
npm --prefix frontend run typecheck
npm --prefix frontend run test
```

Install git hooks (once per clone):

```bash
uv run pre-commit install
```
