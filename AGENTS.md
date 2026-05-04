# AGENTS.md — AutoPulse

Guidance for AI coding agents and humans pairing with them in this repository.

## Read first

1. **[DEVELOPMENT.md](./DEVELOPMENT.md)** — Product scope, architecture, event model, security, build order, definition of MVP done.
2. **[agents/README.md](./agents/README.md)** — Workflow index and how to invoke playbooks.

## Cursor-specific

- **[docs/cursor/CURSOR_DEVELOPMENT.md](./docs/cursor/CURSOR_DEVELOPMENT.md)** — Rules layout, repo map, suggested chat patterns.
- **[docs/cursor/WORKFLOWS.md](./docs/cursor/WORKFLOWS.md)** — Quick links to all agent workflows.
- **`.cursor/rules/`** — Persistent constraints (always-on set and path-scoped rules); see **Always-on rules** in [`docs/cursor/CURSOR_DEVELOPMENT.md`](./docs/cursor/CURSOR_DEVELOPMENT.md).

## When to use which workflow

| Situation | Workflow |
|-----------|----------|
| Implementing a feature or fix | [`agents/implement-task.md`](./agents/implement-task.md) |
| Pre-merge or ad-hoc code review | [`agents/review.md`](./agents/review.md) |
| Dashboard or onboarding UX | [`agents/ui-ux-analysis.md`](./agents/ui-ux-analysis.md) |
| Ingestion, SDK capture, auth, storage | [`agents/security-privacy.md`](./agents/security-privacy.md) |

## Slash commands (optional)

Cursor commands in `.cursor/commands/` mirror these workflows for quicker invocation.

## Repo layout (high level)

| Path | Purpose |
|------|---------|
| `sdk/` | Python SDK and FastAPI middleware |
| `backend/` | FastAPI ingestion, dashboard API, workers |
| `frontend/` | Next.js dashboard |
| `agents/` | Agent/human workflow markdown |
| `docs/cursor/` | Cursor development documentation |

## Defaults for agents

- Prefer **minimal diffs** and preserve existing style.
- SDK and network failures must **not** take down user applications.
- If product scope conflicts with a request, **cite DEVELOPMENT.md** and ask before proceeding.
