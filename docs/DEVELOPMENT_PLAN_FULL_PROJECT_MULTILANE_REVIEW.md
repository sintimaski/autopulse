# AutoPulse Development Plan: Full Multi-Lane Product, UX, and Production Review

Use this plan as the single execution document for the full-lane audit follow-up across product design, CTO/production readiness, developer experience, and frontend UX/UI quality.

## 1) Plan header

- **Plan name:** Full multi-lane review closure plan
- **Owner:** CTO (primary), Product lead, Frontend lead, Backend lead, Ops owner
- **Date:** 2026-05-07
- **Status:** In progress
- **Scope summary (2-4 lines):** Consolidate all identified gaps from product, UX/UI, architecture, production operations, and developer workflow into a single prioritized plan. Execute fixes that improve first-value onboarding, incident diagnosis speed, production safety, and release confidence without expanding beyond MVP boundaries in `DEVELOPMENT.md`. Adds **operating model** (schedule, readiness matrix, promotion/rollback, metrics, observability ownership), **incident drills (T11)**, and **supportability diagnostics (T12)**.
- **Out of scope:** Full enterprise IAM/audit platform, custom dashboard builder, distributed tracing platform parity, multi-cloud orchestration system.

## 2) Context / background

- Problem statement: AutoPulse has strong core functionality and operations docs, but the shipped surface and production posture still contain mismatches and high-risk operator failure modes.
- Why now: The product is close to production-safe, and this is the lowest-cost moment to remove trust gaps, reduce UX friction, and harden deployment defaults before broader rollout.
- Current behavior (as-is): Core diagnosis flow exists and is usable; advanced features are visible in primary navigation; production runbooks are detailed; ingest and scheduler paths are resilient but operationally sensitive.
- Desired behavior (to-be): New users reach value quickly, core diagnosis remains the obvious path, production deployments are guardrailed and observable, and developers can ship safely with low friction.
- User impact: Faster time-to-first-value, clearer troubleshooting outcomes, fewer confusing states, and stronger confidence in production behavior.
- Technical impact: Targeted frontend UX changes, configuration guardrails, release/process hardening, and tighter validation around operations and data-plane consistency.

## 3) Domain rules and constraints

- Product/domain rules: Keep the MVP promise centered on "what broke, when, and what requests led to it"; prioritize diagnosis speed over configurability.
- Security/privacy rules: Keep conservative capture defaults, secure auth/session behavior, and never expose API keys/tokens/PII in logs.
- Performance/SLO constraints: Preserve fast ingest request path; keep heavy work in background jobs; bound queue/retry behavior.
- Compliance/governance constraints: Keep plan aligned with `DEVELOPMENT.md` and `docs/DOCUMENTATION_GOVERNANCE.md`; avoid introducing unsupported implementation promises.
- Non-goals: Scope expansion into enterprise observability platform capabilities.

## 4) Inputs, outputs, and dependencies

- **Inputs:** `DEVELOPMENT.md`, `docs/ops/PRODUCTION_DEPLOYMENT.md`, `docs/ops/DEPLOYMENT_MULTI_INSTANCE.md`, `docs/contracts/ingest-api.md`, frontend dashboard components/routes, backend config/lifecycle/ingest services, current release gate scripts.
- **Outputs:** prioritized implementation backlog, UX and IA changes, production hardening updates, runbook/checklist updates, verification evidence, **§5.1 operating model** (schedule/matrix/rollback/promotion), **T11** drill artifacts, **T12** operator diagnostics surfaces.
- **Dependencies:** frontend, backend, operations ownership; maintainer approval for governed documentation changes.
- **Tools available:** Cursor IDE, pytest/vitest/playwright, release gate scripts, health/metrics endpoints, staging environment.

## 5) Multi-lane findings summary (from review)

### Lane scorecard

- **Product strategy and scope fit:** Yellow
- **Frontend UX/UI and accessibility:** Yellow
- **Backend architecture and reliability:** Yellow
- **Production operations and deployment safety:** Yellow
- **Security readiness for MVP production:** Yellow
- **Developer QOL and release ergonomics:** Yellow

### Priority gap list (all lanes)

| ID | Gap | Lane | Priority | Impact |
|---|---|---|---|---|
| G01 | Ingest docs/status mismatch (`README` vs API contract) | Product trust | P0 | First-run confusion and support noise |
| G02 | Multi-instance/shared DuckDB topology risk | Production | P0 | Data integrity and availability risk |
| G03 | Scheduler/realtime/migration misconfiguration risk | Reliability/Ops | P0 | Silent retention/alerting failure |
| G04 | Primary nav overload vs diagnosis-first promise | Product + UX | P1 | Higher cognitive load, slower diagnosis |
| G05 | Modal/focus accessibility gaps in evidence flows | FE UX/UI | P1 | Incident workflow inaccessible for keyboard/SR users |
| G06 | Weak "first value" path due strict onboarding gate | Product + UX | P1 | Slower activation and trial abandonment |
| G07 | Eventual consistency visibility and recovery maturity | Backend/Ops | P1 | Stale views and operator toil |
| G08 | DX/release parity and automation gaps | Developer QOL | P2 | Slower iteration and avoidable regressions |
| G09 | Cron/job story not fully productized in UI | Product | P2 | Incomplete value for background-job-heavy apps |
| G10 | Hosted packaging/pricing UX not explicit | Product/GTM | P2 | Weak commercialization readiness |

## 5.1) Operating model: schedule, gates, metrics, and ownership

Calendar dates are owner-assigned; **week numbers are relative to plan kickoff** (Week 1 = first execution sprint).

### Master schedule (size, target, dependencies)

