# Phase 5 Release Checklist

Use this checklist before promoting any release-hardening changes.

## Auth and Governance

- [ ] Pre-go-live config verification captured from staging startup logs and `/internal/metrics` `topology_profile` (`event_plane_mode`, `jobs_enable_scheduler`, `dashboard_auth_enabled`, `dashboard_realtime_bus_backend`).
- [ ] Dashboard session endpoint returns `project_id`, `organization_id`, and `membership_role`.
- [ ] Owner/member authorization is enforced for organization governance endpoints.
- [ ] Governance actions create audit events.
- [ ] Production auth mode validation evidence captured for at least one path: first-party magic-link mode or host/OIDC-integrated mode.
- [ ] Externally reachable dashboard is never deployed with `DASHBOARD_AUTH_ENABLED=false` unless upstream auth controls are documented and verified.

## Ingest and Data Lifecycle

- [ ] Ingest remains healthy (`/health` and `/ready`) under retention/archive load.
- [ ] Retention settings updates validate plan and archival options.
- [ ] Archival-before-delete behavior is verified with replay-safe retries.
- [ ] If Parquet hybrid reads are enabled, validate mixed-window dashboard queries (recent=DuckDB hot, historical=Parquet cold) with stable response schema.
- [ ] If Parquet lifecycle is enabled, validate one lifecycle run (compaction + retention dry-run/execute + readability verification) and attach lifecycle manifest evidence.
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

- [ ] Guided troubleshooting panel renders on the home Dashboard (Widgets) view and on Diagnosis.
- [ ] Release evidence includes before/after screenshots of guided troubleshooting on Diagnosis (signals → hints → linked drill-down) after any UX change to that panel.
- [ ] Settings page shows retention tiering/archival state and org governance tools.
- [ ] Role-aware UI behavior is validated with owner and member accounts.
- [ ] Multi-replica WS deployment validates sticky sessions (or single WS replica) with fresh live updates in staging.
- [ ] Stale-live symptom remediation (stickiness/single WS replica) is documented in release evidence.

## Final Gate

- [ ] Run `./scripts/release_gates.sh` from repository root.
- [ ] If release touches Postgres-specific backend behavior, run release gates with `AUTOPULSE_RELEASE_GATES_POSTGRES=1`.
- [ ] If release touches dashboard navigation/rendering/auth UX, run release gates with `AUTOPULSE_RELEASE_GATES_E2E=1`.
- [ ] Run incident drills from `docs/runbooks/PHASE5_INCIDENT_DRILLS.md`.
- [ ] Capture rollback command sequence and escalation owner in release notes.
- [ ] Attach evidence links to PR before merge.
- [ ] Multi-replica rollout uses one-shot migration (`alembic upgrade head`) and API replicas run with `DATABASE_RUN_MIGRATIONS_ON_STARTUP=false`.
