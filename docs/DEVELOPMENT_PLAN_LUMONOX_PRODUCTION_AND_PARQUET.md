# Lumonox Development Plan: Production Readiness + Parquet Rollout

Use this plan to move Lumonox from current state to production-safe operation while adding Parquet as a cold data layer alongside DuckDB.

## 1) Plan header

- **Plan name:** Production hardening and hot/cold data architecture rollout
- **Owner:** CTO (primary), Backend lead, Frontend lead, Ops owner
- **Date:** 2026-05-06
- **Status:** In Progress
- **Scope summary (2-4 lines):** Harden ingest reliability, scheduler/auth/realtime deployment posture, and operational observability. Add Parquet cold storage and hybrid query behavior while preserving fast dashboard diagnosis on hot data. Improve developer velocity and release confidence with CI/release parity and ownership guardrails.
- **Out of scope:** Full distributed tracing platform, custom dashboard builder, full APM feature parity, Kubernetes-specific orchestration.

## 2) Context / background

- Problem statement: Core product works, but production risk remains around topology, cross-store consistency, scheduler defaults, and multi-instance realtime behavior.
- Why now: Current code and docs are mature enough for production rollout, but key operational gaps can cause silent degradation or inconsistent diagnostics.
- Current behavior (as-is): DuckDB is primary hot store path; SQL still supports aggregate/dashboard slices; runbooks are present; release process and decomposition standards were improved.
- Desired behavior (to-be): Predictable production deployments with explicit guardrails, measurable reliability, and low-cost historical retention via Parquet without regressing hot-path diagnosis.
- User impact: Faster and more trustworthy incident diagnosis, fewer operational surprises, better historical analysis retention.
- Technical impact: New background export/reconciliation flows, hybrid query handling, stronger operational checks/alerts, and expanded validation coverage.

## 3) Domain rules and constraints

- Product/domain rules: Preserve MVP promise ("what broke, when, and what requests led to it") and keep diagnosis speed over configurability.
- Security/privacy rules: Keep auth enforced in production by default; never expose secrets in logs; maintain conservative data capture defaults.
- Performance/SLO constraints: Ingest endpoint must remain fast and resilient; heavy processing off request path; bounded retries/backoff.
- Compliance/governance constraints: Do not materially change governed documents without approval; keep plan aligned with `DEVELOPMENT.md`.
- Non-goals: Re-architecture into a multi-system observability platform.

## 4) Inputs, outputs, and dependencies

- **Inputs:** `DEVELOPMENT.md`, ops runbooks, ingest/dashboard schemas, existing metrics and health endpoints, audit findings.
- **Outputs:** backend/frontend code changes, new jobs/pipelines, docs/runbook updates, CI/release updates, rollout checklist.
- **Dependencies:** backend team, frontend team, operations owner, maintainer approvals where governance applies.
- **Tools available:** Cursor IDE, repo scripts, CI workflows, pytest/vitest/playwright, release gates, operational metrics endpoints.

## 5) Parquet all-phase roadmap (required)

- **Phase 1 (T03):** Background export from DuckDB hot tables to partitioned Parquet.
- **Phase 2 (T04):** Hybrid hot/cold query routing (DuckDB for recent, Parquet for historical windows).
- **Phase 3 (T10):** Parquet lifecycle management (compaction, retention tiers, vacuum/cleanup, restore validation).
- **Phase 4 (T11):** Object storage and integrity layer (S3-compatible snapshots, manifests, disaster recovery replay).
- **Exit criteria:** All four phases have implemented tasks, validation evidence, and runbook coverage before "Done."

## 6) Task breakdown

### Task T01: Production topology and config baseline

- **Description:** Establish a single approved production topology profile (single writer rules, scheduler flags, auth posture, realtime bus strategy) and enforce it in deployment configuration.
- **Priority:** P0
- **Acceptance criteria (AC):**
  - AC1: Production env template includes explicit values for scheduler, dashboard auth mode, realtime bus mode, and event-plane mode.
  - AC2: Staging boot logs and `/internal/metrics` prove expected settings are active.
  - AC3: Runbook checklist includes a pre-go-live config verification step.
