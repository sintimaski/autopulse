/** URL: `/query-explorer?preset=job_failures` — starter SQL for failed background job rows. */
export const QUERY_EXPLORER_JOB_FAILURES_PRESET = "job_failures";

export const JOB_FAILURES_STARTER_SQL = [
  "SELECT",
  "  timestamp,",
  "  path AS job_name,",
  "  status_code,",
  "  latency_ms,",
  "  service_name,",
  "  environment,",
  "  request_id,",
  "  type",
  "FROM scoped_events",
  "WHERE lower(trim(type)) = 'job'",
  "  AND status_code >= 500",
  "ORDER BY timestamp DESC",
  "LIMIT 50",
].join("\n");
