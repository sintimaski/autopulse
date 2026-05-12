# Production maturity initiative — task plan

This document follows `docs/DEVELOPMENT_PLAN_TASK_TEMPLATE.md`.

## 1) Plan header

- **Plan name:** Production maturity — HA ingest, operator UX, SDK hardening
- **Owner:** (assign)
- **Date:** 2026-05-12
- **Status:** Draft
- **Scope summary (2-4 lines):** Close the gap between “works well for MVP” and “safe and operable in multi-replica production.” Focus on replica-safe ingest/event storage story, unified operator health surface, SDK reliability and observability, and day-2 product flows (incidents, alerting, correlation).
- **Out of scope:** Full distributed tracing product, custom dashboard builder, enterprise audit/compliance suite, Kubernetes-specific operators (unless explicitly pulled in as docs only).

## 2) Context / background

- **Problem statement:** Teams need confidence that ingest and storage behave correctly under HA, that operators can see system health without hunting multiple pages, and that the SDK does not silently lose critical signals without visibility.
- **Why now:** Product direction targets real production use; documented topology constraints (e.g. DuckDB multi-writer) and best-effort SDK drops need explicit product/engineering closure.
- **Current behavior (as-as):** Ingest and aggregates work; embedded and single-writer paths are strong; multi-replica and event-plane choices require careful ops alignment; UI triage is strong but incident and health surfaces are fragmented; SDK is fail-safe but best-effort with limited self-metrics.
- **Desired behavior (to-be):** One documented HA golden path; measurable ingest and pipeline health in one place; SDK byte-budget and version correctness; lightweight incident and alert lifecycle suitable for small teams.
- **User impact:** Faster confidence during incidents, fewer silent gaps, clearer onboarding to production topology.
- **Technical impact:** Possible new deployment modes, metrics, API fields for releases/incidents, and documentation/runbook updates.

## 3) Domain rules and constraints

- **Product/domain rules:** Align with `DEVELOPMENT.md` — diagnosis-first, low configuration, avoid observability-engineer-only UX.
- **Security/privacy rules:** No plaintext secrets in logs; scrubbing defaults preserved; auth and API key handling unchanged in spirit (hashes only server-side).
- **Performance/SLO constraints:** Ingest path stays fast; heavy work off request path; bounded queues and explicit drop behavior when applicable.
- **Compliance/governance constraints:** Governed doc changes go through `docs/DOCUMENTATION_GOVERNANCE.md`; this file stays under `docs/plans/` until promoted.
- **Non-goals:** Full Datadog-style APM, arbitrary query language as primary UX, complex RBAC/audit products in this phase.

## 4) Inputs, outputs, and dependencies

- **Inputs:** `DEVELOPMENT.md`, `docs/ops/PRODUCTION_DEPLOYMENT.md`, `docs/ops/DEPLOYMENT_MULTI_INSTANCE.md`, `docs/ops/ADR_EVENT_STORE_SCALING.md` (if present), backend ingest/event store modules, `sdk/` monitor and jobs, frontend dashboard shell and settings.
- **Outputs:** Code and tests where tasks require it; runbook updates under `docs/ops/` where durable; optional contract notes under `docs/contracts/` if ingest/API behavior changes.
- **Dependencies:** Decision on canonical HA topology (single-writer vs queue-backed vs object-store path); staging environment for multi-replica validation.
- **Tools available:** CI, backend and frontend test suites, local compose or documented dev stack, metrics endpoints already exposed for internal diagnostics.

## 5) Task breakdown

### Task `PROD-001`: HA ingest and event-store golden path (architecture + docs)

- **Description:** Define and document the supported production topology for multi-replica ingest and event durability. Close gaps between code, ADRs, and `DEPLOYMENT_MULTI_INSTANCE.md` so operators have one clear path.
- **Priority:** P0
- **Acceptance criteria (AC):**
  - AC1: Single canonical HA deployment story is documented (what scales, what must not, and failure modes).
  - AC2: Dangerous combinations are rejected or warned at startup where feasible, with links to docs.
  - AC3: Rollout/rollback notes exist for switching modes (even if “not supported without migration”).
