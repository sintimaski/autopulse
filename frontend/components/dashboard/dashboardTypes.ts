export type OverviewBucket = {
  minute: string;
  request_count: number;
  error_count: number;
  avg_latency_ms: number;
};

export type OverviewResponse = {
  server_now: string;
  from_timestamp: string;
  to_timestamp: string;
  request_count: number;
  error_count: number;
  error_rate: number;
  avg_latency_ms: number;
  requests_per_minute: number;
  series: OverviewBucket[];
};

export type BreakdownItem = {
  key: string;
  request_count: number;
  error_count: number;
  error_rate: number;
  avg_latency_ms: number;
};

export type OverviewExtendedResponse = {
  server_now: string;
  from_timestamp: string;
  to_timestamp: string;
  p50_latency_ms: number;
  p95_latency_ms: number;
  p99_latency_ms: number;
  error_burst_count: number;
  active_incident_count: number;
  service_breakdown: BreakdownItem[];
  route_breakdown: BreakdownItem[];
};

export type RequestItem = {
  timestamp: string;
  method: string;
  path: string;
  status_code: number;
  latency_ms: number;
  service_name: string;
  environment: string;
  request_id: string | null;
};

export type RequestsResponse = {
  server_now: string;
  from_timestamp: string;
  to_timestamp: string;
  total: number;
  limit: number;
  offset: number;
  items: RequestItem[];
};

export type ErrorGroupItem = {
  group_key: string;
  exception_type: string | null;
  message: string | null;
  path: string;
  count: number;
  first_seen: string;
  last_seen: string;
  sample_stack_trace: string | null;
};

export type ErrorGroupsResponse = {
  server_now: string;
  from_timestamp: string;
  to_timestamp: string;
  total: number;
  limit: number;
  offset: number;
  items: ErrorGroupItem[];
};

export type DiagnosisTimelineBucket = {
  minute: string;
  request_count: number;
  error_count: number;
};

export type DiagnosisTimelineResponse = {
  server_now: string;
  from_timestamp: string;
  to_timestamp: string;
  buckets: DiagnosisTimelineBucket[];
};

export type DiagnosisFailureRouteItem = {
  path: string;
  failure_count: number;
  error_rate: number;
  avg_latency_ms: number;
};

export type DiagnosisFailureRoutesResponse = {
  server_now: string;
  from_timestamp: string;
  to_timestamp: string;
  items: DiagnosisFailureRouteItem[];
};

export type DiagnosisErrorGroupEventItem = {
  id: number;
  timestamp: string;
  method: string;
  path: string;
  status_code: number;
  latency_ms: number;
  service_name: string;
  environment: string;
  request_id: string | null;
  stack_trace: string | null;
  message: string | null;
  exception_type: string | null;
};

export type DiagnosisErrorGroupEventsResponse = {
  total: number;
  items: DiagnosisErrorGroupEventItem[];
};

export type AlertSettings = {
  enabled: boolean;
  destination_email: string | null;
  error_spike_ratio_threshold: number;
  error_spike_min_requests: number;
  error_spike_window_minutes: number;
  outage_min_requests: number;
  outage_window_minutes: number;
  cooldown_minutes: number;
};

export type AlertDispatchItem = {
  id: number;
  alert_type: string;
  destination_email: string | null;
  delivered_via: string;
  triggered_at: string;
  window_start: string;
  window_end: string;
  detail: Record<string, number | string>;
};

export type AlertDispatchesResponse = {
  total: number;
  limit: number;
  offset: number;
  items: AlertDispatchItem[];
};

export type ThemePreference = "system" | "light" | "dark";

export type ThemeSettings = {
  theme_preference: ThemePreference;
  exclude_autopulse_traffic: boolean;
};

export type RetentionSettings = {
  raw_events_days: number;
  logs_query_max_window_minutes: number;
};

export type LogQueryRequest = {
  query: string;
  cursor?: string | null;
  page_size?: number;
  from_timestamp?: string;
  to_timestamp?: string;
};

export type LogQueryValidationResponse = {
  valid: boolean;
  normalized_query: string;
  error: string | null;
};

export type LogQueryItem = {
  id: number;
  timestamp: string;
  method: string;
  path: string;
  status_code: number;
  latency_ms: number;
  service_name: string;
  environment: string;
  request_id: string | null;
};

export type LogQueryPageResponse = {
  server_now: string;
  query: string;
  next_cursor: string | null;
  items: LogQueryItem[];
};

