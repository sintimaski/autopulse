# AutoPulse — Production Readiness Task Backlog

**Audience:** Engineering, Product, SRE
**Date:** 2026-05-05
**Status:** Execution backlog derived from [AUTOPULSE_PRODUCTION_READINESS_MASTER_AUDIT.md](./AUTOPULSE_PRODUCTION_READINESS_MASTER_AUDIT.md)
**Related:** [AUTOPULSE_FULL_AUDIT_ROADMAP.md](./AUTOPULSE_FULL_AUDIT_ROADMAP.md), [PRODUCTION_DEPLOYMENT.md](./ops/PRODUCTION_DEPLOYMENT.md)

This document translates the master audit into implementation-ready tasks. It does not override product scope in [DEVELOPMENT.md](../DEVELOPMENT.md).

---

## How to use this backlog

- **P0:** Launch blockers; complete before production traffic.
- **P1:** Stabilization work; target first 30 days after launch.
- **P2:** Strategic hardening; 60-90 day horizon.
- **Task status:** `Todo` | `In Progress` | `Blocked` | `Done`.

Each task includes:

- Description (what to change and why)
- Acceptance criteria (definition of done)
- Related data/signals (what to observe or validate)
- Related files/docs (where to implement or update)

---

## P0 — Launch blockers

### TSK-P0-01 — Golden path runbook for SQLite + DuckDB

- **Priority:** P0
- **Status:** Done
- **Owner:** SRE + Docs
- **Source findings:** #1, #2 (Top 15), B1/B2
- **Description:** Publish a single canonical runbook for the default embedded topology: SQLite metadata + DuckDB events, including file locations, backup/restore of both stores, scheduler behavior, and constraints (single process/single writer assumptions).
- **Acceptance criteria:**
  - Runbook documents default file paths and `AUTOPULSE_DATA_DIR` behavior.
  - Runbook explicitly covers backup/restore for both metadata DB and DuckDB.
  - Runbook states scheduler auto-enable behavior only for default SQLite path set.
  - Runbook includes clear "when to move metadata DB off SQLite" guidance.
- **Related data/signals:**
  - Successful backup + restore drill logs.
  - `/ready` and `/internal/metrics` validation during drill.
- **Related files/docs:**
  - `docs/ops/PRODUCTION_DEPLOYMENT.md`
  - `docs/ops/BACKUP_RESTORE.md`
  - `backend/src/autopulse_backend/core/config.py`
- **Completed (2026-05-05):** Added canonical golden-path section for embedded SQLite metadata + DuckDB events, including default paths and `AUTOPULSE_DATA_DIR` anchoring. Backup/restore now explicitly requires both metadata (`.db`/WAL/SHM) and DuckDB files. Docs now state scheduler auto-enable applies only to default SQLite filenames and include concrete guidance on when to migrate metadata DB off SQLite.

### TSK-P0-02 — Explicit scheduler requirement outside default SQLite path

- **Priority:** P0
- **Status:** Done
- **Owner:** SRE + Backend
- **Source findings:** #2 (Top 15), B1
- **Description:** Eliminate silent scheduler disablement for non-default metadata DB setups by codifying env requirements and surfacing scheduler state clearly in readiness/metrics.
- **Acceptance criteria:**
  - Production env template and docs require `JOBS_ENABLE_SCHEDULER=true` or external cron for non-default SQLite metadata DB.
  - Scheduler state is visible via readiness payload and/or internal metrics.
  - No-go condition is documented and tested in staging.
- **Related data/signals:**
  - `jobs_enable_scheduler` config value in runtime diagnostics.
  - Metrics indicating scheduler ticks are present when expected.
- **Related files/docs:**
  - `backend/src/autopulse_backend/core/config.py`
  - `backend/src/autopulse_backend/api/routes/health.py`
  - `docs/ops/PRODUCTION_DEPLOYMENT.md`
  - `docs/runbooks/PHASE5_RELEASE_CHECKLIST.md`
  - `backend/.env.example`
- **Completed (2026-05-05):** `GET /ready` returns `jobs_enable_scheduler` and `scheduler_running`; `.env.example` and production docs/checklist codify non-default DB scheduler requirements and No-Go without scheduler or documented external cron. Automated tests cover `/ready` payload; staging topology drill remains operator evidence per release checklist.

### TSK-P0-03 — DuckDB topology enforcement for production

