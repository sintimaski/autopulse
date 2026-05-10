# Backend Hardening Phased Task Plan

## 1) Plan header

- **Plan name:** Backend hardening and MVP launch readiness
- **Owner:** Backend team
- **Date:** 2026-05-11
- **Status:** Draft
- **Scope summary (2-4 lines):** Decompose backend audit findings into incremental phases and single-go implementation tasks. Prioritize security/correctness first, then alert semantics and reliability, then DX/QOL and release evidence. Each task is scoped to one focused PR that can be implemented and validated in one pass.
- **Out of scope:** Frontend UX redesign, new non-MVP product features, infra re-platforming.

## 2) Context / background

- Problem statement: Backend foundation is strong, but launch risk remains in RBAC/auth fallback behavior, ingest consistency semantics, alert parity, and local-to-CI validation parity.
- Why now: These gaps can cause security drift, silent data inconsistency, and false confidence during release preparation.
- Current behavior (as-is): Most MVP capabilities exist, with partial semantics in selected paths and operational dependencies that are not fully enforced by tests/runbooks.
- Desired behavior (to-be): Secure-by-default auth/RBAC, deterministic ingest and alert semantics, robust repair visibility, and reproducible verification from local dev through CI/release gates.
- User impact: Fewer false alerts, fewer dashboard inconsistencies, safer access control, faster contributor onboarding.
- Technical impact: Small focused backend diffs, new tests, tightened docs/runbooks, stronger release evidence.

## 3) Domain rules and constraints

- Product/domain rules: Stay within MVP boundaries in `DEVELOPMENT.md`; prefer minimal diffs over scope expansion.
- Security/privacy rules: Never weaken API key protection; avoid storing/logging sensitive payloads; preserve conservative defaults.
- Performance/SLO constraints: Keep ingest hot path fast; preserve dashboard query latency contract.
- Compliance/governance constraints: Governed docs changes require approval if material; task plans belong under `docs/plans/`.
- Non-goals: Building full enterprise RBAC redesign, distributed tracing enhancements, new query language features.

## 4) Inputs, outputs, and dependencies

- **Inputs:** Backend audit findings; `DEVELOPMENT.md`; `docs/DASHBOARD_QUERY_LATENCY_CONTRACT.md`; `docs/runbooks/PHASE5_RELEASE_CHECKLIST.md`; backend tests.
- **Outputs:** Backend code fixes, tests, docs/runbook updates, release gate evidence.
- **Dependencies:** Existing scheduler/jobs wiring, CI workflows, environment variables in `backend/.env.example`.
- **Tools available:** `uv`, `pytest`, `ruff`, `mypy`, `pip-audit`, `make`, release gate scripts, backend health/metrics endpoints.

## 5) Task breakdown

### Phase 0 - Baseline and guardrails

### Task `P0-T1`: Capture baseline readiness evidence

- **Description:** Run current backend checks and collect baseline failures/skips to measure hardening progress.
- **Priority:** P0
- **Acceptance criteria (AC):**
  - AC1: Baseline report includes lint/type/test/release-gate status and skip reasons.
  - AC2: Baseline records test environment variables used.
  - AC3: Report is committed under `docs/plans/` or linked from this plan.
- **Inputs:** Current branch, `Makefile`, `scripts/release_gates.sh`, CI workflows.
- **Outputs:** Baseline evidence artifact.
- **Dependencies:** None.
- **Constraints:** No production config changes in this task.
- **Tools available:** `make`, `uv`, `pytest`, `scripts/release_gates.sh`.
- **Steps / plan:**
  1. Execute local backend quality and release gates.
  2. Record pass/fail/skip and environment assumptions.
  3. Save evidence and identify blockers for next tasks.
- **Error handling:**
  - Expected failure modes: Missing env vars, DB init issues, optional test skips.
  - Recovery steps: Re-run with explicit env vars and isolated test DB path.
  - Rollback/backout conditions: N/A (read/verify task).