- **Inputs:** `docs/ops/PRODUCTION_DEPLOYMENT.md`, `docs/ops/DEPLOYMENT_MULTI_INSTANCE.md`, backend config settings.
- **Outputs:** Environment baseline doc/update, deployment checklist update, verified staging evidence.
- **Dependencies:** Ops owner and backend lead.
- **Constraints:** No breaking changes to local developer defaults.
- **Tools available:** env files, startup logs, health/metrics endpoints.
- **Steps / plan:**
  1. Define approved production profile variants.
  2. Encode required env defaults and explicit override rules.
  3. Validate on staging and capture evidence.
- **Error handling:**
  - Expected failure modes: wrong env values, scheduler not running, auth mismatch.
  - Recovery steps: rollback to previous known-good env, apply corrected vars, restart.
  - Rollback/backout conditions: any auth exposure or ingestion instability.
- **Validation / verification:**
  - Automated checks: startup config validation tests.
  - Manual checks: confirm scheduler/realtime/auth metrics and readiness.
  - Observed evidence: screenshots/log snippets in release note.
- **Idempotency (re-run safety):**
  - Safe to re-run? Yes
  - If partial/no, guardrails required: N/A
- **State / progress tracking:**
  - Status: Done
  - % complete: 100
  - Last update: 2026-05-06 (added explicit production topology baseline in env/docs, topology verification contract in `/ready` + `/internal/metrics`, and pre-go-live release checklist step)
  - Owner: Backend + Ops
- **Related documents:** `docs/ops/PRODUCTION_DEPLOYMENT.md`, `docs/runbooks/PHASE5_RELEASE_CHECKLIST.md`
- **References / examples:** Existing deployment section examples in ops docs.
- **Ambiguity handling:**
  - If requirement is unclear: prefer stricter production-safe setting.
  - If data conflicts: follow `DEVELOPMENT.md` and ops deployment doc.
  - Escalation owner: CTO.
- **Observability (logs, tracking):**
  - Logs/metrics/traces to add: config profile active marker metric.
  - Alert thresholds: scheduler heartbeat stale > 2 intervals.
  - Success signals: stable ingest and active scheduler jobs.

### Task T02: Cross-store consistency repair (DuckDB + SQL tail)

- **Description:** Prevent or repair inconsistencies when DuckDB persistence succeeds but SQL aggregate/widget tail fails.
- **Priority:** P0
- **Acceptance criteria (AC):**
  - AC1: Failed SQL tail writes are recorded with replay-safe metadata.
  - AC2: Automated repair/retry job reconciles pending failures within SLA.
  - AC3: Dashboard consistency checks show no unresolved drift after repair.
- **Inputs:** ingest service logic, current failure metric (`persist_sql_tail_failed`), aggregate write paths.
- **Outputs:** consistency retry/repair worker, failure queue/state table, runbook section.
- **Dependencies:** backend data model and scheduler.
- **Constraints:** Must not slow ingest request path.
- **Tools available:** backend jobs, DB migrations, metrics.
- **Steps / plan:**
  1. Introduce durable failed-tail record model.
  2. Build retry worker with bounded attempts and dead-letter state.
  3. Add reconciliation endpoint/check and runbook flow.
- **Error handling:**
  - Expected failure modes: repeated SQL lock/conflict, malformed payload metadata.
  - Recovery steps: move poisoned items to dead-letter, alert operator, manual replay command.
  - Rollback/backout conditions: ingest latency regression above threshold.
- **Validation / verification:**
  - Automated checks: unit/integration tests for fail-then-repair flow.
  - Manual checks: inject tail failure in staging, verify eventual consistency.
  - Observed evidence: zero unresolved failed-tail items post-repair.
- **Idempotency (re-run safety):**
  - Safe to re-run? Yes (with idempotency key on repair records)
  - If partial/no, guardrails required: dedupe by ingest batch/event id.
- **State / progress tracking:**
  - Status: Done
  - % complete: 100
  - Last update: 2026-05-06 (added durable SQL-tail repair queue + scheduler replay job + bounded retry/dead-letter + ingest fallback + docs/tests)
  - Owner: Backend