- **Priority:** P0
- **Status:** Done
- **Owner:** SRE
- **Source findings:** #3 (Top 15), B2
- **Description:** Make single-writer DuckDB operation explicit and enforceable in deployment guidance to prevent multi-writer corruption/lock failure modes.
- **Acceptance criteria:**
  - Deployment docs define supported topology for DuckDB event writes.
  - Staging validation run with intended replica count confirms no unsupported writer pattern.
  - No-go trigger is present in production checklist.
- **Related data/signals:**
  - Staging load test evidence showing stable event writes.
  - No lock/corruption class errors in logs during scale test.
- **Related files/docs:**
  - `docs/ops/DEPLOYMENT_MULTI_INSTANCE.md`
  - `docs/ops/PRODUCTION_DEPLOYMENT.md`
  - `docs/AUTOPULSE_PRODUCTION_READINESS_MASTER_AUDIT.md`
- **Completed (2026-05-05):** Deployment runbooks now define DuckDB as a single-writer production pattern and mark multi-replica writers against one DuckDB file as No-Go. Phase 5 release checklist includes topology and staging lock/corruption validation gates; multi-instance doc includes explicit staging validation steps.

### TSK-P0-04 — WebSocket + load balancer correctness

- **Priority:** P0
- **Status:** Done
- **Owner:** SRE + Frontend
- **Source findings:** #4 (Top 15), B6
- **Description:** Ensure live dashboard updates remain correct under multi-replica deployments via sticky sessions or a single WebSocket-serving replica.
- **Acceptance criteria:**
  - Runbook documents required LB behavior for WebSocket traffic.
  - Staging test proves live updates remain fresh under target topology.
  - Troubleshooting section includes stale-live symptom and remediation.
- **Related data/signals:**
  - Live update timestamps across session refreshes and replicas.
  - LB config validation evidence for stickiness (or single WS replica).
- **Related files/docs:**
  - `docs/ops/PRODUCTION_DEPLOYMENT.md`
  - `backend/src/autopulse_backend/realtime/connection_hub.py`
  - `frontend/components/dashboard/dashboardPages/OverviewContent.tsx`
- **Completed (2026-05-05):** Multi-instance runbooks now require sticky LB behavior for WS or a dedicated single WS replica, include a staging WS freshness validation procedure, and document stale-live symptoms with concrete remediation steps. Phase 5 release checklist now gates WS correctness evidence for target topology.

### TSK-P0-05 — SDK idempotency + retry behavior hardening

- **Priority:** P0
- **Status:** Done
- **Owner:** SDK + Backend
- **Source findings:** #5 (Top 15), S2/S3
- **Description:** Add per-batch `Idempotency-Key` from SDK and tighten retry policy to avoid retry storms and duplicate ingest on timeout/retry.
- **Acceptance criteria:**
  - SDK emits `Idempotency-Key` for each batch request.
  - SDK does not retry non-retryable 4xx (e.g. 413, 422).
  - SDK honors `Retry-After` for 429 when present.
  - Integration tests verify dedup behavior end-to-end.
- **Related data/signals:**
  - Ingest dedup hit rates in internal metrics.
  - SDK send logs/telemetry indicating retry decision class.
- **Related files/docs:**
  - `sdk/src/autopulse/_monitor.py`
  - `sdk/tests/test_monitor.py`
  - `backend/src/autopulse_backend/routes/ingest.py`
  - `backend/tests/test_ingest.py`
- **Completed (2026-05-05):** SDK now sends per-batch `Idempotency-Key` and reuses it across retries, does not retry non-retryable 4xx responses (for example 413/422), and honors `Retry-After` on 429 before retrying. Existing backend idempotency integration coverage plus new SDK retry/idempotency tests verify dedup/retry behavior end-to-end.

### TSK-P0-06 — Prevent half-configured SDK monitor lifecycle

- **Priority:** P0
- **Status:** Done
- **Owner:** SDK
- **Source findings:** S1
- **Description:** Ensure `monitor()` either completes lifecycle setup fully or fails cleanly without leaving partially attached middleware/background sender state.
- **Acceptance criteria:**
  - Startup/shutdown registration failures do not leave monitor in partial state.
  - Unit/integration tests cover lifecycle error branches.
  - Behavior preserves "do not break host app" rule.
- **Related data/signals:**
  - Test evidence for rollback/cleanup on setup failure.
  - No residual background sender threads/tasks after failure path.
- **Related files/docs:**
  - `sdk/src/autopulse/_monitor.py`
  - `sdk/tests/test_monitor.py`