- **Validation / verification:**
  - Automated checks: `make check-python`, `bash ./scripts/release_gates.sh`.
  - Manual checks: Inspect summary for hidden skips.
  - Observed evidence: Command outputs captured in artifact.
- **Idempotency (re-run safety):**
  - Safe to re-run? Yes
  - If partial/no, guardrails required: N/A
- **State / progress tracking:**
  - Status: Done
  - % complete: 100%
  - Last update: 2026-05-11 (baseline artifact created)
  - Owner: Backend team
- **Related documents:** `docs/runbooks/PHASE5_RELEASE_CHECKLIST.md`
- **References / examples:** `.github/workflows/ci.yml`
- **Ambiguity handling:**
  - If requirement is unclear: Default to CI parity interpretation.
  - If data conflicts: Prefer CI workflow as source of truth.
  - Escalation owner: Tech lead
- **Observability (logs, tracking):**
  - Logs/metrics/traces to add: None.
  - Alert thresholds: None.
  - Success signals: Baseline evidence complete and reproducible.

### Phase 1 - Security and authorization correctness

### Task `P1-T1`: Harden RBAC when auth session is absent

- **Description:** Ensure admin/owner-only dashboard mutations cannot pass through API-key fallback without explicit policy.
- **Priority:** P0
- **Acceptance criteria (AC):**
  - AC1: Mutating routes requiring admin/owner fail when only API-key context is present (unless explicitly allowed by policy).
  - AC2: Existing valid cookie session flows remain unchanged.
  - AC3: Automated tests cover session and API-key fallback permutations.
- **Inputs:** `backend/src/lumonox_backend/auth/rbac.py`, `auth/api_keys.py`, dashboard mutating routes.
- **Outputs:** RBAC policy fix + regression tests.
- **Dependencies:** None.
- **Constraints:** Must not break production auth rules in `core/config.py`.
- **Tools available:** `pytest`, backend auth tests.
- **Steps / plan:**
  1. Define explicit behavior matrix for session vs API-key access.
  2. Implement dependency checks enforcing matrix.
  3. Add tests for all critical permutations.
- **Error handling:**
  - Expected failure modes: Route dependency mismatch, false-deny for legitimate admins.
  - Recovery steps: Add route-level overrides where policy requires.
  - Rollback/backout conditions: Revert to previous dependency behavior if widespread auth regression.
- **Validation / verification:**
  - Automated checks: Targeted auth/RBAC tests + full backend tests.
  - Manual checks: Validate dashboard mutation endpoints with/without session cookie.
  - Observed evidence: 403/401 for forbidden paths; 2xx for allowed paths.
- **Idempotency (re-run safety):**
  - Safe to re-run? Yes
  - If partial/no, guardrails required: Keep tests deterministic with fixed fixtures.
- **State / progress tracking:**
  - Status: Done
  - % complete: 100%
  - Last update: 2026-05-11 (admin/owner guard now requires dashboard cookie session)
  - Owner: Backend team
- **Related documents:** `DEVELOPMENT.md`, `backend/src/lumonox_backend/core/config.py`
- **References / examples:** `backend/src/lumonox_backend/auth/rbac.py`
- **Ambiguity handling:**
  - If requirement is unclear: Default to deny on mutation without trusted user session.
  - If data conflicts: Escalate to product/security owner.
  - Escalation owner: Security lead
- **Observability (logs, tracking):**
  - Logs/metrics/traces to add: Auth deny reason counter by mode (session/api-key).
  - Alert thresholds: Unexpected deny spike >20% day-over-day.
  - Success signals: No unauthorized mutation path in tests.

### Task `P1-T2`: Reduce sensitive data leakage in persisted ingest errors

- **Description:** Replace raw exception persistence with sanitized error codes/messages for repair/dead-letter records.
- **Priority:** P0
- **Acceptance criteria (AC):**
  - AC1: Persisted `last_error` does not contain raw payload fragments/tokens.
  - AC2: Operators can still diagnose failures via stable error categories.
  - AC3: Tests validate redaction behavior.
