# Phase 5 Release Checklist

Use this checklist before promoting any Phase 5 changes.

## Auth and Governance

- [ ] Dashboard session endpoint returns `project_id`, `organization_id`, and `membership_role`.
- [ ] Owner/member authorization is enforced for organization governance endpoints.
- [ ] Governance actions create audit events.

## Ingest and Data Lifecycle

- [ ] Ingest remains healthy (`/health` and `/ready`) under retention/archive load.
- [ ] Retention settings updates validate plan and archival options.
- [ ] Archival-before-delete behavior is verified with replay-safe retries.

## Alerts and Jobs

- [ ] Alert delivery status remains visible with reason codes.
- [ ] `/internal/metrics` contains job start/success/failure counters.
- [ ] Latest job execution telemetry appears for alerts and retention.

## UI and Guided Troubleshooting

- [ ] Guided troubleshooting panel renders on Dashboard and Diagnosis.
- [ ] Settings page shows retention tiering/archival state and org governance tools.
- [ ] Role-aware UI behavior is validated with owner and member accounts.

## Final Gate

- [ ] Run `./scripts/release_gates.sh` from repository root.
- [ ] Run incident drills from `docs/runbooks/PHASE5_INCIDENT_DRILLS.md`.
- [ ] Attach evidence links to PR before merge.