- **Related documents:** `docs/ops/RUNBOOK_EVENT_PLANE_BACKPRESSURE.md`, `docs/ops/ADR_EVENT_STORE_SCALING.md`
- **References / examples:** existing ingest persistence metrics and failure signals.
- **Ambiguity handling:**
  - If requirement is unclear: prioritize correctness over immediate completeness.
  - If data conflicts: treat raw-event truth as source of replay.
  - Escalation owner: Backend lead.
- **Observability (logs, tracking):**
  - Logs/metrics/traces to add: retry queue size, repair success/failure rates, oldest pending age.
  - Alert thresholds: pending failures > 0 for 15 minutes.
  - Success signals: repair success rate > 99% with bounded queue age.

### Task T03: Parquet phase 1 export pipeline (cold layer)

- **Description:** Export hot event data from DuckDB to partitioned Parquet in background jobs for retention and historical analytics.
- **Priority:** P1
- **Acceptance criteria (AC):**
  - AC1: Partitioned Parquet files are generated by date/service/environment.
  - AC2: Export jobs are incremental and restart-safe.
  - AC3: Exported data row counts reconcile with source windows.
- **Inputs:** event schema, DuckDB tables, retention windows.
- **Outputs:** export job, partition layout spec, reconciliation report.
- **Dependencies:** scheduler, filesystem/object storage decision.
- **Constraints:** Export work must not degrade ingest SLA.
- **Tools available:** DuckDB SQL, background jobs, filesystem/S3-compatible targets.
- **Steps / plan:**
  1. Define partition strategy and file naming conventions.
  2. Implement watermark-based incremental exporter.
  3. Add reconciliation checks and failure retries.
- **Error handling:**
  - Expected failure modes: partial file writes, transient I/O errors.
  - Recovery steps: write temp files then atomic rename, retry failed partition.
  - Rollback/backout conditions: export job creates ingest contention.
- **Validation / verification:**
  - Automated checks: partition generation and watermark tests.
  - Manual checks: compare sample windows between DuckDB and Parquet outputs.
  - Observed evidence: reconciliation delta within tolerance (target zero).
- **Idempotency (re-run safety):**
  - Safe to re-run? Yes
  - If partial/no, guardrails required: watermark checkpoint + atomic partition replace.
- **State / progress tracking:**
  - Status: Done
  - % complete: 100
  - Last update: 2026-05-06 (implemented watermark-based DuckDB->Parquet exporter, partitioned output layout, row-count reconciliation, scheduler/CLI wiring, and docs/tests)
  - Owner: Backend data plane
- **Related documents:** `docs/ops/BACKUP_RESTORE.md`, `docs/ops/ADR_EVENT_STORE_SCALING.md`
- **References / examples:** DuckDB external Parquet read/write patterns.
- **Ambiguity handling:**
  - If requirement is unclear: choose partition granularity that favors query pruning.
  - If data conflicts: defer delete/compaction until reconciliation passes.
  - Escalation owner: CTO.
- **Observability (logs, tracking):**
  - Logs/metrics/traces to add: export duration, bytes written, partitions exported, failures.
  - Alert thresholds: export lag > 2 intervals.
  - Success signals: sustained low lag and successful reconciliation.

### Task T04: Hybrid hot/cold query path (DuckDB + Parquet)

- **Description:** Extend dashboard query layer to read recent windows from DuckDB hot data and older windows from Parquet cold data.
- **Priority:** P1
- **Acceptance criteria (AC):**
  - AC1: Query routing by time window is deterministic and documented.
  - AC2: User-visible responses preserve existing schema contracts.
  - AC3: Historical queries complete within target latency budget.
- **Inputs:** dashboard query bundle code, schemas, new Parquet partitions.
- **Outputs:** query planner/routing logic, test coverage, updated docs.
- **Dependencies:** Task T03.
- **Constraints:** No contract-breaking API changes.
- **Tools available:** backend query modules, schema tests, perf profiling.
- **Steps / plan:**
  1. Add read policy for hot vs cold windows.
  2. Merge/normalize result sets for existing response shape.
  3. Benchmark and tune query boundaries.
