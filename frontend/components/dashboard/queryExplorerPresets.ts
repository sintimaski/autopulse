/** URL: `/query-explorer?preset=job_failures` — starter SQL for failed background job rows. */
export const QUERY_EXPLORER_JOB_FAILURES_PRESET = "job_failures";

export type QueryExplorerTemplate = {
  id: string;
  title: string;
  description: string;
  sql: string;
};

/**
 * `type='job'` rows only exist when an app uses background-job instrumentation,
 * which most real users have not wired up yet. A query that filters on job rows
 * legitimately returns zero rows on a request-only project, so the results panel
 * shows an explanatory hint rather than a bare empty state.
 */
export function isJobTypedQuery(sql: string): boolean {
  return /\btype\b\s*[)]*\s*(=|like|in)[^\n]*'job'/i.test(sql.toLowerCase());
}

/** Curated read-only templates (time scope still comes from the header panel). */
export const QUERY_EXPLORER_TEMPLATES: QueryExplorerTemplate[] = [
  {
    id: "requests_by_route",
    title: "Request volume by route",
    description: "Top paths by request count in the scoped window.",
    sql: [
      "SELECT",
      "  path,",
      "  COUNT(*) AS requests,",
      "  SUM(CASE WHEN status_code >= 500 THEN 1 ELSE 0 END) AS errors,",
      "  AVG(latency_ms) AS avg_latency_ms",
      "FROM scoped_events",
      "WHERE lower(trim(type)) = 'request'",
      "GROUP BY path",
      "ORDER BY requests DESC",
      "LIMIT 50",
    ].join("\n"),
  },
  {
    id: "slow_requests",
    title: "Slowest requests (p95 hint)",
    description: "High-latency GET/POST rows for quick triage.",
    sql: [
      "SELECT timestamp, path, method, status_code, latency_ms, service_name, environment",
      "FROM scoped_events",
      "WHERE lower(trim(type)) = 'request'",
      "  AND latency_ms IS NOT NULL",
      "ORDER BY latency_ms DESC",
      "LIMIT 50",
    ].join("\n"),
  },
  {
    id: "errors_by_service",
    title: "5xx counts by service",
    description: "Which instrumented service is throwing server errors.",
    sql: [
      "SELECT",
      "  service_name,",
      "  environment,",
      "  COUNT(*) AS errors",
      "FROM scoped_events",
      "WHERE lower(trim(type)) = 'request'",
      "  AND status_code >= 500",
      "GROUP BY service_name, environment",
      "ORDER BY errors DESC",
      "LIMIT 50",
    ].join("\n"),
  },
  {
    id: "error_events",
    title: "Captured error events",
    description: "Rows emitted as type `error` (stack captured server-side).",
    sql: [
      "SELECT timestamp, path, exception_type, exception_message, service_name",
      "FROM scoped_events",
      "WHERE lower(trim(type)) = 'error'",
      "ORDER BY timestamp DESC",
      "LIMIT 50",
    ].join("\n"),
  },
  {
    id: "status_distribution",
    title: "HTTP status distribution",
    description: "Bucket counts for the scoped request rows.",
    sql: [
      "SELECT status_code, COUNT(*) AS requests",
      "FROM scoped_events",
      "WHERE lower(trim(type)) = 'request'",
      "GROUP BY status_code",
      "ORDER BY requests DESC",
    ].join("\n"),
  },
  {
    id: "environment_mix",
    title: "Traffic by environment label",
    description: "Compare staging vs production traffic volume in-window.",
    sql: [
      "SELECT environment, COUNT(*) AS requests",
      "FROM scoped_events",
      "WHERE lower(trim(type)) = 'request'",
      "GROUP BY environment",
      "ORDER BY requests DESC",
    ].join("\n"),
  },
  {
    id: "recent_correlation",
    title: "Recent rows with request_id",
    description: "Useful when chasing a single correlation / request id.",
    sql: [
      "SELECT timestamp, type, path, status_code, request_id, latency_ms",
      "FROM scoped_events",
      "WHERE request_id IS NOT NULL",
      "  AND trim(CAST(request_id AS VARCHAR)) <> ''",
      "ORDER BY timestamp DESC",
      "LIMIT 100",
    ].join("\n"),
  },
];

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
