# Runbook: Event-plane backpressure

This runbook covers Plan B shard append rejections caused by low disk headroom or shard backlog pressure.

## Signals to watch

- `/internal/metrics` `ingest_pressure.event_plane_append_rejected_total`
- `/internal/metrics` `ingest_pressure.event_plane_append_failed_total`
- Backend logs with `event=event_plane_shard_append_rejected`

## Common causes

- Disk free space dropped below:
  - `AUTOPULSE_EVENT_PLANE_BACKPRESSURE_MIN_FREE_BYTES`
  - `AUTOPULSE_EVENT_PLANE_BACKPRESSURE_MIN_FREE_PERCENT`
- Pending shard count exceeded:
  - `AUTOPULSE_EVENT_PLANE_BACKPRESSURE_MAX_PENDING_SHARDS`

## Remediation steps

1. **Confirm pressure type**
   - Inspect latest `event_plane_shard_append_rejected` log entries.
   - If `reason` contains `low disk headroom`, follow disk remediation.
   - If `reason` contains `backlog pressure`, follow compaction/backlog remediation.

2. **Disk remediation**
   - Free space on the shard volume (delete unrelated artifacts, rotate old logs, expand volume).
   - Verify free bytes/percent are now above configured thresholds.

3. **Backlog remediation**
   - Run compactor until backlog stabilizes and snapshot publication resumes.
   - If compactor is down, restore worker health before increasing thresholds.
   - Only as a temporary emergency measure, raise `AUTOPULSE_EVENT_PLANE_BACKPRESSURE_MAX_PENDING_SHARDS`.

4. **Validation**
   - Send a small ingest batch and verify no new `event_plane_shard_append_rejected` entries.
   - Confirm `event_plane_append_rejected_total` stops increasing.

## Rollback / temporary safety valve

- If sustained pressure continues during incident response, switch project read path back to legacy mode:
  - `PUT /dashboard/event-plane-cutover` with `{"use_snapshot_read": false}`
- Keep shadow writes enabled unless pressure is severe enough to threaten ingest latency SLO.