| Task | Size | Target | Depends on | Lane |
|------|------|--------|------------|------|
| T01 | S | Week 1 | — | Product + Backend |
| T05 | M | Week 1 | — | Backend + Ops |
| T02 | M | Week 2 | T01 | Frontend + Product |
| T04 | M | Week 2–3 | T02 (nav shell stable) | Frontend |
| T03 | M | Week 2–3 | T01 | Frontend + Product |
| T06 | M | Week 3–4 | T05 | Backend + Ops |
| T07 | M | Week 3–4 | T05 | Backend + Ops |
| T11 | M | Week 3–5 | T05, T06 | Ops + Backend |
| T12 | M | Week 4–6 | T05, T06 | Backend + Ops (+ FE surfaces) |
| T08 | S | Week 4–5 | T01 | DevEx |
| T09 | M | Week 4–6 | — (parallel once P0 started) | QA + Eng |
| T10 | S | Week 5–6 | T02, T03 | Product + Frontend |

**Sequencing notes:** T01 and T05 run in parallel Week 1. T02 follows ingest/onboarding trust alignment (T01) to avoid docs and IA diverging. T06/T07 and T11 depend on topology guardrails (T05). T10 is intentionally late so IA and first-value paths settle first.

### Production readiness matrix (environment behavior)

Single source for **what is allowed vs required** per environment. Implementation lives in config/startup (`T05`); this table is the contract operators and reviewers use.

| Capability | Dev | Staging | Production |
|------------|-----|---------|------------|
| Scheduler process | Optional | Required | Required |
| Shared / multi-writer DuckDB | Allowed (local only) | Warning + documented exception path | **Forbidden** (hard fail unless explicit single-writer profile documented and enforced) |
| TLS | No | Yes | Yes |
| Replay / recovery drill | Optional | Weekly target | **Mandatory** before release (`T11`) |
| Metrics endpoint (`/internal/metrics`) exposure | Open on loopback | Internal network only | Restricted (auth/network policy) |
| Unsafe topology (known-dangerous combo) | Warn | Hard fail or blocked deploy | **Hard fail startup** |
| Risky topology (degraded but supported) | Warn | Degraded `/ready` | Degraded `/ready` + alert |
| Non-ideal topology | Info/warn | Warn | Warn |

### Global rollback rules (plan-level)

Per-task rollback conditions remain; **in addition**, trigger a **release rollback or feature flag off** when post-deploy monitoring shows:

| Signal | Threshold (initial targets; tune with baselines) | Action |
|--------|--------------------------------------------------|--------|
| Onboarding funnel conversion (first event) | Drop **> 10%** vs 14-day rolling median after a nav/onboarding change | Rollback FE deploy or revert IA; investigate before retry |
| Auth / session failure rate | Spike **> 2×** baseline for 30 minutes | Rollback last auth/proxy/CORS change (`T07`) |
| Replay / repair lag | Exceeds agreed SLA (see metrics table: **p95 queue age > 10 min** sustained 15 min) | Rollback deploy that touched ingest/repair; scale workers if infra |
| Diagnosis p95 latency (dashboard API) | **> 25%** regression vs 7-day baseline after FE/API change | Rollback or hotfix; hold further FE releases |
| Release gate stability | Pass rate **< 95%** over 14 days | Stop feature merges; fix gates (`T09`) before next prod promotion |

Escalation: **CTO** owns go/no-go on production rollback; **Ops owner** executes runbook rollback steps.

### Staging promotion policy

| Gate | Requirement |
|------|-------------|
| Soak | **Minimum 24h** on staging after merge of release candidate (longer for auth/topology/nav changes) |
| Replay drill | Successful **replay recovery drill** logged (`T11`) for releases touching event plane / aggregates |
| Scheduler | **Failover or absence detection** validated in staging when scheduler topology changed |
| Frontend | **Smoke pass** (core journey + static export build) on RC |
| Release automation | **Release-gate green** on the exact SHA promoted |
| Sign-off | **CTO or delegate** (Backend lead for API/topology; Frontend lead for IA) signs promotion checklist |

Drills are **required before production** for changes in T05/T06/T11 scope; optional soak-only for doc-only releases.

### Lane definition of done (holistic closure)

Tasks may be “done” individually while a lane still fails. **Close a lane** only when all lane criteria below are met (in addition to task AC).

| Lane | Definition of done |
|------|---------------------|
| **Frontend** | Keyboard audit passes on diagnosis + requests flows (**0 critical** a11y blockers); mobile audit passes on same paths; new IA deployed with redirects/aliases verified; **no critical** regression bugs open; optional: onboarding activation **≥ baseline + 5pp** in staging cohort or A/B if available |
| **Ops / reliability** | Production readiness matrix satisfied for prod; `/ready` reflects degraded vs healthy accurately; **T11** drill evidence attached for release window; runbooks updated for new signals |
| **Security** | TLS + CORS + proxy trust validated; **MVP auth hygiene** checklist complete (see `T07`); **no Sev1** open items from security pass |
| **DX** | Documented **one-command** bootstrap works on supported matrix; release gate discoverable; **≤ 15 min** cold start to first local ingest (target) on reference machine |
| **Product** | Measurable metrics table (below) captured for two consecutive weeks or staging equivalent; no P0 trust gaps open |

### Product metrics (quantitative targets)

| Metric | Target | Owner |
|--------|--------|-------|
| Time to first event (signup → first ingested event, staging or prod cohort) | **< 5 min** p75 | Product |
| First-run success rate (completed ingest smoke path) | **> 90%** | Product + Backend |
| Keyboard accessibility blockers (critical path) | **0 critical** | Frontend |
| Replay recovery SLA (controlled drill: queue drained / aggregates consistent) | **< 10 min** | Ops |
| Release gate pass stability (main/RC pipeline) | **> 95%** over 14 days | QA |
| Unsafe topology in production | **0** (hard fail) | Backend + Ops |
| Diagnosis API p95 latency vs baseline | **No > 25% regression** after change | Backend + Frontend |

