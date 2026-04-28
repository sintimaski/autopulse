# Phase 5 Incident Drills

This document defines rehearsal drills required by Phase 5 readiness.
This runbook phase name maps to the post-MVP roadmap release-hardening stage in `docs/POST_MVP_REAL_APP_ROADMAP.md`.

## Drill 1: Ingest Overload

- Trigger: send sustained oversized or high-rate ingest requests.
- Expected signal: `POST /ingest` starts returning explicit overload responses.
- Evidence:
  - `/ready` remains healthy.
  - `/internal/metrics` counters increase for ingest rejections.
  - No scheduler crash.

## Drill 2: Alert Delivery Failure

- Trigger: set invalid alert provider credentials and run `alerts-once`.
- Expected signal:
  - Alert dispatch row includes `status=failed`.
  - Guided troubleshooting panel surfaces alert delivery failure.
- Evidence:
  - Failed dispatch reason code is visible in Alerts and stored.
  - Recovery after credentials fix is confirmed.

## Drill 3: Retention Backlog / Archive Failure

- Trigger: enable archival and induce archival write failure.
- Expected signal:
  - Retention status transitions to `failed`.
  - Last error is recorded in retention settings.
- Evidence:
  - Archived rows are not duplicated on retry.
  - Cleanup resumes after configuration fix.

## Drill 4: Auth and Session Scope

- Trigger: validate org/member access with both owner and member accounts.
- Expected signal:
  - Member cannot run owner-only governance actions.
  - Owner can invite and update roles.
- Evidence:
  - Audit events are written for invite/role changes.
  - Session payload includes organization and role context.
