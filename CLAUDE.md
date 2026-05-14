# CLAUDE.md — Lumonox

Guidance for Claude Code in this repository. Mirrors the rules system maintained for Cursor under `.cursor/rules/` and the tool-agnostic playbooks under `agents/`.

## Canonical sources (read when scope / security / conventions are in play)

| Path | Role |
|------|------|
| `DEVELOPMENT.md` | Product scope, MVP, architecture, event model, security defaults. **Source of truth** when scope is ambiguous. |
| `AGENTS.md` | Entry point and workflow router (shared with humans and other agents). |
| `agents/README.md` + `agents/*.md` | Playbooks: `implement-task`, `review`, `ui-ux-analysis`, `security-privacy`. |
| `docs/DOCUMENTATION_GOVERNANCE.md` | When governed docs may be edited and approval rules. |
| `docs/DEVELOPMENT_PROCESS.md` | Delivery process, risk gates, release readiness. |
| `.cursor/rules/*.mdc` | Authoritative rule files. **Treat these as the rules-of-record** even though they live under `.cursor/`. |

The Cursor `.mdc` files are the canonical rules: always-on rules apply unconditionally; path-scoped rules apply when work touches matching paths. The path-scoped `CLAUDE.md` files in `backend/`, `frontend/`, `sdk/`, `scripts/` point Claude back at the relevant `.mdc` so the same rules govern both tools.

## Always-on constraints (condensed)

Detailed text lives in `.cursor/rules/*.mdc`; the rules below are non-negotiable and always apply.

### Product (`.cursor/rules/lumonox-product.mdc`)
- Lumonox = opinionated FastAPI-native observability for solo devs / teams of 1–5. **Not** a Grafana/Datadog/Sentry replacement.
- MVP must answer: *what broke, when, which requests led to it.*
- Non-goals: distributed tracing, custom dashboard builder, query language, complex alerting, k8s/multi-cloud, log pipelines, full APM, enterprise RBAC/audit.
- Dashboard principle: optimize for **fast diagnosis**, not configurability. Five-second understanding on overview.
- Product rule: if a feature requires observability-engineering expertise to use, it does not belong in MVP. When scope is ambiguous, defer to `DEVELOPMENT.md`.

### Engineering (`.cursor/rules/lumonox-engineering.mdc`)
- **SDK must never break the host app** when Lumonox is misconfigured/down/slow. Async/non-blocking hot path with bounded queue; drop when full. Silent failure by default; explicit debug mode only. Scrub sensitive data; on middleware exceptions capture then re-raise the original.
- **Backend**: keep `POST /ingest` fast, move heavy work off the request path. Authenticate API keys, store hashes only, validate/normalize events, attach server metadata.
- **Security defaults**: HTTPS in prod; conservative capture (no full bodies unless explicitly enabled).
- Prefer small focused diffs and consistent naming; do not expand scope without approval.

### Execution (`.cursor/rules/lumonox-execution.mdc`)
- Default to implementing requested changes directly; avoid long planning unless the user asks.
- Start with minimal context-gathering; avoid broad repo exploration unless required.
- In dirty git trees, never revert unrelated user changes — work around them.
- For substantive edits, run strict but scoped validation (lint + targeted tests).
- **Frontend completion**: when `frontend/` (or anything that ships in the static export) changes, run `npm run build` in `frontend/` before handoff. Skip only when the task scope explicitly excludes UI.
- If blocked, report concrete blocker + what was tried + smallest next step.
- Final responses always include **what changed**, **what was verified**, and **manual verification steps** (`.cursor/rules/post-task-manual-verification.mdc`).