### Required product telemetry (minimum instrumentation)

Instrument **staging first**, then production where privacy allows. Ties to funnels below.

| Event / signal | Funnel / use |
|----------------|--------------|
| First event received (project-level) | Onboarding completion |
| First diagnosis view (errors/overview deep link) | Activation |
| Modal open / close completed without abandon | Diagnosis funnel |
| Jobs page sessions and time-to-first-action | Feature adoption |
| Search / filter with **zero results** | Failed search paths |
| Empty-state CTA click vs bounce | No-data dead-end |
| Replay / repair job outcomes (server-side) | Reliability funnel |

**Funnels to define in dashboard or analytics export:** onboarding (signup → key → first event); diagnosis (incident → evidence modal → resolution marker if present); jobs (landing → correlated error found).

### Observability ownership

| Area | Owner | Responder | Escalation |
|------|-------|-----------|------------|
| Alert routing (Pager/Ops channel) | Ops owner | On-call rotation or CTO | CTO if customer-visible **> 15 min** |
| Dashboards (queue, replay, freshness) | Backend lead | Backend | Ops if data plane |
| SLO / SLI review | CTO | Monthly cadence | Ad hoc after incident |
| `/ready` / topology semantics | Backend + Ops | Backend on-call | CTO for behavior contract changes |
| Frontend client errors (if collected) | Frontend lead | Frontend | Product if UX regression |

## 6) Task breakdown

### Task T01: Align ingest contract and onboarding trust signals

- **Description:** Resolve contract mismatches and first-run messaging so onboarding reflects actual API behavior and reliable success cues.
- **Priority:** P0
- **Acceptance criteria (AC):**
  - AC1: `README.md` ingest response expectations match `docs/contracts/ingest-api.md` and backend route status code.
  - AC2: Onboarding first-event guidance is accurate for current ingest and refresh behavior.
  - AC3: A quick smoke checklist validates first ingest without ambiguous interpretation.
- **Inputs:** `README.md`, ingest contract docs, backend ingest route, onboarding UI text.
- **Outputs:** updated docs/UI copy and verification notes.
- **Dependencies:** Backend and frontend leads.
- **Constraints:** No API contract changes unless explicitly approved.
- **Tools available:** docs edits, smoke scripts, staging verification.
- **Steps / plan:**
  1. Audit all user-facing references to ingest status/first event.
  2. Align wording to contract and live behavior.
  3. Add a short verification block for first-run success.
- **Error handling:**
  - Expected failure modes: stale docs in secondary pages.
  - Recovery steps: grep and reconcile all contract references in docs/UI.
  - Rollback/backout conditions: none (doc/copy only).
- **Validation / verification:**
  - Automated checks: docs lint (if configured), frontend build if UI copy changes.
  - Manual checks: run first ingest and confirm expected status + dashboard reaction.
  - Observed evidence: successful first-ingest checklist.
- **Idempotency (re-run safety):**
  - Safe to re-run? Yes
  - If partial/no, guardrails required: N/A
- **State / progress tracking:**
  - Status: Todo
  - % complete: 0
  - Last update: 2026-05-07
  - Owner: Product + Backend
- **Related documents:** `docs/contracts/ingest-api.md`, `README.md`
- **References / examples:** `backend/src/autopulse_backend/routes/ingest.py`
- **Ambiguity handling:**
  - If requirement is unclear: follow backend contract as source of truth.
  - If data conflicts: defer to route implementation + contract doc.
  - Escalation owner: CTO.
- **Observability (logs, tracking):**
  - Logs/metrics/traces to add: first-event server-side marker if not already present (privacy-safe aggregate only).
  - Alert thresholds: N/A
  - Success signals: first-run success rate **> 90%** in staged cohort; time-to-first-event **< 5 min** p75 (see §5.1 metrics).

### Task T02: Re-tier dashboard IA around diagnosis-first flow

- **Description:** Reorganize navigation and page hierarchy so core diagnosis pages are primary and advanced pages are progressively disclosed.
- **Priority:** P1
- **Acceptance criteria (AC):**
  - AC1: Primary nav highlights `Overview`, `Errors & Diagnosis`, and `Requests`.
  - AC2: Query/trace/power features are moved under explicit advanced grouping.
  - AC3: Existing deep links remain functional.
- **Inputs:** app shell/nav config, routing map, product rules in `DEVELOPMENT.md`.
- **Outputs:** updated IA/nav and migration notes for links.
- **Dependencies:** Frontend + Product.
- **Constraints:** Preserve existing functionality and route compatibility.
- **Dependency / change risk:** Nav changes break mental models, bookmarks, and external docs. Mitigations are **in scope:** in-app **migration banner** (time-boxed), **command palette / search** fallback for “lost” actions, **preserved keyboard shortcuts** where they exist, **release notes** and doc updates, **route-level analytics** (see §5.1 telemetry) to detect dead-ends.
- **Tools available:** frontend components, E2E tests.
- **Steps / plan:**
  1. Define target IA with primary vs advanced tiers.
  2. Implement nav grouping and labels; add banner + palette/discoverability fallbacks as needed.
  3. Validate onboarding and incident flows with keyboard and mobile checks.
- **Error handling:**
  - Expected failure modes: broken route assumptions, stale links.
  - Recovery steps: add redirects and preserve old route aliases.
  - Rollback/backout conditions: significant diagnosis flow regression.
- **Validation / verification:**
  - Automated checks: frontend lint/test/build.
  - Manual checks: first-time navigation and incident drill walk-through.
  - Observed evidence: shorter click path to diagnosis outcomes.
- **Idempotency (re-run safety):**
  - Safe to re-run? Yes
  - If partial/no, guardrails required: maintain route redirects.
- **State / progress tracking:**
  - Status: Todo
  - % complete: 0
  - Last update: 2026-05-07
  - Owner: Frontend + Product
