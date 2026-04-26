# AutoPulse

Opinionated observability for FastAPI applications. Product scope, architecture, and MVP definition live in **[DEVELOPMENT.md](./DEVELOPMENT.md)**.

## Repository layout

| Path | Contents |
|------|----------|
| `sdk/` | Python SDK (installable package `autopulse`) |
| `backend/` | Reserved for ingestion and dashboard API |
| `frontend/` | Reserved for the Next.js dashboard |
| `agents/` | Implementation, review, and analysis playbooks |
| `docs/cursor/` | Editor-specific development notes |

Contributor entry point: **[AGENTS.md](./AGENTS.md)**.

## Tooling

- Python **3.11+**, package and workspace management with **[uv](https://docs.astral.sh/uv/)**.
- **pre-commit** for Ruff, Bandit, and basic hygiene.
- **GitHub Actions** for CI on push and pull request.

```bash
uv sync --group dev
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run bandit -c pyproject.toml -r sdk/src/autopulse
uv run pytest
```

Install git hooks (once per clone):

```bash
uv run pre-commit install
```