export type DashboardSessionResponse = {
  authenticated: boolean;
  email: string | null;
  expires_at: string | null;
};

export type DashboardMagicLinkRequestResponse = {
  accepted: boolean;
  expires_in_seconds: number;
  dev_magic_link_token: string | null;
};

export const EMBEDDED_DEFAULT_API_BASE_URL = "/autopulse";

export const apiBaseUrl =
  process.env.NEXT_PUBLIC_AUTOPULSE_API_BASE_URL ?? EMBEDDED_DEFAULT_API_BASE_URL;

function normalizeBasePath(baseUrl: string): string {
  const trimmed = baseUrl.trim();
  if (!trimmed) {
    return EMBEDDED_DEFAULT_API_BASE_URL;
  }
  return trimmed.endsWith("/") ? trimmed.slice(0, -1) : trimmed;
}

export function buildApiUrl(path: string): string {
  const normalizedBase = normalizeBasePath(apiBaseUrl);
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  if (normalizedBase.startsWith("http://") || normalizedBase.startsWith("https://")) {
    return `${normalizedBase}${normalizedPath}`;
  }
  return `${normalizedBase}${normalizedPath}`;
}

/** Build WS URL from the same path rules as {@link buildApiUrl} so mounts like `/autopulse` stay in sync. */
function httpToWebsocketUrl(httpRef: string): string {
  const origin =
    typeof window !== "undefined" && window.location?.origin
      ? window.location.origin
      : "http://localhost";
  const base =
    httpRef.startsWith("http://") || httpRef.startsWith("https://")
      ? new URL(httpRef)
      : new URL(httpRef, origin);
  base.protocol = base.protocol === "https:" ? "wss:" : "ws:";
  return base.toString();
}

export function buildUpdatesWebsocketUrl(): string {
  return httpToWebsocketUrl(buildApiUrl("/dashboard/updates"));
}

export const WINDOW_OPTIONS = [15, 60, 240, 1440];
export const METHOD_OPTIONS = ["ALL", "GET", "POST", "PUT", "PATCH", "DELETE"];
export const STATUS_CLASS_OPTIONS = ["ALL", "2", "4", "5"];
export const REQUEST_LIMIT_OPTIONS = [50, 100, 200];
export const ERROR_GROUP_LIMIT_OPTIONS = [10, 25, 50];
export const GROUP_OPTIONS = [
  { value: "none", label: "No grouping" },
  { value: "path", label: "Path" },
  { value: "service_name", label: "Service" },
  { value: "environment", label: "Environment" },
] as const;

export type GroupBy = (typeof GROUP_OPTIONS)[number]["value"];
export type SortKey = keyof Pick<
  RequestItem,
  "timestamp" | "method" | "path" | "status_code" | "latency_ms" | "service_name" | "environment"
>;
export type SortDir = "asc" | "desc";

export const RUNBOOK_ALERTS_CMD = [
  "# stdout: number of alert dispatches this run (0 if no rule matched, e.g. empty DB or traffic below thresholds).",
  "# Exit code from the CLI is always 0; read the printed integer for dispatch count.",
  "# Ensure ALERTS_ENABLED is true (default) and the DB has recent request events in the evaluation windows.",
  "uv run python -m autopulse_backend.jobs alerts-once",
].join("\n");
export const RUNBOOK_RETENTION_CMD = "uv run python -m autopulse_backend.jobs retention-once";

export function formatTimestamp(value: string): string {
  return new Date(value).toLocaleString();
}

export function statusTone(code: number): string {
  if (code >= 500) {
    return "bg-rose-500/15 text-rose-800 ring-rose-500/25 dark:bg-rose-900/40 dark:text-rose-300 dark:ring-rose-700/50";
  }
  if (code >= 400) {
    return "bg-amber-500/15 text-amber-900 ring-amber-500/25 dark:bg-amber-900/40 dark:text-amber-300 dark:ring-amber-700/50";
  }
  return "bg-emerald-500/15 text-emerald-900 ring-emerald-500/25 dark:bg-emerald-900/40 dark:text-emerald-300 dark:ring-emerald-700/50";
}

export function compareValues(a: string | number, b: string | number, dir: SortDir): number {
  const mul = dir === "asc" ? 1 : -1;
  if (typeof a === "number" && typeof b === "number") {
    return (a - b) * mul;
  }
  return String(a).localeCompare(String(b), undefined, { sensitivity: "base" }) * mul;
}
