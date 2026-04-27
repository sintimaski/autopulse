# Cursor development — AutoPulse

This file explains how this repo uses Cursor: rules, agent playbooks, and which documents should inform work.

## Canonical sources

| Path | Role |
|------|------|
| `DEVELOPMENT.md` | Product scope, MVP, architecture, event model, security defaults. **Source of truth** when scope is ambiguous. |
| `docs/DOCUMENTATION_GOVERNANCE.md` | When documentation may be edited and approval requirements. |
| `AGENTS.md` | Entry point for humans and agents; links to `agents/`. |
| `agents/*.md` | Playbooks: implement, review, UI/UX, security. |

## Rules layout (`.cursor/rules/`)

Rules use `.mdc` files with YAML frontmatter:

- `alwaysApply: true` — loaded for relevant sessions; use for product constraints and doc-governance reminders.
- `globs: ...` — apply when files matching the pattern are in context.

Keep rules **short and enforceable**. Product nuance belongs in `DEVELOPMENT.md`, not duplicated at length in rules.

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
| Dashboard | `frontend/` |

Tooling (Ruff, Mypy, Bandit, pytest, pre-commit) runs from the repo root via `uv`.

## Commands (optional)

Slash-style command snippets live under `.cursor/commands/` and mirror the playbooks in `agents/` for quick reference.