- **Related documents:** `DEVELOPMENT.md`, `docs/testing/E2E_CORE_JOURNEY.md`
- **References / examples:** `frontend/components/dashboard/AppShell.tsx`
- **Ambiguity handling:**
  - If requirement is unclear: optimize for fastest diagnosis journey.
  - If data conflicts: preserve MVP lane over power-user lane.
  - Escalation owner: Product lead.
- **Observability (logs, tracking):**
  - Logs/metrics/traces to add: route views + nav interactions; zero-result search if applicable.
  - Alert thresholds: N/A
  - Success signals: shorter median clicks-to-diagnosis in staged tests; **no spike** in empty-state exits on former primary routes.

### Task T03: Improve onboarding and first-value activation

- **Description:** Reduce activation friction while preserving secure setup and role-based key management.
- **Priority:** P1
- **Acceptance criteria (AC):**
  - AC1: Users can reach meaningful read-only value before strict completion gates where safe.
  - AC2: Onboarding states clearly explain required actions by role (admin/member).
  - AC3: "No data yet" flow points to one primary next action.
- **Inputs:** onboarding page/component, layout redirects, auth/session behavior.
- **Outputs:** onboarding UX adjustments and role-specific guidance.
- **Dependencies:** Frontend, backend auth behavior.
- **Constraints:** Must not expose privileged actions to non-authorized users.
- **Tools available:** frontend routes/components, E2E flows.
- **Steps / plan:**
  1. Identify hard gates that can become soft guidance.
  2. Add role-specific action copy and progress feedback.
  3. Validate zero-data to first-event journey end-to-end.
- **Error handling:**
  - Expected failure modes: unauthorized key actions; confusing mixed states.
  - Recovery steps: preserve strict permission checks and tighten fallback copy.
  - Rollback/backout conditions: security regression in key issuance flow.
- **Validation / verification:**
  - Automated checks: frontend test/build.
  - Manual checks: admin/member onboarding paths and empty state transitions.
  - Observed evidence: lower onboarding drop-off in test sessions.
- **Idempotency (re-run safety):**
  - Safe to re-run? Yes
  - If partial/no, guardrails required: keep server-side authorization source of truth.
- **State / progress tracking:**
  - Status: Todo
  - % complete: 0
  - Last update: 2026-05-07
  - Owner: Frontend + Product
- **Related documents:** `DEVELOPMENT.md`
- **References / examples:** `frontend/components/dashboard/dashboardPages/OnboardingContent.tsx`
- **Ambiguity handling:**
  - If requirement is unclear: choose simpler first-value path with secure defaults.
  - If data conflicts: prefer explicit server state over client assumptions.
  - Escalation owner: Product lead.
- **Observability (logs, tracking):**
  - Logs/metrics/traces to add: onboarding stage completion telemetry (aggregate).
  - Alert thresholds: N/A
  - Success signals: funnel conversion improves vs baseline or meets **§5.1** onboarding targets.

### Task T04: Fix frontend accessibility blockers in core diagnosis paths

- **Description:** Remove high-impact a11y issues in modal/menu/keyboard interactions for evidence workflows.
- **Priority:** P1
- **Acceptance criteria (AC):**
  - AC1: Evidence modal traps focus, sets initial focus, and restores focus on close.
  - AC2: Row action menus support full keyboard interaction patterns.
  - AC3: Critical interactions pass keyboard-only and basic screen-reader checks.
- **Inputs:** modal, row menu, collapsible header panel, chart wrappers.
- **Outputs:** a11y-focused frontend improvements and test coverage updates.
- **Dependencies:** Frontend.
- **Constraints:** No visual regressions in diagnosis workflows.
- **Tools available:** frontend unit/E2E tests, browser accessibility checks.
- **Steps / plan:**
  1. Implement focus management and keyboard behavior.
  2. Add ARIA/semantics where missing in key controls.
  3. Run keyboard-only verification on diagnosis and requests.
- **Error handling:**
  - Expected failure modes: focus loss, interaction dead-ends.
  - Recovery steps: revert to known-safe modal/menu patterns.
  - Rollback/backout conditions: regression in primary incident workflow.
- **Validation / verification:**
  - Automated checks: frontend test/build.
  - Manual checks: tab/shift-tab/escape/arrow-key flows and modal lifecycle.
  - Observed evidence: no keyboard traps or unreachable controls.
- **Idempotency (re-run safety):**
  - Safe to re-run? Yes
  - If partial/no, guardrails required: preserve role/action permissions.
- **State / progress tracking:**
  - Status: Todo
  - % complete: 0
  - Last update: 2026-05-07
  - Owner: Frontend
- **Related documents:** `docs/testing/E2E_CORE_JOURNEY.md`
- **References / examples:** `frontend/components/dashboard/DashboardDetailModal.tsx`
- **Ambiguity handling:**
  - If requirement is unclear: use WAI-ARIA dialog/menu best-practice behavior.
  - If data conflicts: prioritize incident-path accessibility first.
  - Escalation owner: Frontend lead.
- **Observability (logs, tracking):**
  - Logs/metrics/traces to add: N/A
  - Alert thresholds: N/A
  - Success signals: **0 critical** keyboard/SR blockers on incident paths (see §5.1).

### Task T05: Enforce production topology guardrails and startup validation

- **Description:** Convert high-risk deployment assumptions (DuckDB writer model, scheduler requirements, realtime topology) into explicit, testable guardrails.
- **Priority:** P0
- **Severity behavior (must be implemented, not advisory):**