- **Error handling:**
  - Expected failure modes: missing partitions, duplicate windows.
  - Recovery steps: fallback to hot-only for missing partition, emit warning metric.
  - Rollback/backout conditions: latency or correctness regressions.
- **Validation / verification:**
  - Automated checks: contract tests on mixed hot/cold reads.
  - Manual checks: compare same window before/after migration.
  - Observed evidence: stable response shapes and acceptable latency.
- **Idempotency (re-run safety):**
  - Safe to re-run? Yes
  - If partial/no, guardrails required: deterministic window boundaries.
- **State / progress tracking:**
  - Status: Done
  - % complete: 100
  - Last update: 2026-05-07 (implemented deterministic hot/cold read boundary with Parquet fallback to DuckDB, wired config/metrics visibility, and added regression coverage for hybrid/fallback query paths)
  - Owner: Backend dashboard/data
- **Related documents:** `docs/contracts/ingest-api.md`, `backend/src/lumonox_backend/schemas/dashboard.py`
- **References / examples:** existing bundle query flow and schema models.
- **Ambiguity handling:**
  - If requirement is unclear: prioritize schema stability and diagnosis speed.
  - If data conflicts: prefer newer hot data, annotate uncertainty for cold fallback.
  - Escalation owner: Backend lead.
- **Observability (logs, tracking):**
  - Logs/metrics/traces to add: query source ratio (hot/cold), fallback counts, latency buckets.
  - Alert thresholds: fallback rate > 5% sustained.
  - Success signals: low fallback and stable P95 query latency.

### Task T05: Diagnosis confidence UX and deep-link reliability

- **Description:** Improve dashboard diagnosis trust signals for sample-limited views and make error-group deep links robust across pagination and time windows.
- **Priority:** P1
- **Acceptance criteria (AC):**
  - AC1: Users see explicit indicator when diagnosis data is partial/sampled.
  - AC2: Error-group deep links resolve reliably or provide guided fallback.
  - AC3: Scope propagation between diagnosis and requests remains stable.
- **Inputs:** diagnosis page components, dashboard data context behavior.
- **Outputs:** UI indicators, deep-link fallback logic, frontend tests.
- **Dependencies:** frontend team and QA.
- **Constraints:** Keep dashboard fast and avoid heavy additional fetches.
- **Tools available:** React components, vitest, Playwright e2e.
- **Steps / plan:**
  1. Add partial-data banner and actions.
  2. Implement deep-link resolution fetch/fallback path.
  3. Add targeted tests for diagnosis navigation.
- **Error handling:**
  - Expected failure modes: unresolved hash links, stale scope state.
  - Recovery steps: show guided "expand time window" action.
  - Rollback/backout conditions: major UX confusion or navigation regressions.
- **Validation / verification:**
  - Automated checks: component and e2e coverage for diagnosis flows.
  - Manual checks: incident drill scenario from Overview to Diagnosis to Requests.
  - Observed evidence: successful deep-link resolution rate.
- **Idempotency (re-run safety):**
  - Safe to re-run? Yes
  - If partial/no, guardrails required: preserve URL-state compatibility.
- **State / progress tracking:**
  - Status: Done
  - % complete: 100
  - Last update: 2026-05-07 (added diagnosis partial-scope confidence banner, deep-link retry + guided fallback actions, and focused unit coverage for deep-link/partial-scope logic)
  - Owner: Frontend
- **Related documents:** `DEVELOPMENT.md`, `docs/testing/E2E_CORE_JOURNEY.md`
- **References / examples:** current diagnosis/request navigation patterns.
- **Ambiguity handling:**
  - If requirement is unclear: optimize for five-second diagnosis clarity.
  - If data conflicts: favor transparent confidence messaging.
  - Escalation owner: Product + Frontend lead.
- **Observability (logs, tracking):**
  - Logs/metrics/traces to add: deep-link success/fallback counters, partial-data banner exposures.
  - Alert thresholds: N/A (product metric monitoring only).
  - Success signals: fewer diagnosis drop-offs and improved task completion.

### Task T10: Parquet phase 3 lifecycle management

