export type OverviewBucket = {
  minute: string;
  request_count: number;
  error_count: number;
  avg_latency_ms: number;
};

export type OverviewResponse = {
  from_timestamp: string;
  to_timestamp: string;
  request_count: number;
  error_count: number;
  error_rate: number;
  avg_latency_ms: number;
  requests_per_minute: number;
  series: OverviewBucket[];
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
  from_timestamp: string;
  to_timestamp: string;
  total: number;
  limit: number;
  offset: number;
  items: ErrorGroupItem[];
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

export const apiBaseUrl =
  process.env.NEXT_PUBLIC_AUTOPULSE_API_BASE_URL ?? "http://localhost:8000";
export const apiKey = process.env.NEXT_PUBLIC_AUTOPULSE_API_KEY;

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