- **Inputs:** `services/ingest_service.py`, reliability repositories, dead-letter handling.
- **Outputs:** Sanitized persistence + tests + doc note.
- **Dependencies:** Task P0-T1 baseline evidence.
- **Constraints:** Keep troubleshooting usefulness; avoid over-redacting operational context.
- **Tools available:** `pytest`, logging helpers.
- **Steps / plan:**
  1. Introduce error classifier/redactor utility.
  2. Replace direct exception string persistence.
  3. Add regression tests for sensitive strings.
- **Error handling:**
  - Expected failure modes: Loss of diagnosability.
  - Recovery steps: Add structured fields (`error_code`, `context_id`) instead of raw text.
  - Rollback/backout conditions: If on-call cannot triage incidents.
- **Validation / verification:**
  - Automated checks: Ingest reliability and repair tests.
  - Manual checks: Trigger controlled failure and inspect stored row values.
  - Observed evidence: No secret-like patterns persisted.
- **Idempotency (re-run safety):**
  - Safe to re-run? Yes
  - If partial/no, guardrails required: Migration guard if schema changes are added.
- **State / progress tracking:**
  - Status: Done
  - % complete: 100%
  - Last update: 2026-05-11 (persisted sql-tail errors now store non-sensitive class summaries)
  - Owner: Backend team
- **Related documents:** `docs/ops/PRODUCTION_DEPLOYMENT.md`
- **References / examples:** Existing SDK scrubbing in `sdk/src/lumonox/_monitor.py`
- **Ambiguity handling:**
  - If requirement is unclear: Prefer security-safe redaction by default.
  - If data conflicts: Use deterministic redaction allowlist.
  - Escalation owner: Security lead
- **Observability (logs, tracking):**
  - Logs/metrics/traces to add: Counter for redacted error writes.
  - Alert thresholds: Sudden jump in unknown error code rate.
  - Success signals: Useful diagnostics without sensitive text exposure.

### Phase 2 - Ingest and alert correctness

### Task `P2-T1`: Align alert window semantics across storage backends

- **Description:** Unify error/success counting logic used by alerts across DuckDB and SQL fallback paths.
- **Priority:** P0
- **Acceptance criteria (AC):**
  - AC1: Same event set yields equivalent alert counts in DuckDB and SQL modes.
  - AC2: Outage and spike evaluations are deterministic across modes.
  - AC3: Tests cover mixed status/type event scenarios.
- **Inputs:** `repositories/events.py`, `services/alert_service.py`, ingest aggregate logic.
- **Outputs:** Unified counting implementation + parity tests.
- **Dependencies:** None.
- **Constraints:** Maintain existing alert thresholds unless explicitly changed.
- **Tools available:** `pytest`, alert unit/integration tests.
- **Steps / plan:**
  1. Define canonical counting contract.
  2. Refactor both backend paths to share contract logic.
  3. Add parity tests for critical scenarios.
- **Error handling:**
  - Expected failure modes: Backward-compatible behavior drift.
  - Recovery steps: Add temporary feature switch if needed.
  - Rollback/backout conditions: Alert storm or silent-alert regression.
- **Validation / verification:**
  - Automated checks: `backend/tests/test_alerts.py` plus parity-focused tests.
  - Manual checks: Replay fixture events in both modes and compare outcomes.
  - Observed evidence: Matching counts and trigger decisions.
- **Idempotency (re-run safety):**
  - Safe to re-run? Yes
  - If partial/no, guardrails required: Fixed test fixtures and deterministic timestamps.
- **State / progress tracking:**
  - Status: Done
  - % complete: 100%
  - Last update: 2026-05-11 (unified SQL/DuckDB alert-window counting contract with parity tests)
  - Owner: Backend team