- **Completed (2026-05-05):** `monitor()` now applies lifecycle setup transactionally: startup/shutdown handler registration and middleware attachment either all succeed or are rolled back. New SDK tests cover startup registration failure, shutdown registration failure, and middleware attach failure to ensure no partial monitor state is left behind.

### TSK-P0-07 — Uniform body-size protection for OTLP + ingest

- **Priority:** P0
- **Status:** Done
- **Owner:** Backend
- **Source findings:** #6 (Top 15), S4
- **Description:** Apply consistent request-size guardrails across ingestion surfaces so OTLP cannot bypass protections that exist on `/ingest`.
- **Acceptance criteria:**
  - Oversized OTLP payloads are rejected safely and predictably.
  - Request-size limit behavior is documented and test-covered.
  - No unbounded parse path remains on ingestion endpoints.
- **Related data/signals:**
  - Request rejection counts by endpoint and reason.
  - Load test confirms memory usage remains bounded for oversize traffic.
- **Related files/docs:**
  - `backend/src/autopulse_backend/ingestion/body_size.py`
  - `backend/src/autopulse_backend/app.py`
  - `backend/tests/ingestion/`
- **Completed (2026-05-05):** Ingest body-size middleware now enforces `INGEST_MAX_REQUEST_BYTES` across both `/ingest` and OTLP trace endpoints (`/otlp/v1/traces`, `/ingest/otlp/v1/traces`) including chunked/no-Content-Length bodies. Added OTLP oversize regression coverage alongside ingest body-size tests.

### TSK-P0-08 — Decouple Alembic migration from multi-replica API boot

- **Priority:** P0
- **Status:** Done
- **Owner:** Backend + SRE
- **Source findings:** #7 (Top 15), B3
- **Description:** Reduce DDL race risk by documenting and implementing a migration strategy that avoids every API replica running migrations on startup in production.
- **Acceptance criteria:**
  - Production deployment docs define a one-shot migration step.
  - API supports disabling migrate-on-boot where needed.
  - Staging rollout validates safe startup of multiple replicas.
- **Related data/signals:**
  - Deployment logs show single migration executor.
  - No migration race errors during rolling deploy test.
- **Related files/docs:**
  - `backend/src/autopulse_backend/lifespan.py`
  - `backend/src/autopulse_backend/core/config.py`
  - `docs/ops/PRODUCTION_DEPLOYMENT.md`
  - `docs/ops/DEPLOYMENT_MULTI_INSTANCE.md`
  - `docs/runbooks/PHASE5_RELEASE_CHECKLIST.md`
  - `backend/.env.example`
- **Completed (2026-05-05):** `DATABASE_RUN_MIGRATIONS_ON_STARTUP` gates Alembic in lifespan; canonical and multi-instance docs plus Phase 5 checklist require one-shot `alembic upgrade head` and `false` on steady-state API replicas. `/ready` exposes `database_run_migrations_on_startup`. Unit tests cover flag and readiness fields; multi-replica staging evidence per operator release gate.

### TSK-P0-09 — Official container artifact for repeatable self-hosting

- **Priority:** P0
- **Status:** Done
- **Owner:** Platform + SRE
- **Source findings:** #10 (Top 15), O1
- **Description:** Provide a supported container build for backend + static dashboard mount to reduce deployment drift and onboarding friction.
- **Acceptance criteria:**
  - Repo includes official `Dockerfile` and usage docs.
  - Image starts API, serves static dashboard, passes health/ready checks.
  - Example deployment spec (compose or minimal Helm stub) is available.
- **Related data/signals:**
  - Image build logs and published artifact metadata.
  - Smoke test output for `/health` and `/ready` in containerized run.
- **Related files/docs:**
  - `Dockerfile`
  - `docs/ops/PRODUCTION_DEPLOYMENT.md`
  - `frontend/` build artifact integration path
- **Completed (2026-05-05):** Official multi-stage `Dockerfile`, `docs/ops/docker-compose.autopulse.yml`, and production doc §11 cover build and manual smoke. `scripts/docker_smoke.sh` automates build plus `/health` and `/ready` checks with a production-shaped env; run it where Docker is available and attach logs for release evidence.

### TSK-P0-10 — CI browser smoke for core journey

- **Priority:** P0
- **Status:** Done
- **Owner:** Frontend + Delivery
- **Source findings:** #11 (Top 15), F1/O2
- **Description:** Add minimal browser smoke coverage in CI for sign-in and diagnosis-critical flows to catch regressions currently missed by static/unit checks.
- **Acceptance criteria:**
  - CI includes a stable smoke suite covering login + overview + diagnosis entry path.
  - Failures block merges/releases for protected branches.
  - Test maintenance and local run instructions are documented.
