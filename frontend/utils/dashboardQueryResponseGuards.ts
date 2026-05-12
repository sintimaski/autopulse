import type {
  AlertDispatchItem,
  AlertDispatchesResponse,
  DashboardDataQueryResponse,
  DashboardWidgetDefinition,
  DashboardWidgetPoint,
  DashboardWidgetsResponse,
  DiagnosisErrorGroupEventItem,
  DiagnosisErrorGroupEventsResponse,
  DiagnosisFailureRouteItem,
  DiagnosisFailureRoutesResponse,
  DiagnosisTimelineBucket,
  DiagnosisTimelineResponse,
  ErrorGroupItem,
  ErrorGroupsResponse,
  OverviewBucket,
  OverviewExtendedResponse,
  OverviewReleaseMarker,
  OverviewResponse,
  RecentJobFailureItem,
  RecentJobFailuresResponse,
  RequestItem,
  RequestsResponse,
} from "../components/dashboard/dashboardTypes";

function isRecord(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

function parseOptional<T>(value: unknown, parser: (v: unknown) => T | null): T | null {
  if (value === null || value === undefined) {
    return null;
  }
  return parser(value);
}

function isOverviewBucket(v: unknown): v is OverviewBucket {
  if (!isRecord(v)) {
    return false;
  }
  if (typeof v.minute !== "string") {
    return false;
  }
  if (typeof v.request_count !== "number" || typeof v.error_count !== "number" || typeof v.avg_latency_ms !== "number") {
    return false;
  }
  for (const k of ["count_2xx", "count_3xx", "count_4xx", "count_5xx"] as const) {
    const x = v[k];
    if (x !== undefined && typeof x !== "number") {
      return false;
    }
  }
  return true;
}

function isOverviewReleaseMarker(v: unknown): v is { at: string; release: string; git_sha?: string | null } {
  if (!isRecord(v)) {
    return false;
  }
  if (typeof v.at !== "string" || typeof v.release !== "string") {
    return false;
  }
  const gs = v.git_sha;
  if (gs !== null && gs !== undefined && typeof gs !== "string") {
    return false;
  }
  return true;
}

export function parseOverviewResponse(raw: unknown): OverviewResponse | null {
  if (!isRecord(raw)) {
    return null;
  }
  const sk = ["server_now", "from_timestamp", "to_timestamp"] as const;
  for (const k of sk) {
    if (typeof raw[k] !== "string") {
      return null;
    }
  }
  const nums = [
    "request_count",
    "error_count",
    "error_rate",
    "avg_latency_ms",
    "requests_per_minute",
  ] as const;
  for (const k of nums) {
    if (typeof raw[k] !== "number") {
      return null;
    }
  }
  if (!Array.isArray(raw.series) || !raw.series.every(isOverviewBucket)) {
    return null;
  }
  const markersRaw = raw.release_markers;
  let release_markers: OverviewReleaseMarker[];
  if (markersRaw === undefined) {
    release_markers = [];
  } else {
    if (!Array.isArray(markersRaw) || !markersRaw.every(isOverviewReleaseMarker)) {
      return null;
    }
    release_markers = markersRaw.map((m) => ({
      at: m.at,
      release: m.release,
      git_sha: m.git_sha ?? null,
    }));
  }
  return {
    server_now: raw.server_now as string,
    from_timestamp: raw.from_timestamp as string,
    to_timestamp: raw.to_timestamp as string,
    request_count: raw.request_count as number,
    error_count: raw.error_count as number,
    error_rate: raw.error_rate as number,
    avg_latency_ms: raw.avg_latency_ms as number,
    requests_per_minute: raw.requests_per_minute as number,
    series: raw.series as OverviewBucket[],
    release_markers,
  };
}

function isRequestItem(v: unknown): v is RequestItem {
  if (!isRecord(v)) {
    return false;
  }
  const stringKeys = ["timestamp", "method", "path", "service_name", "environment"] as const;
  for (const k of stringKeys) {
    if (typeof v[k] !== "string") {
      return false;
    }
  }
  if (typeof v.status_code !== "number" || typeof v.latency_ms !== "number") {
    return false;
  }
  if (v.request_id !== null && v.request_id !== undefined && typeof v.request_id !== "string") {
    return false;
  }
  if (v.log_message !== null && v.log_message !== undefined && typeof v.log_message !== "string") {
    return false;
  }
  if (v.event_id !== null && v.event_id !== undefined && typeof v.event_id !== "number") {
    return false;
  }
  if (v.received_at !== null && v.received_at !== undefined && typeof v.received_at !== "string") {
    return false;
  }
  if (v.sdk_version !== null && v.sdk_version !== undefined && typeof v.sdk_version !== "string") {
    return false;
  }
  if (v.event_kind !== null && v.event_kind !== undefined && typeof v.event_kind !== "string") {
    return false;
  }
  if (v.trace_id !== null && v.trace_id !== undefined && typeof v.trace_id !== "string") {
    return false;
  }
  if (v.span_id !== null && v.span_id !== undefined && typeof v.span_id !== "string") {
    return false;
  }
  return true;
}

export function parseRequestsResponse(raw: unknown): RequestsResponse | null {
  if (!isRecord(raw)) {
    return null;
  }
  const sk = ["server_now", "from_timestamp", "to_timestamp"] as const;
  for (const k of sk) {
    if (typeof raw[k] !== "string") {
      return null;
    }
  }
  for (const k of ["total", "limit", "offset"] as const) {
    if (typeof raw[k] !== "number") {
      return null;
    }
  }
  if (!Array.isArray(raw.items) || !raw.items.every(isRequestItem)) {
    return null;
  }
  return raw as RequestsResponse;
}

function isErrorTypeBreakdownItem(v: unknown): v is OverviewExtendedResponse["error_type_breakdown"][number] {
  if (!isRecord(v)) {
    return false;
  }
  return typeof v.error_type === "string" && typeof v.count === "number";
}

function isAlertTimelineItem(v: unknown): v is OverviewExtendedResponse["alerts_timeline"][number] {
  if (!isRecord(v)) {
    return false;
  }
  return typeof v.triggered_at === "string" && typeof v.alert_type === "string" && typeof v.status === "string";
}

function isBreakdownItem(v: unknown): v is OverviewExtendedResponse["service_breakdown"][number] {
  if (!isRecord(v)) {
    return false;
  }
  return (
    typeof v.key === "string" &&
    typeof v.request_count === "number" &&
    typeof v.error_count === "number" &&
    typeof v.error_rate === "number" &&
    typeof v.avg_latency_ms === "number"
  );
}

export function parseOverviewExtendedResponse(raw: unknown): OverviewExtendedResponse | null {
  if (!isRecord(raw)) {
    return null;
  }
  const sk = ["server_now", "from_timestamp", "to_timestamp"] as const;
  for (const k of sk) {
    if (typeof raw[k] !== "string") {
      return null;
    }
  }
  const latencyKeys = ["p50_latency_ms", "p95_latency_ms", "p99_latency_ms", "apdex_score"] as const;
  for (const k of latencyKeys) {
    if (typeof raw[k] !== "number") {
      return null;
    }
  }
  if (typeof raw.active_sessions_estimate !== "number" || typeof raw.error_burst_count !== "number") {
    return null;
  }
  if (typeof raw.active_incident_count !== "number") {
    return null;
  }
  if (!Array.isArray(raw.error_type_breakdown) || !raw.error_type_breakdown.every(isErrorTypeBreakdownItem)) {
    return null;
  }
  if (!Array.isArray(raw.alerts_timeline) || !raw.alerts_timeline.every(isAlertTimelineItem)) {
    return null;
  }
  if (!Array.isArray(raw.service_breakdown) || !raw.service_breakdown.every(isBreakdownItem)) {
    return null;
  }
  if (!Array.isArray(raw.route_breakdown) || !raw.route_breakdown.every(isBreakdownItem)) {
    return null;
  }
  return raw as OverviewExtendedResponse;
}

const WIDGET_TYPES = ["card", "line", "bar", "donut", "histogram", "scatter", "stacked_area"] as const;

function isWidgetType(v: unknown): v is DashboardWidgetDefinition["type"] {
  return typeof v === "string" && (WIDGET_TYPES as readonly string[]).includes(v);
}

function isWidgetConfigValue(v: unknown): boolean {
  return v === null || typeof v === "string" || typeof v === "number" || typeof v === "boolean";
}

function isDashboardWidgetConfig(v: unknown): v is DashboardWidgetDefinition["config"] {
  if (!isRecord(v)) {
    return false;
  }
  return Object.values(v).every(isWidgetConfigValue);
}

function isDashboardWidgetDefinition(v: unknown): v is DashboardWidgetDefinition {
  if (!isRecord(v)) {
    return false;
  }
  if (typeof v.widget_id !== "string" || !isWidgetType(v.type) || typeof v.title !== "string") {
    return false;
  }
  if (v.description !== null && typeof v.description !== "string") {
    return false;
  }
  if (typeof v.order !== "number" || !isDashboardWidgetConfig(v.config)) {
    return false;
  }
  return true;
}

function isDashboardWidgetPoint(v: unknown): v is DashboardWidgetPoint {
  if (!isRecord(v)) {
    return false;
  }
  if (typeof v.widget_id !== "string" || typeof v.timestamp !== "string" || typeof v.value !== "number") {
    return false;
  }
  if (v.label !== null && typeof v.label !== "string") {
    return false;
  }
  return true;
}

function isDashboardWidgetPlacement(v: unknown): boolean {
  if (!isRecord(v)) {
    return false;
  }
  return (
    typeof v.widget_id === "string" &&
    typeof v.order === "number" &&
    typeof v.section === "string" &&
    typeof v.column_span === "number" &&
    typeof v.row_span === "number"
  );
}

function isDashboardWidgetPageLayout(v: unknown): boolean {
  if (!isRecord(v)) {
    return false;
  }
  if (
    typeof v.page_id !== "string" ||
    typeof v.title !== "string" ||
    (v.description !== null && v.description !== undefined && typeof v.description !== "string") ||
    typeof v.order !== "number"
  ) {
    return false;
  }
  return Array.isArray(v.widgets) && v.widgets.every(isDashboardWidgetPlacement);
}

function isDashboardWidgetLayout(v: unknown): boolean {
  if (!isRecord(v)) {
    return false;
  }
  if (typeof v.default_page_id !== "string") {
    return false;
  }
  if (!Array.isArray(v.pages) || !v.pages.every(isDashboardWidgetPageLayout)) {
    return false;
  }
  if (!Array.isArray(v.unplaced_widget_ids) || !v.unplaced_widget_ids.every((id) => typeof id === "string")) {
    return false;
  }
  return true;
}

export function parseDashboardWidgetsResponse(raw: unknown): DashboardWidgetsResponse | null {
  if (!isRecord(raw)) {
    return null;
  }
  const sk = ["server_now", "from_timestamp", "to_timestamp"] as const;
  for (const k of sk) {
    if (typeof raw[k] !== "string") {
      return null;
    }
  }
  if (!Array.isArray(raw.definitions) || !raw.definitions.every(isDashboardWidgetDefinition)) {
    return null;
  }
  if (!Array.isArray(raw.points) || !raw.points.every(isDashboardWidgetPoint)) {
    return null;
  }
  if (
    raw.layout !== undefined &&
    raw.layout !== null &&
    !isDashboardWidgetLayout(raw.layout)
  ) {
    return null;
  }
  return raw as DashboardWidgetsResponse;
}

function isErrorGroupItem(v: unknown): v is ErrorGroupItem {
  if (!isRecord(v)) {
    return false;
  }
  if (typeof v.group_key !== "string" || typeof v.path !== "string" || typeof v.count !== "number") {
    return false;
  }
  if (v.exception_type !== null && typeof v.exception_type !== "string") {
    return false;
  }
  if (v.message !== null && typeof v.message !== "string") {
    return false;
  }
  if (typeof v.first_seen !== "string" || typeof v.last_seen !== "string") {
    return false;
  }
  if (v.sample_stack_trace !== null && typeof v.sample_stack_trace !== "string") {
    return false;
  }
  return true;
}

export function parseErrorGroupsResponse(raw: unknown): ErrorGroupsResponse | null {
  if (!isRecord(raw)) {
    return null;
  }
  const sk = ["server_now", "from_timestamp", "to_timestamp"] as const;
  for (const k of sk) {
    if (typeof raw[k] !== "string") {
      return null;
    }
  }
  for (const k of ["total", "limit", "offset"] as const) {
    if (typeof raw[k] !== "number") {
      return null;
    }
  }
  if (!Array.isArray(raw.items) || !raw.items.every(isErrorGroupItem)) {
    return null;
  }
  return raw as ErrorGroupsResponse;
}

function isDiagnosisTimelineBucket(v: unknown): v is DiagnosisTimelineBucket {
  if (!isRecord(v)) {
    return false;
  }
  return (
    typeof v.minute === "string" &&
    typeof v.request_count === "number" &&
    typeof v.error_count === "number"
  );
}

export function parseDiagnosisTimelineResponse(raw: unknown): DiagnosisTimelineResponse | null {
  if (!isRecord(raw)) {
    return null;
  }
  const sk = ["server_now", "from_timestamp", "to_timestamp"] as const;
  for (const k of sk) {
    if (typeof raw[k] !== "string") {
      return null;
    }
  }
  if (!Array.isArray(raw.buckets) || !raw.buckets.every(isDiagnosisTimelineBucket)) {
    return null;
  }
  return raw as DiagnosisTimelineResponse;
}

function isDiagnosisFailureRouteItem(v: unknown): v is DiagnosisFailureRouteItem {
  if (!isRecord(v)) {
    return false;
  }
  return (
    typeof v.path === "string" &&
    typeof v.failure_count === "number" &&
    typeof v.error_rate === "number" &&
    typeof v.avg_latency_ms === "number"
  );
}

export function parseDiagnosisFailureRoutesResponse(raw: unknown): DiagnosisFailureRoutesResponse | null {
  if (!isRecord(raw)) {
    return null;
  }
  const sk = ["server_now", "from_timestamp", "to_timestamp"] as const;
  for (const k of sk) {
    if (typeof raw[k] !== "string") {
      return null;
    }
  }
  if (!Array.isArray(raw.items) || !raw.items.every(isDiagnosisFailureRouteItem)) {
    return null;
  }
  return raw as DiagnosisFailureRoutesResponse;
}

function isDiagnosisErrorGroupEventItem(v: unknown): v is DiagnosisErrorGroupEventItem {
  if (!isRecord(v)) {
    return false;
  }
  if (typeof v.id !== "number" || typeof v.timestamp !== "string") {
    return false;
  }
  const sk = ["method", "path", "service_name", "environment"] as const;
  for (const k of sk) {
    if (typeof v[k] !== "string") {
      return false;
    }
  }
  if (typeof v.status_code !== "number" || typeof v.latency_ms !== "number") {
    return false;
  }
  if (v.request_id !== null && v.request_id !== undefined && typeof v.request_id !== "string") {
    return false;
  }
  if (v.stack_trace !== null && v.stack_trace !== undefined && typeof v.stack_trace !== "string") {
    return false;
  }
  if (v.message !== null && v.message !== undefined && typeof v.message !== "string") {
    return false;
  }
  if (v.exception_type !== null && v.exception_type !== undefined && typeof v.exception_type !== "string") {
    return false;
  }
  return true;
}

export function parseDiagnosisErrorGroupEventsResponse(raw: unknown): DiagnosisErrorGroupEventsResponse | null {
  if (!isRecord(raw)) {
    return null;
  }
  if (typeof raw.total !== "number") {
    return null;
  }
  if (!Array.isArray(raw.items) || !raw.items.every(isDiagnosisErrorGroupEventItem)) {
    return null;
  }
  return raw as DiagnosisErrorGroupEventsResponse;
}

function isRecentJobFailureItem(v: unknown): v is RecentJobFailureItem {
  if (!isRecord(v)) {
    return false;
  }
  const sk = ["timestamp", "job_name", "trigger", "service_name", "environment"] as const;
  for (const k of sk) {
    if (typeof v[k] !== "string") {
      return false;
    }
  }
  if (typeof v.status_code !== "number" || typeof v.latency_ms !== "number") {
    return false;
  }
  if (v.message !== null && v.message !== undefined && typeof v.message !== "string") {
    return false;
  }
  if (
    v.correlated_request_id !== null &&
    v.correlated_request_id !== undefined &&
    typeof v.correlated_request_id !== "string"
  ) {
    return false;
  }
  return true;
}

export function parseRecentJobFailuresResponse(raw: unknown): RecentJobFailuresResponse | null {
  if (!isRecord(raw)) {
    return null;
  }
  const sk = ["server_now", "from_timestamp", "to_timestamp"] as const;
  for (const k of sk) {
    if (typeof raw[k] !== "string") {
      return null;
    }
  }
  if (!Array.isArray(raw.items) || !raw.items.every(isRecentJobFailureItem)) {
    return null;
  }
  return raw as RecentJobFailuresResponse;
}

function isAlertDispatchDetail(v: unknown): v is AlertDispatchItem["detail"] {
  if (!isRecord(v)) {
    return false;
  }
  return Object.values(v).every((x) => typeof x === "number" || typeof x === "string");
}

function isAlertDispatchItem(v: unknown): v is AlertDispatchItem {
  if (!isRecord(v)) {
    return false;
  }
  if (typeof v.id !== "number" || typeof v.alert_type !== "string") {
    return false;
  }
  if (v.destination_email !== null && typeof v.destination_email !== "string") {
    return false;
  }
  if (typeof v.delivered_via !== "string" || typeof v.status !== "string") {
    return false;
  }
  if (v.reason_code !== null && typeof v.reason_code !== "string") {
    return false;
  }
  if (v.reason_message !== null && typeof v.reason_message !== "string") {
    return false;
  }
  if (typeof v.attempt_count !== "number") {
    return false;
  }
  const timeKeys = ["triggered_at", "window_start", "window_end"] as const;
  for (const k of timeKeys) {
    if (typeof v[k] !== "string") {
      return false;
    }
  }
  if (v.delivered_at !== null && typeof v.delivered_at !== "string") {
    return false;
  }
  if (v.provider_message_id !== null && typeof v.provider_message_id !== "string") {
    return false;
  }
  if (!isAlertDispatchDetail(v.detail)) {
    return false;
  }
  return true;
}

export function parseAlertDispatchesResponse(raw: unknown): AlertDispatchesResponse | null {
  if (!isRecord(raw)) {
    return null;
  }
  for (const k of ["total", "limit", "offset"] as const) {
    if (typeof raw[k] !== "number") {
      return null;
    }
  }
  if (!Array.isArray(raw.items) || !raw.items.every(isAlertDispatchItem)) {
    return null;
  }
  return raw as AlertDispatchesResponse;
}

/**
 * Validates `POST /dashboard/query` JSON against the dashboard contract.
 * Returns `null` when required sections are missing or malformed.
 */
export function parseDashboardDataQueryResponse(raw: unknown): DashboardDataQueryResponse | null {
  if (!isRecord(raw)) {
    return null;
  }
  const overview = parseOverviewResponse(raw.overview);
  const requests = parseRequestsResponse(raw.requests);
  if (!overview || !requests) {
    return null;
  }

  const overview_extended = parseOptional(raw.overview_extended, parseOverviewExtendedResponse);
  if (raw.overview_extended != null && overview_extended === null) {
    return null;
  }
  const widgets = parseOptional(raw.widgets, parseDashboardWidgetsResponse);
  if (raw.widgets != null && widgets === null) {
    return null;
  }
  const error_groups = parseOptional(raw.error_groups, parseErrorGroupsResponse);
  if (raw.error_groups != null && error_groups === null) {
    return null;
  }
  const diagnosis_timeline = parseOptional(raw.diagnosis_timeline, parseDiagnosisTimelineResponse);
  if (raw.diagnosis_timeline != null && diagnosis_timeline === null) {
    return null;
  }
  const diagnosis_failures = parseOptional(raw.diagnosis_failures, parseDiagnosisFailureRoutesResponse);
  if (raw.diagnosis_failures != null && diagnosis_failures === null) {
    return null;
  }
  const diagnosis_error_group_events = parseOptional(
    raw.diagnosis_error_group_events,
    parseDiagnosisErrorGroupEventsResponse,
  );
  if (raw.diagnosis_error_group_events != null && diagnosis_error_group_events === null) {
    return null;
  }
  const recent_job_failures = parseOptional(raw.recent_job_failures, parseRecentJobFailuresResponse);
  if (raw.recent_job_failures != null && recent_job_failures === null) {
    return null;
  }
  const alert_dispatches = parseOptional(raw.alert_dispatches, parseAlertDispatchesResponse);
  if (raw.alert_dispatches != null && alert_dispatches === null) {
    return null;
  }

  return {
    overview,
    overview_extended,
    widgets,
    requests,
    error_groups,
    diagnosis_timeline,
    diagnosis_failures,
    diagnosis_error_group_events,
    recent_job_failures,
    alert_dispatches,
  };
}