- **Description:** Implement Parquet maintenance lifecycle: small-file compaction, retention tier enforcement, cleanup safety, and restore verification.
- **Priority:** P1
- **Acceptance criteria (AC):**
  - AC1: Compaction merges small partitions into query-efficient files on a schedule.
  - AC2: Retention policies move/delete cold partitions according to configured tiers.
  - AC3: Restore validation checks prove compacted/retained partitions are readable and complete.
- **Inputs:** Parquet partition outputs from T03, retention requirements, backup/restore runbooks.
- **Outputs:** lifecycle scheduler jobs, retention policy config, compaction manifests, restore verification report.
- **Dependencies:** T03 complete; scheduler active from T01.
- **Constraints:** Lifecycle jobs must not interfere with hot ingest/query operations.
- **Tools available:** background jobs, DuckDB Parquet tooling, runbook scripts.
- **Steps / plan:**
  1. Implement compaction job with safe temp output + atomic swap.
  2. Add tiered retention policy engine with dry-run mode.
  3. Add restore/readability verification job and alerting.
- **Error handling:**
  - Expected failure modes: compaction interruption, accidental retention over-delete.
  - Recovery steps: keep pre-compaction files until manifest commit; require retention dry-run approval.
  - Rollback/backout conditions: any detected data-loss or unreadable partitions.
- **Validation / verification:**
  - Automated checks: compaction/retention unit tests with synthetic partitions (`backend/tests/test_parquet_lifecycle.py`, plus parquet job/tick coverage in `backend/tests/test_backend_jobs.py`).
  - Manual checks: execute lifecycle on staging snapshots and compare row counts pre/post.
  - Observed evidence: compaction ratio improvements and zero reconciliation loss.
- **Idempotency (re-run safety):**
  - Safe to re-run? Yes (manifest-driven)
  - If partial/no, guardrails required: partition lock + manifest version checks.
- **State / progress tracking:**
  - Status: Done
  - % complete: 100
  - Last update: 2026-05-07 (implemented lifecycle worker/CLI for Parquet compaction + tiered retention + readability verification, added metrics + config surface, and covered with lifecycle/job tests)
  - Owner: Backend data plane + Ops
- **Related documents:** `docs/ops/BACKUP_RESTORE.md`, `docs/ops/EVENT_PLANE_DISASTER_RECOVERY_DRILLS.md`
- **References / examples:** existing compactor and DR evidence docs.
- **Ambiguity handling:**
  - If requirement is unclear: default to conservative retention (keep data longer).
  - If data conflicts: block deletion and escalate with reconciliation report.
  - Escalation owner: CTO + Ops lead.
- **Observability (logs, tracking):**
  - Logs/metrics/traces to add: compaction ratio, files before/after, retention deletes, verify pass/fail.
  - Alert thresholds: restore verification failure > 0.
  - Success signals: stable query latency on historical windows with reduced storage fragmentation.

### Task T11: Parquet phase 4 object storage and integrity manifests

- **Description:** Add optional object-storage sink for Parquet snapshots with integrity manifests and replay procedures for disaster recovery.
- **Priority:** P1
- **Acceptance criteria (AC):**
  - AC1: Export pipeline can publish partitions/manifests to S3-compatible object storage.
  - AC2: Integrity verification validates checksum and manifest continuity.
  - AC3: DR drill can restore a historical window from object storage into queryable state.
- **Inputs:** outputs from T03/T10, object storage credentials/policies, DR runbooks.
- **Outputs:** object storage uploader, manifest/checksum schema, restore-from-object-storage workflow.
- **Dependencies:** T03 and T10.
- **Constraints:** Credentials must be managed securely; no secret leakage in logs.
- **Tools available:** object storage SDK/CLI, background jobs, DR drill environment.
- **Steps / plan:**
  1. Define manifest format and checksum policy.
  2. Implement uploader with retry/backoff and resumable transfers.
  3. Implement restore job using manifests and validate via drill.
- **Error handling:**
  - Expected failure modes: upload interruption, corrupted object, missing manifest segment.
  - Recovery steps: resumable upload, quarantine corrupt objects, replay last good checkpoint.
  - Rollback/backout conditions: inability to validate manifest chain integrity.