- **Related documents:** `DEVELOPMENT.md`
- **References / examples:** `backend/src/lumonox_backend/repositories/events.py`
- **Ambiguity handling:**
  - If requirement is unclear: Match `DEVELOPMENT.md` outage intent.
  - If data conflicts: Default to conservative detection and document decision.
  - Escalation owner: Product owner
- **Observability (logs, tracking):**
  - Logs/metrics/traces to add: Alert decision reason code metric.
  - Alert thresholds: Divergence metric between modes must stay at 0.
  - Success signals: Identical trigger outcomes across storage modes.

### Task `P2-T2`: Strengthen ingest idempotency verification on supported DB path

- **Description:** Remove confidence gaps by ensuring idempotency behavior is tested on a non-skipped backend path (Postgres or equivalent deterministic setup).
- **Priority:** P1
- **Acceptance criteria (AC):**
  - AC1: Idempotency replay test runs in at least one mandatory pipeline path.
  - AC2: Duplicate ingest is prevented or replayed deterministically.
  - AC3: Test docs specify required env setup.
- **Inputs:** `backend/tests/test_ingest.py`, CI workflows, release gate scripts.
- **Outputs:** Updated tests + CI/release-gate wiring + docs note.
- **Dependencies:** P0-T1 baseline.
- **Constraints:** Keep local developer loop practical; avoid huge test runtime increase.
- **Tools available:** `pytest`, CI workflows.
- **Steps / plan:**
  1. Isolate current skip cause and choose mandatory execution path.
  2. Update test and CI/release gate wiring.
  3. Document how contributors run this path locally.
- **Error handling:**
  - Expected failure modes: DB locking flakes, nondeterministic timing.
  - Recovery steps: Stabilize fixtures and retry policy for test setup only.
  - Rollback/backout conditions: If runtime cost becomes prohibitive.
- **Validation / verification:**
  - Automated checks: Targeted idempotency test in required CI path.
  - Manual checks: Local run with documented env vars.
  - Observed evidence: Repeat ingest returns replay behavior without duplicate events.
- **Idempotency (re-run safety):**
  - Safe to re-run? Yes
  - If partial/no, guardrails required: Isolated test DB per run.
- **State / progress tracking:**
  - Status: Done
  - % complete: 100%
  - Last update: 2026-05-11 (Postgres CI/release-gate idempotency replay path is now explicit and documented)
  - Owner: Backend team
- **Related documents:** `.github/workflows/ci.yml`, `backend/README.md`
- **References / examples:** `backend/tests/test_ingest.py`
- **Ambiguity handling:**
  - If requirement is unclear: Prefer CI reliability over local convenience.
  - If data conflicts: Use Postgres CI as canonical.
  - Escalation owner: QA lead
- **Observability (logs, tracking):**
  - Logs/metrics/traces to add: CI marker for idempotency suite execution.
  - Alert thresholds: N/A
  - Success signals: No skip in mandatory path.

### Phase 3 - Reliability and operability

### Task `P3-T1`: Add repair/dead-letter operational visibility

- **Description:** Expose and alert on sql-tail repair and dead-letter backlog health to prevent silent inconsistency drift.
- **Priority:** P1
- **Acceptance criteria (AC):**
  - AC1: Metrics include queue depth, replay successes/failures, dead-letter growth.
  - AC2: Runbook includes operator actions and escalation thresholds.
  - AC3: Readiness/diagnostic surface clearly indicates degraded replay state.
- **Inputs:** `jobs/__init__.py`, ingest reliability repositories, health/metrics routes.
- **Outputs:** Metrics/logging additions + runbook update.
- **Dependencies:** P1-T2 error redaction task.
- **Constraints:** Avoid heavy synchronous work on ingest path.
- **Tools available:** Internal metrics endpoints, Prometheus format routes, docs.
- **Steps / plan:**
  1. Instrument replay/dead-letter lifecycle metrics.
  2. Add diagnostic endpoint fields or internal metrics labels.
  3. Update runbook with operator actions.