- **Inputs:** Existing ops docs, ADR(s), `backend` config validation.
- **Outputs:** Updated `docs/ops/*.md` and/or ADR; code changes to validation if needed.
- **Dependencies:** Maintainer sign-off on chosen golden path.
- **Constraints:** Must not silently weaken security defaults.
- **Tools available:** Doc review, config tests.
- **Steps / plan:**
  1. Inventory current supported topologies and blockers.
  2. Pick primary HA story for next release cycle.
  3. Align docs and validation with that story.
  4. Add operator checklist to production deployment doc.
- **Error handling:**
  - **Expected failure modes:** Misconfiguration at deploy time.
  - **Recovery steps:** Fix env; restart with corrected topology.
  - **Rollback/backout conditions:** Revert to previous single-writer topology if HA path incomplete.
- **Validation / verification:**
  - **Automated checks:** Tests for `validate_deployment_settings` (or equivalent) if extended.
  - **Manual checks:** Two-replica smoke with documented env; confirm no DuckDB concurrent writers if forbidden.
  - **Observed evidence:** Logs/metrics show expected single-writer or bus behavior.
- **Idempotency (re-run safety):**
  - **Safe to re-run?** Yes (doc + validation only iterations).
  - **If partial/no, guardrails required:** N/A
- **State / progress tracking:**
  - **Status:** Todo
  - **% complete:**
  - **Last update:**
  - **Owner:**
- **Related documents:** `docs/ops/DEPLOYMENT_MULTI_INSTANCE.md`, `docs/ops/PRODUCTION_DEPLOYMENT.md`
- **References / examples:** Existing runbooks in `docs/ops/`, `docs/runbooks/`
- **Ambiguity handling:**
  - **If requirement is unclear:** Default to documented single-writer + scale-out read until queue/object path is ready.
  - **If data conflicts:** Escalate to owner; do not merge conflicting topology claims.
  - **Escalation owner:** (assign)
- **Observability (logs, tracking):**
  - **Logs/metrics/traces to add:** Topology guardrail metrics if not already present.
  - **Alert thresholds:** (define per staging evidence)
  - **Success signals:** No conflicting writers; healthy ingest rate on all replicas where allowed.

---

### Task `PROD-002`: Unified operator health surface (backend + UI)

- **Description:** Aggregate scheduler, retention, realtime bus, ingest pressure, and alert-delivery health into one operator-facing view (API + dashboard), reusing existing internal metrics where possible.
- **Priority:** P0
- **Acceptance criteria (AC):**
  - AC1: One dashboard route (or overview section) lists key subsystems with green/yellow/red or explicit “unknown.”
  - AC2: Deep links to existing settings diagnostics remain available from each row.
  - AC3: Permissions match existing dashboard auth model.
- **Inputs:** Internal metrics endpoints, settings UI patterns, `OperatorReliabilityCallout` behavior.
- **Outputs:** New API slice or aggregated endpoint; UI section; tests.
- **Dependencies:** PROD-001 clarity (what “healthy” means per topology).
- **Constraints:** Avoid duplicating heavy queries on every navigation; cache or batch server-side.
- **Tools available:** Frontend build, backend tests, manual UI pass.
- **Steps / plan:**
  1. Define minimal health schema (fields + semantics).
  2. Implement aggregation in backend.
  3. Add UI section and links.
  4. Add smoke test or contract test for health payload.
- **Error handling:**
  - **Expected failure modes:** Subsystem unreachable; partial data.
  - **Recovery steps:** Show degraded state; link to diagnostics.
  - **Rollback/backout conditions:** Feature flag or revert UI section.
- **Validation / verification:**
  - **Automated checks:** Unit/API tests for aggregator; optional Playwright smoke.
  - **Manual checks:** Induce degraded state in staging; UI matches.
  - **Observed evidence:** Screenshots or staging notes in task comments.
