# Cursor development — AutoPulse

This file explains how this repo uses Cursor: rules, agent playbooks, and which documents should inform work.

## Canonical sources

| Path | Role |
|------|------|
| `DEVELOPMENT.md` | Product scope, MVP, architecture, event model, security defaults. **Source of truth** when scope is ambiguous. |
| `docs/DOCUMENTATION_GOVERNANCE.md` | When documentation may be edited and approval requirements. |
| `AGENTS.md` | Entry point for humans and agents; links to `agents/`. |
| `agents/*.md` | Playbooks: implement, review, UI/UX, security (plus `agents/README.md` as workflow index). |

## Rules layout (`.cursor/rules/`)

Rules use `.mdc` files with YAML frontmatter:

- `alwaysApply: true` — loaded for relevant sessions; use for product constraints and doc-governance reminders.
- `globs: ...` — apply when files matching the pattern are in context.

Keep rules **short and enforceable**. Product nuance belongs in `DEVELOPMENT.md`, not duplicated at length in rules.

New `.mdc` files **must** include the **Rule self-review** footer defined under **New `.cursor/rules/*.mdc` files** in `.cursor/rules/autopulse-execution.mdc` (every rule except `autopulse-execution.mdc` itself, which hosts the full process).

For **bug hunts and “it doesn’t work”** reports, the always-on rule **`.cursor/rules/autopulse-debugging.mdc`** expects a **default repro** of file-backed SQLite from `backend/.env` (unless the issue is clearly Postgres-only), running backend/frontend when relevant, explicit repro steps and logs over guesses, and temporary probes removed before merge.

### Always-on rules (current)

These files use `alwaysApply: true` in Cursor:

| File | Role |
|------|------|
| `autopulse-execution.mdc` | Delivery workflow, rules self-review, template for new rules |
| `autopulse-product.mdc` | MVP boundaries and product filter |
| `autopulse-engineering.mdc` | SDK/backend/security engineering constraints |
| `autopulse-debugging.mdc` | Evidence-based debugging and default repro stack |
| `documentation-and-context.mdc` | Governed docs policy; when to read `DEVELOPMENT.md` |
| `post-task-manual-verification.mdc` | Final responses include manual verification steps |
| `post-task-code-review.mdc` | Pre-handoff review gate |

Other `.mdc` files are **path-scoped** (`globs`) for `sdk/`, `backend/`, `frontend/`, `scripts/`, tests, docs, synthetic stack, embedded bundle, etc. See the `.cursor/rules/` directory for the authoritative list.

## Automatic context

Always-on rules summarize **non-negotiables** (SDK must not break host apps, conservative capture, etc.) and point to `DEVELOPMENT.md` for detail.

When starting substantial work, agents should **read** `DEVELOPMENT.md` and the playbook under `agents/` that matches the task type, even if not every line is quoted back to the user.

## Chat attachments and @-mentions

In Cursor chats:

- Use **@DEVELOPMENT.md** when discussing scope, MVP, or security defaults.
- Use **@docs/DOCUMENTATION_GOVERNANCE.md** before editing governed docs.
- Use **@agents/implement-task.md** (or review / UI / security playbook) when running structured workflows.

Repository configuration cannot force a human to attach files; the combination of **always-on rules** plus **explicit @-mentions** is the intended way to keep context consistent.

## Where code will live

| Area | Path |
|------|------|
| Python SDK | `sdk/` |
| Backend API | `backend/` |
| Dashboard | `frontend/` (Next.js; static export is the default shipping path) |
| Agent / workflow docs | `agents/`, `docs/cursor/` |
| Local stack / ops scripts | `scripts/` |

Python tooling (Ruff, Mypy, Bandit, pytest, pre-commit) is configured in the **repo root** `pyproject.toml` and run via **`uv`** (workspace members: `sdk/`, `backend/`).

## Commands (optional)

Slash-style command snippets live under `.cursor/commands/` and mirror the playbooks in `agents/` for quick reference.
