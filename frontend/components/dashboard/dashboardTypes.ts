export type OverviewBucket = {
  minute: string;
  request_count: number;
  error_count: number;
  avg_latency_ms: number;
  count_2xx?: number;
  count_3xx?: number;
  count_4xx?: number;
  count_5xx?: number;
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
  apdex_score: number;
  active_sessions_estimate: number;
  error_burst_count: number;
  active_incident_count: number;
  error_type_breakdown: Array<{
    error_type: string;
    count: number;
  }>;
  alerts_timeline: Array<{
    triggered_at: string;
    alert_type: string;
    status: string;
  }>;
  service_breakdown: BreakdownItem[];
  route_breakdown: BreakdownItem[];
};

export type DashboardWidgetType =
  | "card"
  | "line"
  | "bar"
  | "donut"
  | "histogram"
  | "scatter"
  | "stacked_area";

export type DashboardWidgetDefinition = {
  widget_id: string;
  type: DashboardWidgetType;
  title: string;
  description: string | null;
  order: number;
  config: Record<string, string | number | boolean | null>;
};

export type DashboardWidgetPoint = {
  widget_id: string;
  timestamp: string;
  label: string | null;
  value: number;
};

export type DashboardWidgetsResponse = {
  server_now: string;
  from_timestamp: string;
  to_timestamp: string;
  definitions: DashboardWidgetDefinition[];
  points: DashboardWidgetPoint[];
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
  /** Error / diagnostic text from the stored event payload (e.g. `exception_message`). */
  log_message: string | null;
  /** Storage row id (DuckDB / Postgres); stable for deep links when present. */
  event_id?: number | null;
  received_at?: string | null;
  sdk_version?: string | null;
  /** Ingest event type, e.g. `request` or `error`. */
  event_kind?: string | null;
  trace_id?: string | null;
  span_id?: string | null;
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
  email_enabled: boolean;
  slack_enabled: boolean;
  slack_webhook_url: string | null;
  discord_enabled: boolean;
  discord_webhook_url: string | null;
  webhook_enabled: boolean;
  webhook_url: string | null;
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
  status: string;
  reason_code: string | null;
  reason_message: string | null;
  attempt_count: number;
  triggered_at: string;
  window_start: string;
  window_end: string;
  delivered_at: string | null;
  provider_message_id: string | null;
  detail: Record<string, number | string>;
};

export type AlertChannelCapability = {
  channel: "email" | "slack" | "discord" | "webhook";
  status: "active" | "configured" | "planned" | "unavailable";
  enabled: boolean;
  reason: string;
};