- **Idempotency (re-run safe):** Partial — deploy safe; data migration N/A unless new tables.
- **State / progress tracking:** **Status:** Todo | **Owner:**
- **Related documents:** `docs/ops/PRODUCTION_DEPLOYMENT.md`
- **Ambiguity handling:** If a subsystem has no signal yet, show “not configured” not false green.
- **Observability:** Reuse existing metrics; add counters for health endpoint latency if needed.

---

### Task `PROD-003`: SDK — correct version metadata and ingest compatibility

- **Description:** Ensure SDK reports a reliable package version to ingest (distribution name vs import name); document FastAPI/Starlette/httpx compatibility expectations.
- **Priority:** P0
- **Acceptance criteria (AC):**
  - AC1: Ingest receives non-`unknown` `sdk_version` for standard `lumonox-sdk` installs.
  - AC2: `sdk/README.md` states version reporting and upgrade policy.
  - AC3: Regression test covers version string.
- **Inputs:** `sdk/pyproject.toml`, `sdk/src/lumonox/_monitor.py` (or equivalent), ingest schema.
- **Outputs:** Code fix, tests, README.
- **Dependencies:** None.
- **Constraints:** No blocking on hot path; keep fail-safe sends.
- **Tools available:** `pytest` in `sdk/`.
- **Steps / plan:** Implement fallback resolution → test → document.
- **Error handling:** If metadata unavailable, document explicit fallback string behavior.
- **Validation / verification:** Automated: sdk tests; Manual: install wheel in clean venv and inspect batch payload (debug server or log).
- **Idempotency:** Yes — code deploy.
- **State / progress tracking:** **Status:** Todo | **Owner:**
- **Related documents:** `DEVELOPMENT.md` (SDK behavior), `docs/contracts/ingest-api.md`
- **Observability:** Version field visible in ingest records for support.

---

### Task `PROD-004`: SDK — batch byte budget and split policy

- **Description:** Cap serialized batch size to align with server `ingest_max_request_bytes` (or configurable client max); split or trim with documented rules to avoid 413 and silent drop storms.
- **Priority:** P0
- **Acceptance criteria (AC):**
  - AC1: Default behavior prevents typical large-stack batches from exceeding server limits.
  - AC2: Documented precedence: errors vs sampled requests under pressure if implemented.
  - AC3: Tests cover oversize batch splitting and edge cases.
- **Inputs:** Backend body size middleware config, ingest schema limits.
- **Outputs:** SDK changes, tests, README env vars.
- **Dependencies:** Accurate server default documented for alignment.
- **Constraints:** Preserve non-blocking behavior; avoid unbounded memory.
- **Tools available:** sdk tests, optional integration test against local backend.
- **Error handling:** Truncation policy explicit; no PII expansion.
- **Validation / verification:** Automated tests with mocked httpx; manual large payload run.
- **Idempotency:** Yes.
- **State / progress tracking:** **Status:** Todo | **Owner:**
- **Observability:** Optional counter hook for split/drop (ties to PROD-005).

---

### Task `PROD-005`: SDK — pressure metrics and optional hooks

- **Description:** Expose opt-in hooks or structured metrics for queue depth, drops, flush latency, and retry counts without default hot-path cost.
- **Priority:** P1
- **Acceptance criteria (AC):**
  - AC1: When disabled, no measurable overhead in microbenchmark or documented “negligible” path.
  - AC2: When enabled, caller can export to OpenTelemetry metrics or app logger in documented example.
  - AC3: Documented in `sdk/README.md`.
- **Inputs:** `_EventDispatcher` implementation.
- **Outputs:** Hook API + tests + doc snippet.
- **Dependencies:** PROD-004 optional for coherent “split” signals.
- **Constraints:** No secrets in hook payloads.
- **Validation / verification:** Unit tests with hook mock; manual enable in sample app.
- **Idempotency:** Yes.
- **State / progress tracking:** **Status:** Todo | **Owner:**
- **Observability:** This task is the observability surface for the SDK itself.

