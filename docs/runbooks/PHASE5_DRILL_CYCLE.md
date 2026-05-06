# Phase 5 drill cadence and evidence

This runbook turns [Phase 5 incident drills](./PHASE5_INCIDENT_DRILLS.md), [event-plane DR drills](../ops/EVENT_PLANE_DISASTER_RECOVERY_DRILLS.md), and backup/restore procedures into **recurring, evidence-backed** execution. It satisfies process AC for production readiness without running drills against live user traffic.

## Cadence and ownership

| Frequency | Scope | Default owner | Success signal |
|-----------|--------|---------------|----------------|
| Weekly | Spot-check: `/health`, `/ready`, `/internal/metrics` job telemetry, ingest pressure counters | Ops on-call | No unexplained job failures; counters move as expected in staging |
| Monthly | Run **at least one** scenario from [PHASE5_INCIDENT_DRILLS.md](./PHASE5_INCIDENT_DRILLS.md) in **staging** (or an isolated sandbox with the same topology profile) | Backend + Ops | Evidence row added to [PHASE5_DRILL_EVIDENCE_LOG.md](./PHASE5_DRILL_EVIDENCE_LOG.md); open actions triaged |
| Monthly | If Parquet object storage is enabled: `parquet-object-sync-once` then `parquet-object-restore-once` on a disposable restore root; verify checksums and row readability | Ops | Evidence row + restored file count; no checksum failures |
| Quarterly | Full pass: all drills in [PHASE5_INCIDENT_DRILLS.md](./PHASE5_INCIDENT_DRILLS.md) applicable to your deployment + event-plane drill (`scripts/event_plane_disaster_recovery_drill.sh`) | Ops lead + Backend | All applicable rows green; DR script meets declared RTO/RPO in doc |

Replace **default owner** with named people in your org; keep this table updated when rotations change.

## Evidence capture (required fields)

Each drill run should produce a short artifact (internal wiki, ticket, or PR comment) containing:

1. **When:** UTC timestamp and environment (e.g. staging cluster id).
2. **What:** Drill id (e.g. `ingest-overload`, `parquet-object-restore`) and scenario version (link to runbook commit or tag).
3. **Topology:** `event_store`, `event_plane_mode`, `jobs_enable_scheduler`, Parquet flags from `/internal/metrics` `topology_profile` / `parquet_export` (no secrets).
4. **Result:** pass / fail / blocked (with reason).
5. **Metrics:** Paste or link redacted snippets (status codes, job counters, relevant `parquet.*` counters).
6. **Actions:** Open remediation items with owner and due date, or explicit “none”.

Then append one row to [PHASE5_DRILL_EVIDENCE_LOG.md](./PHASE5_DRILL_EVIDENCE_LOG.md) with a pointer to the artifact (URL or ticket id). Do **not** paste API keys, magic-link tokens, or full request bodies.

## Related procedures

- [BACKUP_RESTORE.md](../ops/BACKUP_RESTORE.md)
- [EVENT_PLANE_DISASTER_RECOVERY_DRILLS.md](../ops/EVENT_PLANE_DISASTER_RECOVERY_DRILLS.md)
- [PRODUCTION_DEPLOYMENT.md](../ops/PRODUCTION_DEPLOYMENT.md) (Parquet export / lifecycle / object storage CLIs)
- [PHASE5_RELEASE_CHECKLIST.md](./PHASE5_RELEASE_CHECKLIST.md)

## Review cadence

At least monthly, the ops lead reviews the evidence log for unresolved failures and confirms follow-ups are closed or explicitly deferred with a reason.