### Debugging (`.cursor/rules/lumonox-debugging.mdc`)
- For vague reports ("doesn't work", "X never runs"), do not guess. Build a short repro, gather runtime evidence, then patch.
- Default repro stack: file-backed SQLite from `backend/.env` (unless clearly Postgres-only); backend from `backend/` validating `/health`, `/ready`, `/internal/metrics`; frontend from `frontend/` for UI issues.
- Use `logging` not `print`. Remove temporary probes/scratch scripts before handoff. Never log API keys, magic-link tokens, or full PII.
- After 3 failed attempts, summarize blocker + evidence + next action — do not retry blindly.

### Documentation & governance (`.cursor/rules/documentation-and-context.mdc`)
- Material updates to governed docs require **explicit maintainer approval** — see `docs/DOCUMENTATION_GOVERNANCE.md`. Do not rewrite canonical specs on assumption.
- Iterative refinement of `.cursor/rules/*.mdc` via the **Rules self-review** loop in `lumonox-execution.mdc` is encouraged for small clarity / convention improvements; material shifts to MVP or security need the governance path.
- New / transient docs (feature plans, roadmaps, spike notes) go under `docs/plans/`, not at the root of `docs/` and not beside governed docs.

### Pre-handoff review (`.cursor/rules/post-task-code-review.mdc`)
- Before finalizing, run a short review pass on changed files focused on: correctness regressions, security/privacy regressions (API keys, tokens, PII), hot-path performance (`POST /ingest`, SDK send path, dashboard critical loads), MVP scope drift, and missing tests.
- Report findings in the final response (ordered by severity) along with tests run and manual verification.

### Plan decomposition (`.cursor/rules/plan-to-task-conversion.mdc`)
- For multi-step plans (2+ meaningful tasks, cross-team deps, or production risk), use full task-card decomposition. For simple changes, return a compact execution plan instead — no heavy decomposition for trivial work.
- Standalone plan documents go under `docs/plans/`.

## Workflow router

| Situation | Use |
|-----------|-----|
| Implementing a feature or fix | `agents/implement-task.md` (also `/implement-task`) |
| Pre-merge or ad-hoc code review | `agents/review.md` (also `/review`); for isolated-context review delegate to the `code-reviewer` subagent |
| Dashboard or onboarding UX | `agents/ui-ux-analysis.md` (also `/ui-ux-analysis`) |
| Ingestion, SDK capture, auth, storage, scrubbing | `agents/security-privacy.md` (also `/security-privacy`) |
| Finishing a planned feature → commit + release | `.cursor/rules/plan-completion-commit-handoff.mdc` |

## Rule self-review

When work was substantive **and** one or more `.cursor/rules/*.mdc` files materially guided the approach: compare rule to reality, apply small clarity/convention edits to the rule in the same change series when practical, and mention the edit in the final response. Material shifts to MVP / security / workflow obligations are not silent doc tweaks — surface them and follow `docs/DOCUMENTATION_GOVERNANCE.md`. Full procedure in `.cursor/rules/lumonox-execution.mdc`.

## Repo layout

| Path | Purpose |
|------|---------|
| `sdk/` | Python SDK (PyPI: `lumonox-sdk`): FastAPI middleware + opt-in Django adapter (`[django]` extra). Core/adapter split — see `sdk/docs/adapters.md` |
| `backend/` | FastAPI ingestion, dashboard API, workers (PyPI: `lumonox`) |
| `frontend/` | Next.js dashboard; default delivery is the **static export** (`npm run build` → `frontend/out/`) mounted at `/lumonox/ui/` by the backend |
| `scripts/` | Local stack and ops scripts |
| `agents/` | Tool-agnostic playbooks |
| `docs/` | Permanent docs; `docs/plans/` for transient |
| `.cursor/rules/`, `.cursor/commands/` | Cursor rules + commands (authoritative rule files) |
| `.claude/commands/`, `.claude/agents/` | Claude slash commands + subagents (mirrors Cursor commands) |

Python tooling (Ruff, Mypy, Bandit, pytest, pre-commit) is configured at repo root in `pyproject.toml` and run via **`uv`** (workspace members: `sdk/`, `backend/`).