---

### Task `PROD-006`: SDK — sender concurrency and circuit breaker (resilience)

- **Description:** Reduce head-of-line blocking on single slow POST; add bounded concurrency and backoff/circuit behavior to protect apps and backend under sustained failure.
- **Priority:** P1
- **Acceptance criteria (AC):**
  - AC1: Configurable max in-flight requests with safe default.
  - AC2: Documented interaction with idempotency keys and retries.
  - AC3: Tests for stall scenarios (mocked slow server).
- **Inputs:** Current sender loop in SDK.
- **Outputs:** SDK code, tests, README.
- **Dependencies:** PROD-004 to avoid oversized parallel posts.
- **Constraints:** Must not violate “never take down user app” rule.
- **Validation / verification:** Load tests in CI if present; else documented manual script.
- **Idempotency:** Yes.
- **State / progress tracking:** **Status:** Todo | **Owner:**

---

### Task `PROD-007`: Incident mode (lightweight)

- **Description:** Named time window + title + optional notes + pinned links to error groups/requests; shareable URL; builds on bookmarks/scope patterns where possible.
- **Priority:** P1
- **Acceptance criteria (AC):**
  - AC1: User can create, view, and share an incident link.
  - AC2: Scope parameters restore diagnosis context consistently with existing routes.
  - AC3: Persistence model defined (local-only vs server-backed); if server-backed, migration + API + auth tests.
- **Inputs:** Bookmarks UI, URL scope utilities, dashboard API patterns.
- **Outputs:** Feature as agreed (MVP: server-backed or URL-only with optional local storage — **decide in execution**).
- **Dependencies:** Product decision on persistence.
- **Constraints:** Static export compatibility if feature ships in static UI.
- **Validation / verification:** E2E smoke for happy path; manual cross-browser check if critical.
- **Idempotency:** Partial if DB migrations — document migration rollback.
- **State / progress tracking:** **Status:** Todo | **Owner:**
- **Ambiguity handling:** If static export blocks server persistence, ship URL-encoded MVP first.

---

### Task `PROD-008`: Alerting — channel expansion and lifecycle (ack / mute / snooze)

- **Description:** Add at least one additional production channel (e.g. Slack or generic webhook) with test delivery; add mute/snooze/ack to reduce noise for small teams.
- **Priority:** P1
- **Acceptance criteria (AC):**
  - AC1: Channel configuration in settings with validation and test button.
  - AC2: Delivery history shows channel outcome; failures visible in health aggregation (PROD-002).
  - AC3: Mute/snooze/ack semantics documented (time scope, permissions).
- **Inputs:** Existing alert delivery services, settings UI.
- **Outputs:** Backend + UI + tests + ops note for secrets.
- **Dependencies:** Secrets handling review.
- **Constraints:** Rate limit outbound webhooks; no blocking ingest.
- **Validation / verification:** Integration test with webhook mock; manual Slack test in staging.
- **Idempotency:** Migrations if new tables — document rollback.
- **State / progress tracking:** **Status:** Todo | **Owner:**

---

### Task `PROD-009`: Release / deployment markers in UI

- **Description:** Ingest and display `release` / `git_sha` (or agreed fields) on overview and diagnosis charts as vertical markers or legend entries when present in events.
- **Priority:** P2
- **Acceptance criteria (AC):**
  - AC1: SDK or docs show how to set release metadata.
  - AC2: UI shows markers when data exists; empty state when not.
  - AC3: No chart breakage on sparse data.
- **Inputs:** Event model, overview chart components, SDK extra fields policy.
- **Outputs:** SDK doc + optional SDK helper; API if aggregation needed; UI.
- **Dependencies:** Schema and cardinality review.
- **Constraints:** Avoid high-cardinality explosion in aggregates.
- **Validation / verification:** Sample dataset test; manual UI check.
- **Idempotency:** Yes.
- **State / progress tracking:** **Status:** Todo | **Owner:**

---

### Task `PROD-010`: Saved team views and scoped export