- **Error handling:**
  - Expected failure modes: Metric cardinality explosion.
  - Recovery steps: Use bounded labels and aggregate counters.
  - Rollback/backout conditions: If metrics significantly impact performance.
- **Validation / verification:**
  - Automated checks: Metrics endpoint tests and replay job tests.
  - Manual checks: Inject replay failures and verify metrics/log signals.
  - Observed evidence: Backlog anomalies are visible within minutes.
- **Idempotency (re-run safety):**
  - Safe to re-run? Yes
  - If partial/no, guardrails required: N/A
- **State / progress tracking:**
  - Status: Done
  - % complete: 100%
  - Last update: 2026-05-11 (replay/dead-letter queue depth gauges + readiness degradation + ops runbook thresholds)
  - Owner: Backend team
- **Related documents:** `docs/ops/PRODUCTION_DEPLOYMENT.md`
- **References / examples:** `backend/src/lumonox_backend/api/routes/health.py`
- **Ambiguity handling:**
  - If requirement is unclear: Prefer actionable operator signals over completeness.
  - If data conflicts: Align with existing metric naming conventions.
  - Escalation owner: SRE owner
- **Observability (logs, tracking):**
  - Logs/metrics/traces to add: Replay queue depth and dead-letter counters.
  - Alert thresholds: Queue depth sustained > N for > M minutes.
  - Success signals: No silent backlog accumulation.

### Task `P3-T2`: Track and manage realtime fanout background tasks safely

- **Description:** Replace fire-and-forget websocket fanout task creation with managed lifecycle tracking.
- **Priority:** P2
- **Acceptance criteria (AC):**
  - AC1: Background fanout tasks are tracked and drained on shutdown.
  - AC2: Failures surface through structured logs/metrics.
  - AC3: No regression in request latency under nominal load.
- **Inputs:** `routes/ingest.py`, websocket/realtime modules, lifespan hooks.
- **Outputs:** Managed task pool utility + tests.
- **Dependencies:** None.
- **Constraints:** Keep ingest request path non-blocking.
- **Tools available:** Async task utilities, pytest async tests.
- **Steps / plan:**
  1. Introduce task registry for non-blocking fanout.
  2. Wire shutdown drain behavior.
  3. Add tests for cancellation/failure and latency invariants.
- **Error handling:**
  - Expected failure modes: Shutdown hangs, task leak.
  - Recovery steps: Timeout-based cancellation and fallback logging.
  - Rollback/backout conditions: If shutdown reliability worsens.
- **Validation / verification:**
  - Automated checks: Async lifecycle tests and ingest route tests.
  - Manual checks: Start/stop backend under fanout load.
  - Observed evidence: Clean shutdown with no orphan tasks.
- **Idempotency (re-run safety):**
  - Safe to re-run? Yes
  - If partial/no, guardrails required: N/A
- **State / progress tracking:**
  - Status: Todo
  - % complete: 0%
  - Last update: 2026-05-11
  - Owner: Backend team
- **Related documents:** `docs/DASHBOARD_QUERY_LATENCY_CONTRACT.md`
- **References / examples:** `backend/src/lumonox_backend/routes/ingest.py`
- **Ambiguity handling:**
  - If requirement is unclear: Prioritize safety over maximal throughput.
  - If data conflicts: Benchmark both implementations.
  - Escalation owner: Backend lead
- **Observability (logs, tracking):**
  - Logs/metrics/traces to add: Fanout task backlog and error counters.
  - Alert thresholds: Fanout errors above baseline for 10 minutes.
  - Success signals: Stable latency and clean task lifecycle.

### Phase 4 - DX/QOL parity and release readiness

### Task `P4-T1`: Close local-to-CI check parity gaps