| Severity | Example | Behavior |
|----------|---------|----------|
| **Unsafe** | Shared DuckDB writers across instances; production multi-writer where integrity cannot hold; scheduler missing when required for prod profile | **Hard fail startup** in production (and staging where matrix requires); block deploy |
| **Risky** | Single writer but replay/scheduler degraded; migration mode inconsistent with topology | Process may start; **`/ready` = not ready** (or equivalent degraded signal) + alert |
| **Non-ideal** | Suboptimal but supported (e.g. dev-only shortcuts enabled in staging) | Warning logs + docs |

- **Acceptance criteria (AC):**
  - AC1: Startup and `/ready` expose topology profile; **unsafe** combinations **hard-fail** in production per matrix (§5.1), not “warn only.”
  - AC2: Runbook checklists list unsafe vs risky vs non-ideal and map to behaviors above.
  - AC3: Staging validation covers scheduler, realtime bus/stickiness, and migration mode; invalid migration modes for topology **fail closed** where classified unsafe/risky.
- **Inputs:** config validation, lifespan startup, ops docs.
- **Outputs:** guardrail checks and updated operational verification checklist.
- **Dependencies:** Backend + Ops.
- **Constraints:** Do not break local development defaults.
- **Tools available:** backend config tests, health/metrics endpoints, staging env.
- **Steps / plan:**
  1. Enumerate unsafe/risky/non-ideal combinations and map to severity table.
  2. Implement **hard fail** for unsafe production configs; **degraded ready** for risky; warnings for non-ideal.
  3. Verify in staging and capture evidence; confirm dev defaults unchanged.
- **Error handling:**
  - Expected failure modes: false-positive config rejection.
  - Recovery steps: provide clear override/deprecation path where justified.
  - Rollback/backout conditions: startup failures on valid known deployments.
- **Validation / verification:**
  - Automated checks: config validation tests.
  - Manual checks: staging startup + `/ready` + `/internal/metrics`.
  - Observed evidence: expected topology markers and healthy readiness.
- **Idempotency (re-run safety):**
  - Safe to re-run? Yes
  - If partial/no, guardrails required: migration toggles documented.
- **State / progress tracking:**
  - Status: In progress
  - % complete: 55
  - Last update: 2026-05-08 (guardrail increment: explicit unsafe/risky topology classification in `/ready` + realtime risk signaling + tests/docs)
  - Owner: Backend + Ops
- **Related documents:** `docs/ops/PRODUCTION_DEPLOYMENT.md`, `docs/ops/DEPLOYMENT_MULTI_INSTANCE.md`
- **References / examples:** `backend/src/autopulse_backend/core/config.py`, `backend/src/autopulse_backend/lifespan.py`
- **Ambiguity handling:**
  - If requirement is unclear: prefer safer fail-closed production behavior.
  - If data conflicts: use ops docs + runtime checks as source of truth.
  - Escalation owner: CTO.
- **Observability (logs, tracking):**
  - Logs/metrics/traces to add: topology and scheduler health markers.
  - Alert thresholds: scheduler inactive or unsafe topology detected.
  - Success signals: **zero** unsafe production starts; risky states visible in `/ready` within **1 min** of fault injection (staging drill).

### Task T06: Harden reliability and consistency operations

- **Description:** Tighten repair/replay and monitoring loops for cross-store consistency and aggregate freshness.
- **Priority:** P1
- **Acceptance criteria (AC):**
  - AC1: SQL-tail repair queue health is visible and alertable.
  - AC2: Runbook includes deterministic replay/recovery for stale aggregates.
  - AC3: Incident drills validate recovery within defined SLA.
- **Inputs:** ingest service, repair jobs, ops runbooks, metrics endpoints.
- **Outputs:** monitoring thresholds, drill evidence, runbook updates.
- **Dependencies:** Backend + Ops.
- **Constraints:** No ingest hot-path regressions.
- **Tools available:** metrics, replay tools, drill playbooks.
- **Steps / plan:**
  1. Define freshness and consistency SLO/SLI targets.
  2. Wire alerts for queue age/failures and replay outcomes.
  3. Execute drills and update operational guidance.
- **Error handling:**
  - Expected failure modes: replay failures or poisoned records.
  - Recovery steps: dead-letter handling and manual replay tooling.
  - Rollback/backout conditions: repeated replay failures without bounded recovery.
- **Validation / verification:**
  - Automated checks: backend tests for fail-then-repair scenarios.
  - Manual checks: controlled failure injection in staging.
  - Observed evidence: queue drains and aggregates recover to expected state.
- **Idempotency (re-run safety):**
  - Safe to re-run? Yes
  - If partial/no, guardrails required: replay dedupe by event/batch identifiers.
- **State / progress tracking:**
  - Status: Todo
  - % complete: 0
  - Last update: 2026-05-07
  - Owner: Backend + Ops
- **Related documents:** `docs/ops/RUNBOOK_EVENT_PLANE_BACKPRESSURE.md`
- **References / examples:** `backend/src/autopulse_backend/services/ingest_service.py`
- **Ambiguity handling:**
  - If requirement is unclear: favor correctness over partial freshness.
  - If data conflicts: use raw persisted events as replay source.
  - Escalation owner: Backend lead.
- **Observability (logs, tracking):**
  - Logs/metrics/traces to add: queue age, replay success/failure, stale-window count.
  - Alert thresholds: pending repair age over target SLA (see §5.1 replay SLA).
  - Success signals: bounded lag with stable repair success; drill completes within **< 10 min** where scoped.

### Task T07: Production security posture tightening pass