export type AlertCapabilitiesResponse = {
  channels: AlertChannelCapability[];
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
  retention_max_db_size_mb: number | null;
  retention_max_log_rows: number | null;
  retention_plan: "starter" | "standard" | "extended";
  archival_enabled: boolean;
  archival_mode: "db_archive";
  archival_status: "idle" | "running" | "failed";
  archival_last_success_at: string | null;
  archival_last_error: string | null;
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

export type QueryExplorerRequest = {
  query: string;
  from_timestamp?: string;
  to_timestamp?: string;
  window_minutes?: number;
  row_limit?: number;
};

export type QueryExplorerResponse = {
  server_now: string;
  from_timestamp: string;
  to_timestamp: string;
  query: string;
  columns: string[];
  rows: Array<Array<string | number | boolean | null>>;
  truncated: boolean;
};

export type TraceSummaryItem = {
  trace_id: string;
  first_seen: string;
  last_seen: string;
  span_count: number;
  error_count: number;
  services: string[];
  root_span_name: string | null;
};

export type TraceSearchResponse = {
  server_now: string;
  from_timestamp: string;
  to_timestamp: string;
  project_id: string;
  total: number;
  items: TraceSummaryItem[];
};

export type TraceSpanItem = {
  timestamp: string;
  service_name: string;
  environment: string;
  span_name: string;
  path: string;
  method: string;
  status_code: number;
  latency_ms: number;
  trace_id: string;
  span_id: string | null;
  parent_span_id: string | null;
  request_id: string | null;
  otlp_status_code: number | null;
};

export type TraceDetailResponse = {
  trace_id: string;
  first_seen: string | null;
  last_seen: string | null;
  error_count: number;
  items: TraceSpanItem[];
};

export type DashboardSessionResponse = {
  authenticated: boolean;
  email: string | null;
  expires_at: string | null;
  project_id: string | null;
  organization_id: string | null;
  membership_role: "owner" | "admin" | "member" | "viewer" | null;
};

export type DashboardOnboardingStatusResponse = {
  session_authenticated: boolean;
  project_ready: boolean;
  ingest_key_ready: boolean;
  first_event_received: boolean;
  first_diagnostic_signal_ready: boolean;
  /** Persisted on project when user completes onboarding (dashboard gate). */
  onboarding_completed: boolean;
  /** Short hint for the dashboard onboarding checklist. */
  next_recommended_action: string;
  current_step:
    | "authenticate_session"
    | "confirm_project"
    | "provision_ingest_key"
    | "send_first_event"
    | "open_diagnosis"
    | "completed";
};

export type DashboardProjectSummary = {
  project_id: string;
  project_name: string;
  organization_id: string | null;
};

export type DashboardOrganizationSummary = {
  organization_id: string;
  organization_name: string;
  projects: DashboardProjectSummary[];
  role: "owner" | "admin" | "member" | "viewer";
};

export type DashboardOrganizationListResponse = {
  organizations: DashboardOrganizationSummary[];
};

export type DashboardMembershipItem = {
  user_id: string;
  email: string;
  role: "owner" | "admin" | "member" | "viewer";
  invited_email: string | null;
  created_at: string;
};

export type DashboardMembershipListResponse = {
  organization_id: string;
  members: DashboardMembershipItem[];
};

export type DashboardMagicLinkRequestResponse = {
  accepted: boolean;
  expires_in_seconds: number;
  dev_token?: string | null;
  dev_magic_link_url?: string | null;
};

export type DashboardApiKeyItem = {
  key_id: string;
  created_at: string;
  revoked_at: string | null;
};

export type DashboardApiKeyListResponse = {
  items: DashboardApiKeyItem[];
};

export type DashboardApiKeyIssueResponse = {
  key_id: string;
  api_key: string;
  created_at: string;
};

export type DashboardApiKeyRotateResponse = {
  revoked_key_id: string;
  replacement_key_id: string;
  replacement_api_key: string;
  rotated_at: string;
};

export type DashboardBootstrapResponse = {
  retention_settings: RetentionSettings;
  alert_settings: AlertSettings;
  theme_settings: ThemeSettings;
  api_keys: DashboardApiKeyListResponse;
  alert_capabilities: AlertCapabilitiesResponse;
  onboarding_status: DashboardOnboardingStatusResponse | null;
};

export type DashboardInternalMetricsResponse = {
  enabled: boolean;
  reason: string | null;
  metrics: Record<string, unknown> | null;
};

export type DashboardSystemDiagnosticsResponse = {
  generated_at: string;
  topology: Record<string, unknown>;
  scheduler: Record<string, unknown>;
  replay_queue: Record<string, unknown>;
  ingestion_freshness: Record<string, unknown>;
  config_diagnostics: Record<string, unknown>;
};

export type DashboardDataQueryScope = {
  from_timestamp?: string;
  to_timestamp?: string;
  window_minutes: number;
  method?: string;
  status_class?: number;
  path_contains?: string;
  environments?: string;
  services?: string;
  min_latency_ms?: number;
  max_latency_ms?: number;
  event_sql_filter?: string;
};

export type DashboardDataQueryRequest = {
  scope: DashboardDataQueryScope;
  include_extended?: boolean;
  include_widgets?: boolean;
  include_error_groups?: boolean;
  include_diagnosis?: boolean;
  include_alert_dispatches?: boolean;
  include_recent_job_failures?: boolean;
  requests: { limit: number; offset: number };
  error_groups: { limit: number; offset: number };
  alert_dispatches?: { limit: number; offset: number };
  diagnosis_error_group_key?: string;
  diagnosis_error_group_events?: { limit: number; offset: number };
};

export type RecentJobFailureItem = {
  timestamp: string;
  job_name: string;
  trigger: string;
  status_code: number;
  latency_ms: number;
  service_name: string;
  environment: string;
  message?: string | null;
  correlated_request_id?: string | null;
};

export type RecentJobFailuresResponse = {
  server_now: string;
  from_timestamp: string;
  to_timestamp: string;
  items: RecentJobFailureItem[];
};

export type DashboardDataQueryResponse = {
  overview: OverviewResponse;
  overview_extended: OverviewExtendedResponse | null;
  widgets: DashboardWidgetsResponse | null;
  requests: RequestsResponse;
  error_groups: ErrorGroupsResponse | null;
  diagnosis_timeline: DiagnosisTimelineResponse | null;
  diagnosis_failures: DiagnosisFailureRoutesResponse | null;
  diagnosis_error_group_events: DiagnosisErrorGroupEventsResponse | null;
  recent_job_failures?: RecentJobFailuresResponse | null;
  alert_dispatches: AlertDispatchesResponse | null;
};

/**
 * Default API base when unset: same-origin root (``/dashboard/...``, ``/ingest`` on the backend).
 * Static UI lives under ``/autopulse/ui`` only; the API is not prefixed with ``/autopulse`` for
 * standalone ``autopulse_backend`` (see ``app.include_router(api_router)`` with no mount prefix).
 */
export const DEFAULT_MOUNTED_API_BASE = "";

export const apiBaseUrl =
  process.env.NEXT_PUBLIC_AUTOPULSE_API_BASE_URL ?? DEFAULT_MOUNTED_API_BASE;

const _isNextSidecarDev: boolean =
  process.env.NEXT_PUBLIC_AUTOPULSE_FRONTEND_MODE === "sidecar";

/** True when the dashboard calls the API on the same origin via a path prefix (static UI on the API host). */
export function isApiSubpathDashboard(): boolean {
  if (_isNextSidecarDev) {
    return false;
  }
  const normalized = normalizeBasePath(apiBaseUrl);
  return !normalized.startsWith("http://") && !normalized.startsWith("https://");
}

function normalizeBasePath(baseUrl: string): string {
  const trimmed = baseUrl.trim();
  if (!trimmed) {
    return "";
  }
  return trimmed.endsWith("/") ? trimmed.slice(0, -1) : trimmed;
}

/** Sidecar: Next runs on :3000 while API is on another origin; relative paths must be resolved to that origin. */
function resolveApiBaseForRequests(): string {
  const base = normalizeBasePath(apiBaseUrl);
  const relative = !base.startsWith("http://") && !base.startsWith("https://");
  if (relative && _isNextSidecarDev) {
    const origin = (
      process.env.NEXT_PUBLIC_AUTOPULSE_DEV_API_ORIGIN ?? "http://127.0.0.1:8000"
    ).replace(/\/+$/, "");
    if (!base) {
      return origin;
    }
    return `${origin}${base.startsWith("/") ? base : `/${base}`}`;
  }
  // Static export is served under ``/autopulse/ui`` on the API host; API routes are on the same
  // origin at ``/dashboard/...`` (no ``/autopulse`` API prefix for standalone backend).
  if (typeof window !== "undefined") {
    const href = window.location.href || "";
    const locPath = window.location.pathname || "";
    let looksLikeMountedStaticUi =
      href.includes("/autopulse/ui") ||
      locPath === "/autopulse/ui" ||
      locPath.startsWith("/autopulse/ui/");
    if (!looksLikeMountedStaticUi && typeof document !== "undefined") {
      const scripts = document.getElementsByTagName("script");
      for (let i = 0; i < scripts.length; i++) {
        const src = scripts[i]?.getAttribute("src") ?? "";
        if (src.includes("/autopulse/ui/_next/")) {
          looksLikeMountedStaticUi = true;
          break;
        }
      }
    }
    if (looksLikeMountedStaticUi) {
      const abs = base.startsWith("http://") || base.startsWith("https://");
      if (abs && /^https?:\/\/[^/]+\/?$/i.test(base)) {
        try {
          const pageOrigin = window.location.origin;
          const baseParsed = new URL(base);
          const pageParsed = new URL(pageOrigin);
          if (baseParsed.host === pageParsed.host && baseParsed.protocol === pageParsed.protocol) {
            return pageParsed.origin;
          }
        } catch {
          /* ignore */
        }
      }
    }
  }
  return base;
}

/** True when API base is an absolute URL with no path (e.g. ``http://127.0.0.1:8000``) — usually correct for standalone backend + static UI. */
export function isAbsoluteOriginOnlyApiBase(): boolean {
  const normalized = resolveApiBaseForRequests();
  if (!normalized.startsWith("http://") && !normalized.startsWith("https://")) {
    return false;
  }
  return /^https?:\/\/[^/]+\/?$/i.test(normalized);
}

export function buildApiUrl(path: string): string {
  const normalizedBase = resolveApiBaseForRequests();
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

export const WINDOW_OPTIONS = [15, 60, 240, 1440, 2880, 10080];
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

export const LOGS_TABLE_SORT_KEYS = [
  "timestamp",
  "method",
  "path",
  "status_code",
  "latency_ms",
  "service_name",
  "environment",
  "log_message",
] as const satisfies readonly (keyof RequestItem)[];

export type SortKey = (typeof LOGS_TABLE_SORT_KEYS)[number];

export const LOGS_TABLE_SORT_KEY_SET = new Set<string>(LOGS_TABLE_SORT_KEYS);
export {
  compareValues,
  formatTimestamp,
  formatTimestampCompact,
  statusTone,
  type SortDir,
} from "./dashboardDisplayUtils";

export const RUNBOOK_ALERTS_CMD = [
  "# stdout: number of alert dispatches this run (0 if no rule matched, e.g. empty DB or traffic below thresholds).",
  "# Exit code from the CLI is always 0; read the printed integer for dispatch count.",
  "# Ensure ALERTS_ENABLED is true (default) and the DB has recent request events in the evaluation windows.",
  "uv run python -m autopulse_backend.jobs alerts-once",
].join("\n");
export const RUNBOOK_RETENTION_CMD = "uv run python -m autopulse_backend.jobs retention-once";
