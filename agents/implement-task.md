# Playbook: implement a task

## Purpose

Turn a request into a **small, correct change** aligned with `DEVELOPMENT.md`, with explicit acceptance criteria before coding.

## Phase 1 — Understand and restate

1. Read the task literally; list **assumptions** separately from **facts** in the issue or message.
2. Open `DEVELOPMENT.md` sections that apply (MVP scope, SDK behavior, ingestion, dashboard, security).
3. Restate the task in one paragraph: **user-visible outcome** and **technical touchpoints** (paths, APIs).

**Stop if** the task conflicts with MVP or non-goals; summarize the conflict and ask for direction.

## Phase 2 — Task analysis

Answer briefly:

| Question | Notes |
|----------|-------|
| Which package? | `sdk/`, `backend/`, `frontend/`, or docs-only |
| Hot path? | If yes, async/non-blocking and bounded work only |
| Data crossing trust boundaries? | If yes, scrubbing, auth, hashing per `DEVELOPMENT.md` |
| Migrations or new env vars? | Document defaults; avoid breaking existing installs |
| Tests | What fails today without the change; what proves the fix |

## Phase 3 — Design sketch

- Prefer the **smallest** API or data model that satisfies the task.
- List **files likely to change** (max ~10); if more, consider splitting the task.
- Note **rollback** (feature flag, revert-only, or data backfill).

## Phase 4 — Implementation

1. Implement in **one vertical slice** when possible (types → logic → tests).
2. Match local style: imports, naming, error handling patterns in sibling code.
3. SDK rule: never break the host app; swallow or drop with bounds; re-raise user exceptions after capture.

## Phase 5 — Verification

- Run targeted tests: `uv run pytest` (narrow path if large suite).
- Run linters: `uv run ruff check`, `uv run ruff format --check`, `uv run mypy` as configured.
- For security-sensitive paths: `uv run bandit -c pyproject.toml -r sdk/src/autopulse -r backend/src/autopulse_backend`.

## Phase 6 — Handoff

- PR description: **what**, **why**, **how verified**, **risk** (one line).
- If behavior changed for integrators, say so explicitly.
- Provide a concise end-of-task summary of all changed files and key outcomes so maintainers can catch up quickly.
- Treat commit creation as a post-implementation step: commit only after code and verification are complete.

## Checklist (quick)

- [ ] Scope matches `DEVELOPMENT.md` MVP or explicitly approved stretch
- [ ] No new “observability engineer” configuration surface unless approved
- [ ] Sensitive defaults unchanged or tightened, not loosened, unless approved
- [ ] Tests or clear manual steps included
- [ ] Governed docs updated only with approval per `docs/DOCUMENTATION_GOVERNANCE.md`