- **Description:** Review and tighten production-safe security defaults and deployment patterns (CORS, proxy trust, auth/session modes), plus **MVP production auth hygiene** (below—not enterprise IAM).
- **Priority:** P1
- **Acceptance criteria (AC):**
  - AC1: Production CORS guidance is explicit and least-privilege.
  - AC2: HTTPS/proxy header expectations are validated in deployment checks.
  - AC3: Security-sensitive env combinations are documented and test-covered.
  - AC4: **API key lifecycle** documented (issue, rotate, revoke; hashes-at-rest only; no plaintext in logs) and aligned with backend behavior.
  - AC5: **Session expiration / idle timeout** policy documented and consistent with cookie settings; magic-link or token flows reviewed for TTL and single-use where applicable.
  - AC6: **CSRF** posture verified for cookie-authenticated dashboard mutations (same-site, token, or equivalent); gaps documented with fix or explicit accepted risk for MVP.
  - AC7: **Secret rotation** guidance: which secrets, how often, runbook steps for DB/proxy/signing keys without downtime goals beyond MVP.
  - AC8: **Audit logging strategy for MVP:** what is logged (e.g. admin actions, key rotation events), what is explicitly **not** logged (payloads, PII), retention pointer—no full enterprise audit product.
- **Inputs:** backend app middleware config, deployment docs, auth settings.
- **Outputs:** tightened security guidance/checks and regression tests where needed.
- **Dependencies:** Backend + Ops.
- **Constraints:** Preserve local dev ergonomics.
- **Tools available:** config tests, staging validation, docs updates.
- **Steps / plan:**
  1. Audit current production defaults and permissive settings.
  2. Add explicit constraints/recommendations for production.
  3. Validate sessions/auth flows behind TLS proxy in staging.
- **Error handling:**
  - Expected failure modes: over-restrictive CORS breaks dashboard usage.
  - Recovery steps: controlled rollback to known-safe origin set.
  - Rollback/backout conditions: customer-facing auth/session failures.
- **Validation / verification:**
  - Automated checks: config and auth deployment tests.
  - Manual checks: login/session behavior under proxy/TLS.
  - Observed evidence: secure cookies and expected origin behavior.
- **Idempotency (re-run safety):**
  - Safe to re-run? Yes
  - If partial/no, guardrails required: staged rollout by environment.
- **State / progress tracking:**
  - Status: Todo
  - % complete: 0
  - Last update: 2026-05-07
  - Owner: Backend + Ops
- **Related documents:** `docs/ops/PRODUCTION_DEPLOYMENT.md`, `agents/security-privacy.md`
- **References / examples:** `backend/src/autopulse_backend/app.py`, `backend/src/autopulse_backend/auth/dashboard_security.py`
- **Ambiguity handling:**
  - If requirement is unclear: choose stricter production-safe behavior.
  - If data conflicts: prioritize documented security constraints.
  - Escalation owner: CTO.
- **Observability (logs, tracking):**
  - Logs/metrics/traces to add: auth/session error-rate markers (aggregate).
  - Alert thresholds: login failure spikes after security changes (see §5.1 global rollback).
  - Success signals: stable secure auth; **no 2×** baseline auth error spike post-deploy.

### Task T08: Developer QOL quick-win bundle

- **Description:** Remove common engineering friction in local setup, parity checks, and daily workflows with **explicit commands and parity matrix** (no vague “improve DX”).
- **Priority:** P2
- **Acceptance criteria (AC):**
  - AC1: **Exact commands** documented end-to-end, e.g. `make backend-dev` (or repo-standard equivalent), `uv sync` / `pip install -e` path as used in CI, `npm ci && npm run dev` / `npm run build` in `frontend/`, and **one** “first ingest smoke” command sequence from cold clone.
  - AC2: `scripts/release_gates.sh` (or successor) linked from **root `README.md`** with copy-paste invocation and expected green output summary.
  - AC3: **Supported matrix** table: OS (macOS/Linux), Python **3.x** minor range as tested in CI, Node **LTS** version as in `.nvmrc` or `package.json` engines, and “best effort” vs “supported” for Windows if applicable.
  - AC4: **Parity matrix:** local vs CI for lint, unit tests, release gates (which steps run where); drift between doc and script is resolved in favor of **script/CI as source of truth** with doc updated same PR.
- **Inputs:** Makefile/scripts, frontend/backend setup docs, CI workflow.
- **Outputs:** improved DX docs/scripts and reduced setup variance.
- **Dependencies:** Backend + Frontend + DevEx owner.
- **Constraints:** Keep changes lightweight and backwards-compatible.
- **Tools available:** scripts, docs, CI config.
- **Steps / plan:**
  1. Identify top recurring setup pain points.
  2. Add convenience targets/documentation for common paths.
  3. Verify fresh-machine style setup flow.
- **Error handling:**
  - Expected failure modes: drift between docs and script behavior.
  - Recovery steps: enforce script-as-source-of-truth for docs examples.
  - Rollback/backout conditions: broken dev startup path.
- **Validation / verification:**
  - Automated checks: CI script checks.
  - Manual checks: clean local startup and first ingest following documented commands only (no unstated steps).
  - Observed evidence: cold start meets **§5.1** DX target; parity matrix matches CI.
- **Idempotency (re-run safety):**
  - Safe to re-run? Yes
  - If partial/no, guardrails required: N/A
- **State / progress tracking:**
  - Status: Todo
  - % complete: 0
  - Last update: 2026-05-07
  - Owner: DevEx
- **Related documents:** `README.md`, `scripts/release_gates.sh`
- **References / examples:** `Makefile`, `.github/workflows/ci.yml`
- **Ambiguity handling:**
  - If requirement is unclear: optimize for shortest reliable path to local value.
  - If data conflicts: script behavior wins over prose docs.
  - Escalation owner: CTO.
- **Observability (logs, tracking):**
  - Logs/metrics/traces to add: N/A
  - Alert thresholds: N/A
  - Success signals: cold start to first local ingest **≤ 15 min** on reference laptop (§5.1 DX DoD).

### Task T09: Release quality gate hardening and test strategy uplift

