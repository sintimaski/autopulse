# Phase 5 Release Checklist

Use this checklist before promoting any Phase 5 changes.
Note: this runbook "Phase 5" label maps to the post-MVP roadmap release-hardening stage in `docs/POST_MVP_REAL_APP_ROADMAP.md`.

## Auth and Governance

- [ ] Dashboard session endpoint returns `project_id`, `organization_id`, and `membership_role`.
- [ ] Owner/member authorization is enforced for organization governance endpoints.
- [ ] Governance actions create audit events.
- [ ] Production auth mode validation evidence captured for at least one path: first-party magic-link mode or host/OIDC-integrated mode.
- [ ] Externally reachable dashboard is never deployed with `DASHBOARD_AUTH_ENABLED=false` unless upstream auth controls are documented and verified.

## Ingest and Data Lifecycle

- [ ] Ingest remains healthy (`/health` and `/ready`) under retention/archive load.
- [ ] Retention settings updates validate plan and archival options.
- [ ] Archival-before-delete behavior is verified with replay-safe retries.
- [ ] DuckDB topology validation passed: no deployment plans with multi-replica writers targeting the same DuckDB file.
- [ ] Staging load run for intended topology shows no DuckDB lock/corruption-class errors.

## Alerts and Jobs

- [ ] Alert delivery status remains visible with reason codes.
- [ ] `/internal/metrics` contains job start/success/failure counters.
- [ ] `/metrics` exposes ingest and job counters in Prometheus text format.
- [ ] Latest job execution telemetry appears for alerts and retention.
- [ ] Scheduler lease mode (`JOBS_SCHEDULER_LEASE_ENABLED=1`) is validated in multi-instance staging.
- [ ] For non-default SQLite or Postgres metadata DBs, deployment sets `JOBS_ENABLE_SCHEDULER=true` (or equivalent external cron); scheduler mode is visible in `/ready`.

## SLO Gate

- [ ] Ingest request path SLOs meet target (p95 under agreed threshold, 5xx rate within budget).
- [ ] Aggregate freshness SLO is within target window after ingest bursts.
- [ ] Alert job success ratio stays within target during drill runs.

## UI and Guided Troubleshooting

- [ ] Guided troubleshooting panel renders on Dashboard and Diagnosis.
- [ ] Settings page shows retention tiering/archival state and org governance tools.
- [ ] Role-aware UI behavior is validated with owner and member accounts.
- [ ] Multi-replica WS deployment validates sticky sessions (or single WS replica) with fresh live updates in staging.
- [ ] Stale-live symptom remediation (stickiness/single WS replica) is documented in release evidence.

## Final Gate

- [ ] Run `./scripts/release_gates.sh` from repository root.
- [ ] Run incident drills from `docs/runbooks/PHASE5_INCIDENT_DRILLS.md`.
- [ ] Capture rollback command sequence and escalation owner in release notes.
- [ ] Attach evidence links to PR before merge.
- [ ] Multi-replica rollout uses one-shot migration (`alembic upgrade head`) and API replicas run with `DATABASE_RUN_MIGRATIONS_ON_STARTUP=false`.