- **Related data/signals:**
  - CI job pass/fail trend for smoke suite.
  - Coverage mapping against `E2E_CORE_JOURNEY.md`.
- **Related files/docs:**
  - `.github/workflows/ci.yml`
  - `docs/testing/E2E_CORE_JOURNEY.md`
  - `frontend/tests/e2e/`
- **Completed (2026-05-05):** Added Playwright smoke suite (`frontend/tests/e2e/core-journey.spec.ts`) plus config and npm scripts. CI now includes blocking `browser-smoke` job that builds static UI, starts backend, waits for `/ready`, and runs Playwright. Local maintenance/run instructions are documented in `docs/testing/E2E_CORE_JOURNEY.md`.

### TSK-P0-11 — Auth modes clarity and validation (basic vs host-integrated)

- **Priority:** P0
- **Status:** Done
- **Owner:** Product + Backend + Docs
- **Source findings:** #13 (Top 15), B7
- **Description:** Clarify and validate both accepted production auth modes: first-party basic auth path and host/SSO-integrated path, including misconfiguration guardrails.
- **Acceptance criteria:**
  - Docs provide two explicit deployment checklists: basic mode and host-integrated mode.
  - Production checklist warns against exposed dashboard with auth disabled.
  - Staging validation executed for at least one flow per mode.
- **Related data/signals:**
  - Auth mode config matrix and pass/fail results.
  - Access control test evidence for protected dashboard routes.
- **Related files/docs:**
  - `docs/ops/PRODUCTION_DEPLOYMENT.md`
  - `docs/AUTOPULSE_PRODUCTION_READINESS_MASTER_AUDIT.md`
  - `backend/src/autopulse_backend/core/config.py`
- **Completed (2026-05-05):** Production deployment docs now define two explicit auth mode checklists (first-party magic-link and host/OIDC-integrated), including required env configuration and staging validation steps. Release checklist now includes auth-mode evidence and warns that externally exposed dashboard with `DASHBOARD_AUTH_ENABLED=false` is No-Go unless upstream auth protection is documented.

### TSK-P0-12 — Read-path rate limits for expensive dashboard endpoints

- **Priority:** P0
- **Status:** Done
- **Owner:** Backend
- **Source findings:** #14 (Top 15), §4.3
- **Description:** Protect metadata DB and API responsiveness by introducing rate limits or equivalent controls on high-cost dashboard read/query endpoints.
- **Acceptance criteria:**
  - Heavy query endpoints are identified and protected.
  - Limits are configurable and documented for SQLite and upgraded DB topologies.
  - Abuse tests demonstrate graceful rejection under load.
- **Related data/signals:**
  - 429 counts and endpoint-level latency before/after.
  - DB saturation signals during abuse/load tests.
- **Related files/docs:**
  - `backend/src/autopulse_backend/routes/`
  - `backend/src/autopulse_backend/services/`
  - `docs/ops/PRODUCTION_DEPLOYMENT.md`
- **Completed (2026-05-05):** Added configurable per-project dashboard read rate limiting on expensive endpoints (`/dashboard/query`, `/dashboard/query-explorer/execute`) with `429` + `Retry-After` responses. Introduced `DASHBOARD_READ_RATE_LIMIT_REQUESTS_PER_WINDOW` and `DASHBOARD_READ_RATE_LIMIT_WINDOW_SECONDS` settings and documented them for production. Added abuse tests proving graceful rejection under load.

### TSK-P0-13 — Postgres optional-path CI policy parity

- **Priority:** P0
- **Status:** Done
- **Owner:** Delivery + Backend
- **Source findings:** #15 (Top 15), §8.5
- **Description:** Define and enforce policy for non-default metadata DB quality signals (full parity or explicit subset) so upgrade users are not operating on unknown risk.
- **Acceptance criteria:**
  - CI policy explicitly states parity scope between SQLite and Postgres jobs.
  - CI pipeline reflects policy (expanded tests or documented subset).
  - Policy is published in contributor/deployment docs.
- **Related data/signals:**
  - CI matrix coverage by DB backend.
  - Historical failure classification by backend path.
- **Related files/docs:**
  - `.github/workflows/ci.yml`
  - `scripts/release_gates.sh`
  - `docs/ops/PRODUCTION_DEPLOYMENT.md`
