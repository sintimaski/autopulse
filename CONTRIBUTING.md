# Contributing

Thanks for contributing to AutoPulse.

## First read

- `DEVELOPMENT.md` (product + engineering source of truth)
- `docs/DEVELOPMENT_PROCESS.md` (execution and release gates)
- `docs/DOCUMENTATION_GOVERNANCE.md` (governed docs policy)
- `AGENTS.md` (workflow pointers)

## Local setup

From repository root:

```bash
uv sync --group dev
npm --prefix frontend install
```

## Validation before PR

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run bandit -c pyproject.toml -r sdk/src/autopulse -r backend/src/autopulse_backend
uv run pytest
npm --prefix frontend run lint
npm --prefix frontend run typecheck
npm --prefix frontend run test
```

## PR expectations

- Keep changes small and focused.
- Include tests (or explicit manual verification notes) for behavior changes.
- Call out security-sensitive changes (auth, keys, scrubbing, ingestion limits) in PR description.
- Do not expand scope beyond requested task without explicit approval.

## Scope guardrails

AutoPulse MVP is diagnosis-first and low-config. If a change adds observability-engineering complexity, discuss it before implementation.