- **Description:** Increase release confidence by strengthening critical-path validation and consistency between local, CI, and production assumptions.
- **Priority:** P2
- **Acceptance criteria (AC):**
  - AC1: Critical-path tests are explicitly documented and always executed in release gates.
  - AC2: Frontend static build/export path is validated for every UI-impacting change.
  - AC3: Coverage and regression policy is defined with gradual tightening targets.
- **Inputs:** release gate scripts/workflows, current test matrices, coverage policy.
- **Outputs:** improved release checklist and enforced validation steps.
- **Dependencies:** Backend + Frontend + QA owner.
- **Constraints:** Avoid large CI runtime spikes without value.
- **Tools available:** release scripts, CI workflows, testing suites.
- **Steps / plan:**
  1. Define critical-path test manifest.
  2. Enforce manifest in release-gate scripts.
  3. Set and review incremental quality targets.
- **Error handling:**
  - Expected failure modes: flaky tests increase cycle time.
  - Recovery steps: quarantine and stabilize flaky paths quickly.
  - Rollback/backout conditions: release blocked by unrelated unstable checks.
- **Validation / verification:**
  - Automated checks: release gate run in CI.
  - Manual checks: confirm checklist evidence before production deploy.
  - Observed evidence: consistent green release-gate outcomes.
- **Idempotency (re-run safety):**
  - Safe to re-run? Yes
  - If partial/no, guardrails required: isolate flaky test retries.
- **State / progress tracking:**
  - Status: Todo
  - % complete: 0
  - Last update: 2026-05-07
  - Owner: QA + Eng leads
- **Related documents:** `docs/runbooks/PHASE5_RELEASE_CHECKLIST.md`, `docs/testing/E2E_CORE_JOURNEY.md`
- **References / examples:** `.github/workflows/ci.yml`, `.github/workflows/release-gates.yml`
- **Ambiguity handling:**
  - If requirement is unclear: prioritize customer-visible incident paths.
  - If data conflicts: release gate scripts define minimum bar.
  - Escalation owner: CTO.
- **Observability (logs, tracking):**
  - Logs/metrics/traces to add: CI pass/fail trend dashboards.
  - Alert thresholds: repeated release-gate failures.
  - Success signals: release gate pass rate **> 95%** / 14d (§5.1).

### Task T10: Productize jobs/cron and advanced capabilities with progressive disclosure

- **Description:** Clarify and improve feature presentation so background-job monitoring and advanced analytics are available without diluting default diagnosis flow.
- **Priority:** P2
- **Acceptance criteria (AC):**
  - AC1: Jobs/cron value path has clear UI entry and action guidance.
  - AC2: Advanced capabilities are discoverable but non-disruptive to first-value flow.
  - AC3: Documentation clearly distinguishes core versus advanced workflows.
- **Inputs:** frontend IA/pages, job event routes, product docs.
- **Outputs:** improved UI/docs for jobs and advanced feature positioning.
- **Dependencies:** Product + Frontend + Backend.
- **Constraints:** Must keep MVP-first user journey intact. **Anti-feature-creep:** must **not** add new primary workflows, workflow-engine UI, general-purpose scheduler product, or automation platform—**only** diagnosis-adjacent surfacing (status, errors, links to core incident path) and docs/IA. Any expansion beyond that requires **explicit** scope approval outside this plan.
- **Tools available:** frontend components/routes, docs updates.
- **Steps / plan:**
  1. Map current jobs/cron user journey and friction points.
  2. Add concise productized entry points and guidance.
  3. Validate that core incident journey remains primary.
- **Error handling:**
  - Expected failure modes: feature creep in primary nav.
  - Recovery steps: keep advanced paths grouped and optional.
  - Rollback/backout conditions: increased complexity in onboarding flow.
- **Validation / verification:**
  - Automated checks: frontend build/tests.
  - Manual checks: jobs failure discovery-to-resolution walkthrough.
  - Observed evidence: quicker completion of jobs diagnosis tasks.
- **Idempotency (re-run safety):**
  - Safe to re-run? Yes
  - If partial/no, guardrails required: preserve route compatibility.
- **State / progress tracking:**
  - Status: Todo
  - % complete: 0
  - Last update: 2026-05-07
  - Owner: Product + Frontend
- **Related documents:** `DEVELOPMENT.md`, `docs/DEVELOPMENT_PROCESS.md`
- **References / examples:** `backend/src/autopulse_backend/dashboard/routes/job_events.py`
- **Ambiguity handling:**
  - If requirement is unclear: default to minimal UI with clear value.
  - If data conflicts: preserve current stable behavior and phase changes.
  - Escalation owner: Product lead.
- **Observability (logs, tracking):**
  - Logs/metrics/traces to add: jobs-page engagement and resolution flow signals (see §5.1 required telemetry).
  - Alert thresholds: N/A
  - Success signals: measurable increase in “jobs page → correlated finding” completion in staged usability or analytics (define baseline in first sprint of T10).

### Task T11: Incident drill program (first-class)

- **Description:** Formalize repeated, evidenced drills so operators prove recovery—not only runbooks—covering replay, scheduler, realtime degradation, migration rollback, and stale aggregate recovery.
- **Priority:** P1 (operational; pairs with T06)
- **Acceptance criteria (AC):**
  - AC1: Drill catalog exists with **frequency** (staging weekly target; pre-prod mandatory per §5.1), owner, and expected duration.
  - AC2: Minimum drills: **replay recovery**; **scheduler outage / absence**; **websocket or realtime degradation**; **migration rollback**; **stale aggregate recovery**—each with pass/fail criteria and log attachment.
  - AC3: Drill outcomes feed back into runbooks and alert thresholds (`T06`).