- **Validation / verification:**
  - Automated checks: manifest generation/verification tests (`backend/tests/test_parquet_object_storage.py`, CLI flows in `backend/tests/test_backend_jobs.py`).
  - Manual checks: run DR replay drill from object storage snapshots.
  - Observed evidence: successful replay and checksum validation for sampled partitions.
- **Idempotency (re-run safety):**
  - Safe to re-run? Yes
  - If partial/no, guardrails required: immutable object keys and manifest versioning.
- **State / progress tracking:**
  - Status: Done
  - % complete: 100
  - Last update: 2026-05-07 (added optional object-storage sync + manifest continuity checks + restore CLI path with checksum verification and job wiring)
  - Owner: Backend + Ops
- **Related documents:** `docs/ops/BACKUP_RESTORE.md`, `docs/ops/EVENT_PLANE_DISASTER_RECOVERY_DRILLS.md`, `docs/ops/PRODUCTION_DEPLOYMENT.md`
- **References / examples:** current backup/restore process and DR drill templates.
- **Ambiguity handling:**
  - If requirement is unclear: prefer simpler immutable snapshot policy first.
  - If data conflicts: treat manifest as source of truth and block promotion.
  - Escalation owner: CTO.
- **Observability (logs, tracking):**
  - Logs/metrics/traces to add: upload success rate, bytes transferred, checksum failures, replay duration.
  - Alert thresholds: checksum failures > 0 or replay failure.
  - Success signals: periodic successful restore drills from object storage.

### Task T06: Release-gate and CI parity

- **Description:** Align local release gates and release checklist with CI-critical checks (security audits, frontend budget checks, e2e smoke) to reduce "passes locally, fails in CI."
- **Priority:** P1
- **Acceptance criteria (AC):**
  - AC1: Release gate script mirrors required CI checks or clearly documents intentional subset.
  - AC2: Release checklist references updated gate behavior.
  - AC3: One dry-run release validates the new flow.
- **Inputs:** CI workflow files, release gate script, release checklist doc.
- **Outputs:** updated script/workflow docs and release process notes.
- **Dependencies:** DevEx owner and maintainers.
- **Constraints:** Keep gate runtime reasonable for developer usage.
- **Tools available:** shell scripts, CI workflows, npm/pytest tooling.
- **Steps / plan:**
  1. Diff CI checks vs release gates.
  2. Add missing checks or explicit policy note.
  3. Validate end-to-end on branch.
- **Error handling:**
  - Expected failure modes: flaky e2e, long runtime pushback.
  - Recovery steps: retry strategy for known flaky tests, split optional vs required.
  - Rollback/backout conditions: unacceptable release latency without value.
- **Validation / verification:**
  - Automated checks: run release script and compare outputs to CI job matrix.
  - Manual checks: review release checklist completeness.
  - Observed evidence: reduced CI surprise failures.
- **Idempotency (re-run safety):**
  - Safe to re-run? Yes
  - If partial/no, guardrails required: N/A
- **State / progress tracking:**
  - Status: Done
  - % complete: 100
  - Last update: 2026-05-06 (mypy clean; release_gates.sh + Makefile bandit invocation matches CI; full release gates dry-run passed)
  - Owner: DevEx
- **Related documents:** `docs/runbooks/PHASE5_RELEASE_CHECKLIST.md`, `.github/workflows/ci.yml`
- **References / examples:** existing `scripts/release_gates.sh`.
- **Ambiguity handling:**
  - If requirement is unclear: prioritize production-risk checks as mandatory.
  - If data conflicts: CI remains source of truth until parity is complete.
  - Escalation owner: CTO.
- **Observability (logs, tracking):**
  - Logs/metrics/traces to add: gate duration and failure reason summary.
  - Alert thresholds: N/A
  - Success signals: lower PR-to-merge friction and fewer post-merge failures.

### Task T07: Ownership and dependency hygiene guardrails

- **Description:** Add CODEOWNERS and dependency update automation to improve security and maintainability velocity.
- **Priority:** P2
- **Acceptance criteria (AC):**
  - AC1: CODEOWNERS enforces review on auth/ingest/ops critical files.
  - AC2: Automated dependency updates are enabled for Python and frontend.
  - AC3: CI validates update PRs reliably.