- **Description:** Ensure local standard checks mirror mandatory CI quality gates for backend.
- **Priority:** P1
- **Acceptance criteria (AC):**
  - AC1: `make check-python` (or documented equivalent) includes all mandatory backend gates.
  - AC2: Required test env vars are clearly documented and surfaced in scripts.
  - AC3: Contributors can run CI-equivalent backend checks with one command.
- **Inputs:** `Makefile`, `scripts/release_gates.sh`, `.github/workflows/ci.yml`, docs.
- **Outputs:** Updated automation/docs.
- **Dependencies:** P0-T1 baseline evidence.
- **Constraints:** Keep command runtime reasonable.
- **Tools available:** `make`, shell scripts, docs.
- **Steps / plan:**
  1. Compare Make/release scripts to CI requirements.
  2. Add missing checks or clear wrappers.
  3. Update docs with copy-paste parity commands.
- **Error handling:**
  - Expected failure modes: Longer local runtime causing low adoption.
  - Recovery steps: Offer fast and full profiles with clear expectations.
  - Rollback/backout conditions: If contributor velocity is materially harmed.
- **Validation / verification:**
  - Automated checks: Run parity command end-to-end locally.
  - Manual checks: Fresh clone onboarding dry run.
  - Observed evidence: Same failure classes caught locally and in CI.
- **Idempotency (re-run safety):**
  - Safe to re-run? Yes
  - If partial/no, guardrails required: N/A
- **State / progress tracking:**
  - Status: Todo
  - % complete: 0%
  - Last update: 2026-05-11
  - Owner: Developer experience owner
- **Related documents:** `README.md`, `backend/README.md`
- **References / examples:** `.github/workflows/ci.yml`
- **Ambiguity handling:**
  - If requirement is unclear: CI remains canonical.
  - If data conflicts: Prefer stricter gate.
  - Escalation owner: Engineering manager
- **Observability (logs, tracking):**
  - Logs/metrics/traces to add: Optional script summary of skipped checks.
  - Alert thresholds: N/A
  - Success signals: Reduced CI-only failures from parity mismatch.

### Task `P4-T2`: Release readiness checkpoint and go/no-go report

- **Description:** Execute final hardening verification and publish a go/no-go report mapped to this plan.
- **Priority:** P0
- **Acceptance criteria (AC):**
  - AC1: All P0/P1 tasks are Done or explicitly deferred with owner/date.
  - AC2: Release gates, targeted backend tests, and manual checks are attached as evidence.
  - AC3: Known residual risks are documented with mitigations.
- **Inputs:** Completed task artifacts, runbook checklist, CI results.
- **Outputs:** Launch readiness report.
- **Dependencies:** All preceding phases.
- **Constraints:** No hidden blockers; unresolved items must be explicit.
- **Tools available:** CI, release scripts, docs.
- **Steps / plan:**
  1. Run final verification matrix.
  2. Produce go/no-go summary with residual risks.
  3. Obtain sign-off from owners.
- **Error handling:**
  - Expected failure modes: Late-stage regression.
  - Recovery steps: Open blocker task and re-run affected matrix.
  - Rollback/backout conditions: Any unresolved P0 security/correctness issue.
- **Validation / verification:**
  - Automated checks: Full backend release gate + targeted suites.
  - Manual checks: Ingest to dashboard E2E, auth mutation checks, readiness/metrics checks.
  - Observed evidence: Signed checklist and stable CI.
- **Idempotency (re-run safety):**
  - Safe to re-run? Yes
  - If partial/no, guardrails required: Freeze branch during final run.
- **State / progress tracking:**
  - Status: Todo
  - % complete: 0%
  - Last update: 2026-05-11
  - Owner: Release owner
- **Related documents:** `docs/runbooks/PHASE5_RELEASE_CHECKLIST.md`
- **References / examples:** `scripts/release_gates.sh`
- **Ambiguity handling:**
  - If requirement is unclear: Default to no-go until clarified.
  - If data conflicts: CI and runtime evidence override assumptions.
  - Escalation owner: Product + engineering leads