- **Inputs:** staging env, runbooks, metrics, replay tooling.
- **Outputs:** drill checklist artifacts, dated evidence, runbook updates.
- **Dependencies:** T05, T06; Ops owner leads.
- **Constraints:** Drills must not corrupt production; use isolated data sets.
- **Tools available:** staging, scripts, observability stack.
- **Steps / plan:** 1) Author catalog. 2) Execute first full cycle. 3) Schedule recurring execution with ownership in §5.1.
- **Error handling:** Failed drill → block prod promotion until remediated or risk accepted in writing by CTO.
- **Validation / verification:** At least one full drill cycle completed and archived before declaring Ops lane done (§5.1).
- **Idempotency:** Safe to re-run drills on disposable staging data.
- **State / progress tracking:** Status: Todo; Owner: Ops + Backend; Last update: 2026-05-07
- **Related documents:** `docs/ops/*`, `T06` references
- **Observability:** Drill metrics stored with incident review cadence (§5.1).

### Task T12: Supportability and diagnostics surfaces

- **Description:** Operator-facing surfaces that reduce support burden: topology, scheduler health, replay queue, ingestion freshness, and **safe** config diagnostics export (no secrets).
- **Priority:** P1
- **Acceptance criteria (AC):**
  - AC1: **Topology / profile** visible in dashboard or documented API for operators (aligned with T05 markers).
  - AC2: **Scheduler status** page or section (last run, next run, failure state).
  - AC3: **Replay / repair queue** status visible with age and backlog indicators.
  - AC4: **Ingestion freshness** indicator (last event received / lag vs wall clock, project-scoped where applicable).
  - AC5: **Config diagnostics export** (redacted env summary, feature flags, topology class) for support tickets—**no API keys or tokens**.
- **Inputs:** backend metrics, existing internal routes, frontend shell.
- **Outputs:** UI pages or consolidated “System” area + export JSON endpoint behind auth.
- **Dependencies:** T05, T06; Backend primary; Frontend for surfaces.
- **Constraints:** Authz must match dashboard admin model; no PII expansion.
- **Tools available:** FastAPI routes, frontend pages, metrics already emitted.
- **Steps / plan:** 1) Inventory existing signals. 2) Design minimal UI. 3) Ship behind feature flag if needed.
- **Validation / verification:** Operator can answer “is the system healthy?” without SSH in common cases.
- **State / progress tracking:** Status: Todo; Owner: Backend + Frontend + Ops; Last update: 2026-05-07
- **Related documents:** §5.1 Production readiness matrix

## 7) Plan-level execution strategy

- **Schedule source of truth:** dependency gates, relative weeks, and environment matrix live in **§5.1** (master schedule, production readiness matrix, promotion policy, rollback rules, metrics, observability ownership). Update §5.1 when dates slip—do not let narrative sections drift from the table.
- **Architecture-level production risk (until closed):** the **#1 operational risk** remains **shared mutable storage topology** (multi-writer DuckDB / wrong migration mode). Treat **T05 + T06 + T11** as the primary containment until topology is eliminated or fully guardrailed per the readiness matrix.
- Delivery sequence:
  1. P0 trust and production guardrails (`T01`, `T05`)—Week 1 per §5.1.
  2. P1 UX/core-flow, reliability, security, drills, and supportability (`T02`, `T03`, `T04`, `T06`, `T07`, **`T11`**, **`T12`**).
  3. P2 DX/release/productization follow-through (`T08`, `T09`, `T10`).
- Parallelization opportunities:
  - Frontend lane (`T02`, `T03`, `T04`) can run in parallel with backend/ops lane (`T05`, `T06`, `T07`) once `T01` has landed for IA/doc alignment.
  - **`T11` drills** run on staging alongside `T06` hardening; **`T12`** surfaces consume signals from `T05`/`T06` and can parallelize FE work after markers exist.
  - DX/release (`T08`, `T09`) can run concurrently once P0 has started.
- Risk register (top 5):
  - R1: Unsafe production topology still deployable by operator error (**mitigation: T05 severity table + readiness matrix hard fails**).
  - R2: UX simplification causes regressions in power-user workflows (**mitigation: T02 migration banner, palette, shortcuts, route analytics, §5.1 rollback thresholds**).
  - R3: Security hardening changes inadvertently break auth/session (**mitigation: T07 AC4–8, staging soak, global rollback auth spike rule**).
  - R4: Reliability drill gaps remain untested in realistic staging conditions (**mitigation: T11 mandatory catalog + promotion policy**).
  - R5: Execution drift from **uncalendared** work (**mitigation: §5.1 master schedule + weekly owner review of metrics table**).
- Decision log:
  - Decision: Prioritize trust + production-safety fixes before feature expansion.
  - Why: Highest impact on user confidence and incident outcomes.
  - Date: 2026-05-07
  - Owner: CTO

## 8) Validation gate before completion

Mark each item before closing the plan:

- [ ] All P0 and P1 tasks have **owners and relative week targets** (§5.1); calendar dates assigned for next two milestones.
- [ ] **Lane definition-of-done** (§5.1) reviewed for Frontend, Ops, Security, DX, Product.
- [ ] Contract/docs alignment is verified by first-ingest smoke test (**first-run success rate** measured vs §5.1 target where feasible).
- [ ] Production guardrails are validated on staging (`/health`, `/ready`, `/internal/metrics`); **unsafe topology hard-fail** verified in staging drill.
- [ ] Frontend diagnosis flow passes keyboard-only and mobile checks (**0 critical** a11y blockers).
- [ ] **Staging promotion policy** (§5.1) satisfied for last production release candidate.
- [ ] **Global rollback** thresholds wired to monitoring or manual review checklist.
- [ ] Release gates include critical backend + frontend pathways; **> 95%** pass rate trend or documented remediation (`T09`).
- [ ] **T11** drill catalog executed at least one full cycle with archived evidence; **T12** surfaces usable for common support questions.
- [ ] Updated docs remain aligned with `DEVELOPMENT.md` and no unsupported promises.
- [ ] **Product telemetry** minimum set (§5.1) implemented or explicitly deferred with owner + date.
