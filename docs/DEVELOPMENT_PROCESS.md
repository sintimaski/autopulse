# Lumonox Detailed Development Process

This document defines execution and release-readiness practices for this repository.

Precedence rule:

- `DEVELOPMENT.md` remains the product and engineering source of truth.
- This document is an execution guide (quality gates, workflows, MVP and release checks).
- If any wording here conflicts with `DEVELOPMENT.md`, follow `DEVELOPMENT.md`.

## 1) Operating Principles

- Keep scope inside the MVP promise: answer what broke, when, and which requests led to it.
- Do not add features that force users to think like observability engineers.
- Protect the host application first: SDK code must stay async, non-blocking, and bounded.
- Keep ingestion fast and push expensive work to background processing as the system grows.
- Use conservative data capture defaults and scrub sensitive fields before transmission.
- Store API keys hashed (never plaintext), and treat auth/scrubbing behavior as release gates.

## 2) Development Environment and Quality Gates

Run from repository root:

```bash
uv sync --group dev
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run bandit -c pyproject.toml -r sdk/src/lumonox -r backend/src/lumonox_backend
uv run pytest
npm --prefix frontend run lint
npm --prefix frontend run typecheck
npm --prefix frontend run test
npm --prefix frontend run build
```

Optional local setup:

```bash
uv run pre-commit install
uv run pre-commit run --all-files
```

Pre-commit runs **`frontend-build`** when staged paths include **`frontend/`**: Next **`npm run build`** so the static export stays valid.

Execution policy:

- Run targeted tests during implementation (`uv run pytest sdk/tests/...`) for speed.
- Run full root checks before merge.
- For security-sensitive changes, always include Bandit and a manual scrub/auth review.

## 3) Default Per-Task Workflow (Cross-Cutting)

Use this workflow for every feature/fix, aligned with `agents/implement-task.md`:

1. Understand and restate request, assumptions, and touchpoints.
2. Analyze package boundaries, hot-path risk, trust-boundary crossings, and test plan.
3. Sketch smallest viable design and rollback path.
4. Implement in one vertical slice when possible.
5. Verify with targeted tests and full static checks.
6. Prepare handoff with clear risk notes and verification evidence.
7. Present a concise user update covering all changed files and the main points before finalizing.
8. Commit only after implementation is complete and verification checks pass.

When to use specialized playbooks:

- Security/privacy-sensitive work: `agents/security-privacy.md`
- Dashboard/onboarding/user-facing workflows: `agents/ui-ux-analysis.md`
- Pre-merge and regression review: `agents/review.md`

## 4) Build order, jobs, and planning pointers

- **Build order (steps 1–16):** use `DEVELOPMENT.md` as the only authoritative sequencing; do not maintain parallel milestone checklists here.
- **Multi-step initiatives:** use `docs/DEVELOPMENT_PLAN_TASK_TEMPLATE.md` for task cards; put disposable initiative writeups under `docs/plans/` (see `docs/DOCUMENTATION_GOVERNANCE.md`).
- **Day-to-day implementation:** `agents/implement-task.md`.

**Operational jobs (local / cron-style):**

- One-off alert evaluation: `uv run python -m lumonox_backend.jobs alerts-once`
- One-off retention cleanup: `uv run python -m lumonox_backend.jobs retention-once`
- Optional in-process scheduler (dev): set `JOBS_ENABLE_SCHEDULER=true` and tune `JOBS_ALERT_INTERVAL_SECONDS` / `JOBS_RETENTION_INTERVAL_SECONDS`.
- SDK benchmark harness: `uv run pytest sdk/tests/test_benchmarks.py`

**Milestone shorthand (informative):** M1 SDK (steps 1–5) → M2 ingest (6–8) → M3 read API + dashboard shell (9–11) → M4 errors + aggregation (12–13) → M5 alerts + retention + hardening (14–16). Details live in `DEVELOPMENT.md`.

## 5) Test Strategy by Repository Phase

Current repository state:

- Active test packages: `sdk/tests`, `backend/tests`, and `frontend` Vitest suites.
- `frontend/` is an active Next.js dashboard application with overview/logs/diagnosis/alerts routes.

Scaling strategy:

- Keep SDK behavioral tests in `sdk/tests` from day one.
- Continue expanding `backend/tests` alongside ingest/read API growth.
- Keep frontend unit/smoke tests in `frontend/` and expand coverage as dashboard UX grows.
- Preserve root-level CI as the global gate while allowing local targeted loops.

Test taxonomy used across milestones:

- Unit tests: event construction, hashing, scrub functions, queue/sender internals.
- Integration/API tests: ingest auth, persistence, aggregation reads.
- UI tests: overview/request/error rendering, empty/error/loading states.
- Manual scenario tests: end-to-end first-value path and outage resilience.