- **Inputs:** repository structure, current workflow rules.
- **Outputs:** `CODEOWNERS`, dependency bot config, docs note.
- **Dependencies:** maintainer review policy.
- **Constraints:** Avoid review bottlenecks for routine low-risk changes.
- **Tools available:** GitHub workflow/config files.
- **Steps / plan:**
  1. Define critical ownership paths.
  2. Add dependency update configuration.
  3. Validate PR automation and reviewer routing.
- **Error handling:**
  - Expected failure modes: noisy update PR volume.
  - Recovery steps: batch schedules, grouping rules.
  - Rollback/backout conditions: unsustainable review load.
- **Validation / verification:**
  - Automated checks: test sample dependency bump PR in CI.
  - Manual checks: verify reviewer assignment on sensitive path changes.
  - Observed evidence: regular patch cadence and controlled update noise.
- **Idempotency (re-run safety):**
  - Safe to re-run? Yes
  - If partial/no, guardrails required: keep config deterministic.
- **State / progress tracking:**
  - Status: Done
  - % complete: 100
  - Last update: 2026-05-06 (implemented CODEOWNERS + Dependabot config + contributing guidance)
  - Owner: CTO + maintainers
- **Related documents:** `CONTRIBUTING.md`, CI workflow docs.
- **References / examples:** GitHub CODEOWNERS and Dependabot/Renovate conventions.
- **Ambiguity handling:**
  - If requirement is unclear: enforce strictness for high-risk paths only.
  - If data conflicts: prefer least-disruptive ownership defaults first.
  - Escalation owner: CTO.
- **Observability (logs, tracking):**
  - Logs/metrics/traces to add: monthly dependency age and update success KPI.
  - Alert thresholds: security advisory PRs older than SLA.
  - Success signals: predictable security patch cadence.

### Task T08: Dev workflow and plan execution ergonomics

- **Description:** Improve developer productivity by unifying task runner commands and tightening docs around bootstrap, release gates, and plan-to-task execution workflow.
- **Priority:** P2
- **Acceptance criteria (AC):**
  - AC1: Single root command entrypoint covers setup, test, and release gates.
  - AC2: CONTRIBUTING and docs index reflect canonical workflow.
  - AC3: New task-plan template is referenced in team process.
- **Inputs:** existing scripts, docs, new template and rule.
- **Outputs:** root task runner file, doc updates, workflow snippet.
- **Dependencies:** team agreement on command names.
- **Constraints:** Keep commands backward compatible when possible.
- **Tools available:** scripts, markdown docs, pre-commit hooks.
- **Steps / plan:**
  1. Add root command wrapper (`make` or `just`).
  2. Update docs and examples.
  3. Validate onboarding from clean checkout.
- **Error handling:**
  - Expected failure modes: platform-specific shell behavior.
  - Recovery steps: add OS-safe wrappers and clear fallback commands.
  - Rollback/backout conditions: command layer adds confusion instead of reducing it.
- **Validation / verification:**
  - Automated checks: command smoke in CI/local.
  - Manual checks: follow onboarding steps from scratch.
  - Observed evidence: reduced onboarding/setup time.
- **Idempotency (re-run safety):**
  - Safe to re-run? Yes
  - If partial/no, guardrails required: commands should be no-op when already configured.
- **State / progress tracking:**
  - Status: Done
  - % complete: 100
  - Last update: 2026-05-06 (added root Makefile workflow + README/CONTRIBUTING canonical commands)
  - Owner: DevEx
- **Related documents:** `README.md`, `CONTRIBUTING.md`, `docs/DEVELOPMENT_PROCESS.md`
- **References / examples:** `scripts/bootstrap_local.sh`, `scripts/release_gates.sh`.
- **Ambiguity handling:**
  - If requirement is unclear: optimize for first-time contributor flow.
  - If data conflicts: docs under `README.md` + CONTRIBUTING are source of truth.
  - Escalation owner: DevEx lead.