- **Observability (logs, tracking):**
  - Logs/metrics/traces to add: None required; verify existing telemetry health.
  - Alert thresholds: Existing production thresholds in runbook.
  - Success signals: Explicit go decision with evidence links.

## 6) Plan-level execution strategy

- Delivery sequence:
  1. Phase 0 baseline
  2. Phase 1 security hardening
  3. Phase 2 alert/ingest correctness
  4. Phase 3 reliability instrumentation
  5. Phase 4 DX parity and release checkpoint
- Parallelization opportunities:
  - P1-T2 and P2-T2 can run in parallel after baseline.
  - P3-T2 can run parallel to P4-T1 if ownership differs.
- Risk register (top 3-5):
  - R1: Auth policy regression blocks dashboard admin flows.
  - R2: Alert semantics change causes noise or missed incidents.
  - R3: CI parity tightening increases local runtime and adoption drops.
  - R4: Repair instrumentation introduces high-cardinality metrics.
- Decision log:
  - Decision: Prioritize security and correctness before DX polish.
  - Why: Highest launch risk reduction per unit effort.
  - Date: 2026-05-11
  - Owner: Backend lead

## 7) Validation gate before completion

Mark each item before closing the plan:

- [ ] All tasks have explicit AC.
- [ ] All tasks define validation (automated + manual).
- [ ] Idempotency is documented for each task.
- [ ] Domain rules and constraints are mapped to tasks.
- [ ] Observability updates are included where behavior changed.
- [ ] Related docs are updated or explicitly deferred.
- [ ] Remaining ambiguity is logged with owner and due date.

## 8) Live execution tracker

### Current phase status snapshot

- **Completed tasks:** `P0-T1`, `P1-T1`, `P1-T2`, `P2-T1`, `P2-T2`, `P3-T1`
- **In progress tasks:** None
- **Todo tasks:** `P3-T2`, `P4-T1`, `P4-T2`
- **Overall completion (task-count based):** 6/9 (67%)
- **Last refreshed:** 2026-05-11

### Next-up execution queue (strict order)

1. `P4-T1` (local-to-CI parity) - lowers pre-release integration churn.
2. `P3-T2` (managed fanout task lifecycle) - reliability hardening with lower launch criticality.
3. `P4-T2` (go/no-go checkpoint) - final release decision artifact.

### Task handoff template (apply per task)

- **Kickoff checklist:**
  1. Re-state AC in PR description as a checklist.
  2. Link touched files and targeted tests.
  3. Capture before/after behavior in one short evidence note.
- **Completion checklist:**
  1. Mark task status and `% complete` in this plan.
  2. Add evidence link under "Execution evidence index".
  3. Note residual risk or "None" explicitly.

### Execution evidence index

- `P0-T1`: `docs/plans/backend-hardening-baseline-2026-05-11.md`
- `P1-T1`: Pending link to merged PR / commit SHA
- `P1-T2`: Pending link to merged PR / commit SHA
- `P2-T1`: Pending link to merged PR / commit SHA
- `P2-T2`: Pending link to merged PR / commit SHA
- `P3-T1`: Pending link to merged PR / commit SHA
- `P3-T2`: Pending
- `P4-T1`: Pending
- `P4-T2`: Pending

### Open ambiguity and blocker log

- **A1 (resolved 2026-05-11 by backend team):**
  Canonical alert counting contract locked to `error_like := (type == "error") OR (status_code >= 500)` for both SQL and DuckDB paths in `P2-T1`.
- **A2 (resolved 2026-05-11 by backend team):**
  Mandatory idempotency replay path is pinned to Postgres in CI (`python-postgres` job) and mirrored in local release-gate/docs commands.
- **A3 (resolved 2026-05-11 by backend team):**
  Replay/dead-letter instrumentation label set locked to low-cardinality queue gauges and replay outcome counters (`ingest.replay_queue.*`, `ingest.sql_tail.repair_*`).