## 6) MVP Completion Gate (Must Match DEVELOPMENT.md)

Treat MVP completion as a release gate, not a status note.
All checks below must pass in one verification cycle and include evidence links
(test output, screenshots, command snippets, or notes in the release PR description).

### 6.1 Required gate checks

- **One-line integration:** verify a clean FastAPI sample app (and a Django sample app, via the `[django]` extra) can enable Lumonox with one line and no extra observability configuration.
- **First value speed:** after generating traffic, requests are visible in the dashboard within a few seconds.
- **Error diagnosis:** induced exceptions are grouped and visible with stack traces.
- **Core overview signals:** request rate, error rate, and average latency are visible and numerically plausible.
- **Fail-silent SDK behavior:** when backend is unavailable, the host app still serves requests successfully.
- **Default scrubbing:** sensitive headers and common secret fields are scrubbed in captured payloads.
- **Alert baseline:** simple error spike emits an email alert.
- **Outage heuristic:** simple outage pattern emits an email alert.
- **Setup brevity:** onboarding/setup docs are concise enough for a new user to read in a few minutes.

### 6.2 MVP gate execution checklist

Run these checks in order from repository root:

```bash
uv sync --group dev
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run bandit -c pyproject.toml -r sdk/src/lumonox -r backend/src/lumonox_backend
npm --prefix frontend install
npm --prefix frontend run lint
npm --prefix frontend run typecheck
npm --prefix frontend run test
npm --prefix frontend run build
```

Then perform the manual MVP scenario:

1. Start `./scripts/run_synthetic_stack.sh` (or backend + synthetic app separately) and confirm the dashboard under `/lumonox/ui/` and ingest on the backend.
2. Generate normal and failing traffic.
3. Capture evidence for first-value time, grouped errors, and overview metrics.
4. Simulate backend outage and verify host app continuity.
5. Validate scrubbed payload output and alert dispatch behavior.
6. (Optional) run `./scripts/run_remote_stack.sh` hints with separate backend/frontend terminals.

### 6.3 MVP sign-off requirement

MVP is complete only when all checks in `6.1` are marked pass and all evidence from `6.2`
is attached to the milestone release PR.
Any failed check blocks MVP declaration until remediated.

## 7) Risk and Release Readiness Checks

Before each milestone release, run a structured risk review using the classes below.
Every class needs: current status (`pass`, `needs mitigation`, or `blocked`), evidence,
and an explicit owner when mitigation is required.

### 7.1 Required risk classes

- **SDK hot path performance risk:** latency regression in middleware/request path.
- **Reliability containment risk:** unbounded memory growth or retry storms during outages.
- **Data exposure risk:** sensitive leakage from header/body/query capture.
- **Auth boundary risk:** API-key/auth drift (hashed keys, project isolation, reject invalid credentials).
- **Transport/default security drift:** production HTTPS and conservative capture defaults.
- **Product scope drift:** dashboard complexity moving away from fast diagnosis.
- **Data lifecycle risk:** storage growth and retention-policy correctness.

### 7.2 Per-release readiness routine

For each milestone release:

1. Run full automated checks from section `6.2`.
2. Complete a manual risk walk for all classes in `7.1`.
3. Record mitigations, owners, and due dates for non-pass classes.
4. Confirm no unresolved `blocked` risks remain for MVP-critical behavior.
5. Add a short "release readiness" note to the PR describing residual risk.

### 7.3 Release decision rule

Release proceeds when:

- all automated checks pass,
- no `blocked` risks remain in the classes above,
- any `needs mitigation` risks have an owner and dated follow-up issue,
- and the release note includes residual-risk acknowledgment.

Keep mitigations aligned with `DEVELOPMENT.md` engineering-risk guidance.

## 8) Post-MVP and Deferred Work

Tracked but intentionally deferred from MVP completion:

- Background jobs and cron monitoring depth improvements.
- Smarter (adaptive) request sampling and richer route/status/error filtering.
- Local sidecar agent exploration.
- WebSocket-driven live dashboard updates **on by default** (the WS path ships behind `LUMONOX_DASHBOARD_REALTIME_ENABLED` / `LUMONOX_DASHBOARD_REALTIME_WS_ENABLED`, both off by default).
- Any distributed tracing, custom dashboard builders, or complex alert-rule systems.

Already shipped beyond MVP (no longer deferred): Slack / Discord / generic webhook alert channels (see `backend/ALERT_DELIVERY_RUNBOOK.md`), Django ASGI SDK adapter (`lumonox-sdk[django]`), per-request trace context, release/git markers, incident worksheet, operator pipeline health surface.

These are evaluated after MVP validation, not during MVP delivery.