- **Observability (logs, tracking):**
  - Logs/metrics/traces to add: onboarding completion checklist pass rate.
  - Alert thresholds: N/A
  - Success signals: faster successful first local run.

### Task T09: Production drills and recovery automation

- **Description:** Turn incident/runbook drills (scheduler, backpressure, restore, auth modes) into recurring tracked execution with explicit evidence artifacts.
- **Priority:** P1
- **Acceptance criteria (AC):**
  - AC1: Drill cadence and owners are defined and scheduled.
  - AC2: Each drill run stores evidence and remediation notes.
  - AC3: Restore and event-plane failure drills meet documented success thresholds.
- **Inputs:** incident and release runbooks, backup/DR docs.
- **Outputs:** drill calendar/checklist, evidence archive process, action tracker.
- **Dependencies:** Ops owner availability.
- **Constraints:** Drills must not impact production user traffic.
- **Tools available:** staging environment, runbooks, health/metrics endpoints.
- **Steps / plan:**
  1. Create recurring drill schedule.
  2. Standardize evidence capture format.
  3. Review and close action items each cycle.
- **Error handling:**
  - Expected failure modes: failed drill due to env drift.
  - Recovery steps: patch drift, rerun drill, record exception.
  - Rollback/backout conditions: N/A (drill task).
- **Validation / verification:**
  - Automated checks: N/A (process heavy).
  - Manual checks: execute all listed drill scenarios.
  - Observed evidence: completed drill reports and action closure.
- **Idempotency (re-run safety):**
  - Safe to re-run? Yes
  - If partial/no, guardrails required: isolate drill in staging/sandbox.
- **State / progress tracking:**
  - Status: Done
  - % complete: 100
  - Last update: 2026-05-07 (added recurring drill cadence, evidence template, shared evidence log, and cross-links from incident/Parquet runbooks)
  - Owner: Ops
- **Related documents:** `docs/runbooks/PHASE5_INCIDENT_DRILLS.md`, `docs/runbooks/PHASE5_DRILL_CYCLE.md`, `docs/runbooks/PHASE5_DRILL_EVIDENCE_LOG.md`, `docs/ops/BACKUP_RESTORE.md`, `docs/ops/EVENT_PLANE_DISASTER_RECOVERY_DRILLS.md`
- **References / examples:** existing phase 5 runbook scenarios.
- **Ambiguity handling:**
  - If requirement is unclear: favor most severe plausible failure scenario first.
  - If data conflicts: use runbook-defined acceptance thresholds.
  - Escalation owner: CTO + Ops.
- **Observability (logs, tracking):**
  - Logs/metrics/traces to add: drill pass/fail trend and unresolved action count.
  - Alert thresholds: unresolved P0 drill finding > 7 days.
  - Success signals: consecutive successful drill cycles.

## 7) Plan-level execution strategy

- Delivery sequence: T01 -> T02 -> T03 -> T04 -> T10 -> T11 in core backend stream; run T05 and T06 in parallel after T01 starts; run T07/T08/T09 in parallel as capacity allows.
- Parallelization opportunities: frontend (T05), DevEx/CI (T06-T08), and Ops drills (T09) can proceed while Parquet phases advance sequentially.
- Risk register (top 3-5):
  - Ingest performance regression from consistency/export changes.
  - Data mismatch between hot and cold layers.
  - Operational misconfiguration in multi-instance deployments.
  - Query latency regressions on historical windows.
  - Object storage manifest integrity drift if checks are incomplete.
  - Team throughput reduction if release gates become too heavy.
- Decision log:
  - Decision: Keep DuckDB as hot store; add Parquet as cold layer.
  - Why: preserves diagnosis speed while improving retention economics and resilience.
  - Date: 2026-05-06
  - Owner: CTO

## 8) Validation gate before completion

Mark each item before closing the plan:

- [x] All tasks have explicit AC.
- [x] All tasks define validation (automated + manual).
- [x] Idempotency is documented for each task.
- [x] Domain rules and constraints are mapped to tasks.
- [x] Observability updates are included where behavior changed.
- [x] Related docs are updated or explicitly deferred.
- [x] Remaining ambiguity is logged with owner and due date.