- **Completed (2026-05-05):** Defined explicit CI policy: SQLite is full baseline gate, Postgres is required optional-path backend gate. CI workflow now annotates this policy, production deployment docs publish it, and `scripts/release_gates.sh` supports explicit local Postgres optional-path verification via `AUTOPULSE_RELEASE_GATES_POSTGRES=1`.

---

## P1 — 30-day stabilization

### TSK-P1-01 — Distributed rate-limit race hardening

- **Priority:** P1
- **Status:** Todo
- **Owner:** Backend
- **Source findings:** #8 (Top 15), B5
- **Description:** Remove first-hit race condition that can surface as server errors under concurrent distributed rate limit inserts.
- **Acceptance criteria:**
  - Concurrency-safe upsert/handling prevents IntegrityError leaks.
  - Regression test reproduces previous race and validates fix.
  - Ingest availability remains stable under synthetic burst.
- **Related data/signals:**
  - 5xx rate on ingest under concurrent bursts.
  - Error logs for unique constraint collisions.
- **Related files/docs:**
  - `backend/src/autopulse_backend/services/distributed_rate_limit.py`
  - `backend/tests/ingestion/`

### TSK-P1-02 — Ingest cross-store consistency strategy

- **Priority:** P1
- **Status:** Todo
- **Owner:** Backend
- **Source findings:** #9 (Top 15), B4
- **Description:** Define and implement recovery/compensation for partial failures between DuckDB event writes and SQL aggregate/widget updates.
- **Acceptance criteria:**
  - Consistency strategy documented (outbox/reconcile/retry pattern).
  - Metric exists for SQL lag or reconciliation backlog.
  - Failure-injection test demonstrates recovery path.
- **Related data/signals:**
  - Reconciliation lag metrics.
  - Event-to-aggregate mismatch counters.
- **Related files/docs:**
  - `backend/src/autopulse_backend/services/ingest_service.py`
  - `backend/src/autopulse_backend/services/ingest_aggregate_worker.py`
  - `docs/ops/PRODUCTION_DEPLOYMENT.md`

### TSK-P1-03 — Guided troubleshooting panel parity check

- **Priority:** P1
- **Status:** Todo
- **Owner:** Product + Frontend
- **Source findings:** F2
- **Description:** Verify and align dashboard troubleshooting UX with documented runbook expectations to preserve fast diagnosis flow.
- **Acceptance criteria:**
  - UI panel behavior matches release checklist expectations.
  - Any mismatch is resolved in either code or runbook.
  - QA notes include before/after diagnosis flow screenshots.
- **Related data/signals:**
  - User test pass rate on guided diagnosis steps.
  - Support/debug friction signals for first-run confusion.
- **Related files/docs:**
  - `frontend/components/dashboard/`
  - `docs/runbooks/PHASE5_RELEASE_CHECKLIST.md`
  - `docs/AUTOPULSE_FULL_AUDIT_ROADMAP.md`

### TSK-P1-04 — Forwarded header and HTTPS trust checklist

- **Priority:** P1
- **Status:** Todo
- **Owner:** SRE
- **Source findings:** B8
- **Description:** Document and validate reverse-proxy requirements for `X-Forwarded-Proto`, secure cookies, and ingest HTTPS enforcement.
- **Acceptance criteria:**
  - Runbook includes explicit proxy config checks.
  - Staging confirms secure behavior behind target LB/proxy.
  - Misconfiguration symptom matrix is documented.
- **Related data/signals:**
  - Request scheme/header diagnostics in logs.
  - Cookie secure-flag behavior in browser sessions.
- **Related files/docs:**
  - `docs/ops/PRODUCTION_DEPLOYMENT.md`
  - `backend/src/autopulse_backend/middleware/`
  - `backend/src/autopulse_backend/core/config.py`

### TSK-P1-05 — MVP scope narrative alignment

- **Priority:** P1
- **Status:** Todo
- **Owner:** Product + Docs
- **Source findings:** #12 (Top 15), §3.1, §11
- **Description:** Align documentation and UI copy with current shipped capabilities without re-opening billing scope, reducing confusion between MVP promise and advanced surfaces.
- **Acceptance criteria:**
  - Scope language is consistent across key docs and onboarding copy.
  - Advanced capabilities are framed with progressive disclosure.
  - No billing/plan assumptions added to readiness gates.
- **Related data/signals:**
  - Documentation consistency review checklist.
  - Reduced support confusion around feature scope positioning.