- **Description:** Extend bookmarks or new “saved views” with project visibility; add bounded export (CSV/JSON) for scoped requests or error summary.
- **Priority:** P2
- **Acceptance criteria (AC):**
  - AC1: Role-gated create/list/delete for team views.
  - AC2: Export respects current filters and row limits; documented max rows.
  - AC3: Tests for auth and limit enforcement.
- **Inputs:** Bookmarks API, dashboard auth roles.
- **Outputs:** API + UI + tests.
- **Dependencies:** None critical.
- **Constraints:** Export must not stream unbounded memory; scrub sensitive columns per product defaults.
- **Validation / verification:** API tests + manual download check.
- **Idempotency:** Yes for code; migration rollback documented if new tables.
- **State / progress tracking:** **Status:** Todo | **Owner:**

---

### Task `PROD-011`: Query Explorer — curated templates

- **Description:** Ship a small library of safe, read-only templates with descriptions and “open in diagnosis” handoff where applicable.
- **Priority:** P2
- **Acceptance criteria (AC):**
  - AC1: At least N curated templates (set N during execution, suggest 5–10).
  - AC2: Each template documented with intent and parameters.
  - AC3: No templates encourage destructive SQL.
- **Inputs:** `QueryExplorerContent` (or equivalent), DuckDB access patterns.
- **Outputs:** UI data file + copy + tests if logic-heavy.
- **Dependencies:** None.
- **Constraints:** Align with MVP security (read-only expectations).
- **Validation / verification:** Manual run each template against dev data.
- **Idempotency:** Yes.
- **State / progress tracking:** **Status:** Todo | **Owner:**

---

### Task `PROD-012`: Onboarding completion nudge

- **Description:** Until first successful ingest (or checklist complete), show dismissible banner or nav entry to `/onboarding` per `OnboardingContent` milestones.
- **Priority:** P2
- **Acceptance criteria (AC):**
  - AC1: New projects see nudge; completed projects do not (definition of “completed” matches onboarding checklist).
  - AC2: Dismiss persists per browser or server as implemented and documented.
  - AC3: Does not block dashboard access.
- **Inputs:** `OnboardingContent`, `DashboardPageBoundary`.
- **Outputs:** UI change + tests if feasible.
- **Dependencies:** None.
- **Constraints:** Static export compatible.
- **Validation / verification:** E2E or manual journey from fresh org.
- **Idempotency:** Yes.
- **State / progress tracking:** **Status:** Todo | **Owner:**

## 6) Plan-level execution strategy

- **Delivery sequence:** PROD-001 → PROD-002 (parallel track: PROD-003, PROD-004) → PROD-005/006 → PROD-007/008 → P2 backlog (009–012).
- **Parallelization opportunities:** SDK tasks (003–006) parallel with backend health aggregation (002) once 001’s topology decision is stable; UI-only 011–012 can proceed with less coupling.
- **Risk register (top 3–5):**
  1. HA topology decision slips → blocks validation and health semantics.
  2. SDK byte budget misaligned with server defaults → false sense of safety until integration tested.
  3. Incident mode persistence choice wrong for static export → rework.
  4. Alert webhooks abused for SSRF or secret leakage → security review required.
  5. Release markers cause cardinality issues → needs aggregate design before UI polish.
- **Decision log:**

| Decision | Why | Date | Owner |
|----------|-----|------|-------|
| (pending) Canonical HA topology for next milestone | Must be explicit before marketing multi-replica | | |
| (pending) Incident MVP: URL-only vs server-backed | Trade shipping speed vs collaboration | | |

## 7) Validation gate before completion

Mark each item before closing the plan:

- [ ] All tasks have explicit AC.
- [ ] All tasks define validation (automated + manual).
- [ ] Idempotency is documented for each task.
- [ ] Domain rules and constraints are mapped to tasks.
- [ ] Observability updates are included where behavior changed.
- [ ] Related docs are updated or explicitly deferred.
- [ ] Remaining ambiguity is logged with owner and due date.
