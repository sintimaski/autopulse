# Runbook: SQL-tail replay recovery

Use this runbook when DuckDB ingest succeeds but SQL aggregate/widget persistence lags or fails.

## Signals and thresholds

Watch these signals from `/internal/metrics` and `/dashboard/system-diagnostics`:

- `ingest_pressure.persist_sql_tail_failed_total`
- `ingest_pressure.sql_tail_repair_queued_total`
- `ingest_pressure.sql_tail_repair_failed_total`
- `ingest_pressure.sql_tail_repair_dead_lettered_total`
- `system_diagnostics.replay_queue.pending_sql_tail_repairs`
- `system_diagnostics.replay_queue.oldest_pending_age_seconds`

Initial alert target (tune per environment baseline):

- Treat replay backlog as incident when `oldest_pending_age_seconds > 600` for 15 minutes.

## Deterministic recovery flow

1. Confirm SQL-side dependency health (metadata DB reachable, migration state valid, no disk pressure).
2. Check backlog shape:
   - pending count rising -> worker cannot keep up
   - dead-letter count rising -> repeated hard failures
3. Run one manual replay pass:

```bash
uv run python -m lumonox_backend.jobs replay-sql-tail-repairs-once
```

4. Re-check diagnostics:
   - pending count should fall
   - oldest pending age should trend down
   - dead-letter growth should stop
5. If dead letters remain after fix, capture representative `last_error` samples and rerun replay.

## Drill procedure (staging)

Run this before production promotions that touch ingest/replay paths:

1. Inject a controlled SQL-tail failure (for example temporary DB auth deny or transaction failure).
2. Send a small ingest burst and verify queue growth (`pending_sql_tail_repairs` > 0).
3. Restore dependency health.
4. Run `replay-sql-tail-repairs-once` and verify queue drains.
5. Record elapsed recovery time; target <10 minutes end-to-end.

## Escalation

- If replay queue age breaches incident threshold and does not recover after one replay pass:
  - escalate to Backend on-call + Ops owner
  - hold production promotion for ingest-path changes
- If dead-letter backlog continues growing, open incident and attach:
  - diagnostics snapshot
  - replay command output
  - remediation hypothesis and owner