- **Related files/docs:**
  - `DEVELOPMENT.md`
  - `docs/AUTOPULSE_FULL_AUDIT_ROADMAP.md`
  - `frontend/components/dashboard/dashboardPages/SettingsContent.tsx`

---

## P2 — Strategic hardening (60-90 days)

### TSK-P2-01 — Shared realtime bus for multi-replica correctness

- **Priority:** P2
- **Status:** Todo
- **Owner:** Backend
- **Source findings:** §10 P2 roadmap
- **Description:** Introduce a cross-replica realtime propagation path (for example Redis/NATS) to remove sticky-session dependence for live dashboard updates.
- **Acceptance criteria:**
  - Realtime updates are consistent across replicas without LB stickiness.
  - Failure modes and fallback behavior are documented.
  - Load test verifies update latency within target SLO.
- **Related data/signals:**
  - End-to-end event-to-UI latency under scale.
  - Message bus health/error metrics.
- **Related files/docs:**
  - `backend/src/autopulse_backend/realtime/`
  - `docs/ops/DEPLOYMENT_MULTI_INSTANCE.md`

### TSK-P2-02 — Scaled event-store strategy beyond single DuckDB writer

- **Priority:** P2
- **Status:** Todo
- **Owner:** Platform
- **Source findings:** §10 P2 roadmap
- **Description:** Define long-term architecture for higher-volume/high-availability event storage when single-writer DuckDB is insufficient.
- **Acceptance criteria:**
  - Architecture decision record published with migration strategy.
  - Compatibility and operational costs evaluated against MVP goals.
  - Trigger thresholds documented for when to adopt new path.
- **Related data/signals:**
  - Throughput and storage growth benchmarks.
  - Operational incident trends linked to current event plane limits.
- **Related files/docs:**
  - `docs/ops/PRODUCTION_DEPLOYMENT.md`
  - `docs/AUTOPULSE_PRODUCTION_READINESS_MASTER_AUDIT.md`

### TSK-P2-03 — Frontend bundle budget and chart loading optimization

- **Priority:** P2
- **Status:** Todo
- **Owner:** Frontend
- **Source findings:** F5
- **Description:** Add explicit performance budget and lazy-load strategy for heavy dashboard visualizations to preserve fast diagnosis on constrained environments.
- **Acceptance criteria:**
  - Budget thresholds are defined and checked in CI/local tooling.
  - Critical diagnosis path meets p95 JS load target.
  - Chart-heavy routes use deferred/lazy loading where practical.
- **Related data/signals:**
  - Bundle analysis reports.
  - Web vitals/diagnosis path load timings.
- **Related files/docs:**
  - `frontend/next.config.js`
  - `frontend/components/dashboard/`
  - `.github/workflows/ci.yml`

### TSK-P2-04 — Optional frontend RUM with privacy guardrails

- **Priority:** P2
- **Status:** Todo
- **Owner:** Frontend + Ops
- **Source findings:** F4
- **Description:** Add opt-in client-side telemetry for dashboard runtime errors/perf, gated by environment and aligned with privacy defaults.
- **Acceptance criteria:**
  - RUM is disabled by default and env-gated when enabled.
  - Data captured is documented and scrubbed per privacy policy.
  - Operational runbook includes enable/disable and validation steps.
- **Related data/signals:**
  - Client error rate and session-level performance signals.
  - Privacy review checklist sign-off.
- **Related files/docs:**
  - `frontend/`
  - `docs/ops/PRODUCTION_DEPLOYMENT.md`
  - `DEVELOPMENT.md`

---

## Cross-cutting execution metadata

### Dependency map (high-level)

- `TSK-P0-01` is prerequisite context for `TSK-P0-02`, `TSK-P0-03`, `TSK-P0-04`, and `TSK-P0-11`.
- `TSK-P0-08` should complete before broad replica scaling.
- `TSK-P0-05` and `TSK-P0-07` should land before ingest stress/load sign-off.
- `TSK-P0-10` should block release candidate promotion once stable.

### Suggested tracking fields for project board

- Task ID
- Priority
- Status
- Owner
- Target milestone date
- Risk if delayed
- Links to PR(s)
- Verification evidence link

---

## Ready-to-run release gate checklist (task-based)

Before go-live, confirm all of the following are `Done`:

- `TSK-P0-01` through `TSK-P0-13`
- Any P1 task explicitly marked mandatory by incident history in your environment

If any P0 task remains open, production launch is `No-Go`.
