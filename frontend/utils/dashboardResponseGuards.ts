import type {
  DashboardAlertTestResponse,
  DashboardInternalMetricsResponse,
  DashboardMembershipItem,
  DashboardOrganizationListResponse,
  DashboardOrganizationSummary,
  DashboardProjectSummary,
  DashboardSystemDiagnosticsResponse,
  QueryExplorerResponse,
  TraceDetailResponse,
  TraceSearchResponse,
  TraceSpanItem,
  TraceSummaryItem,
} from "../components/dashboard/dashboardTypes";

function isRecord(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

function isJsonScalar(v: unknown): v is string | number | boolean | null {
  return v === null || typeof v === "string" || typeof v === "number" || typeof v === "boolean";
}

function isStringArray(v: unknown): v is string[] {
  return Array.isArray(v) && v.every((x) => typeof x === "string");
}

function isQueryExplorerRow(v: unknown): v is QueryExplorerResponse["rows"][number] {
  return Array.isArray(v) && v.every(isJsonScalar);
}

function isTraceSummaryItem(v: unknown): v is TraceSummaryItem {
  if (!isRecord(v)) {
    return false;
  }
  if (typeof v.trace_id !== "string") {
    return false;
  }
  if (typeof v.first_seen !== "string" || typeof v.last_seen !== "string") {
    return false;
  }
  if (typeof v.span_count !== "number" || typeof v.error_count !== "number") {
    return false;
  }
  if (!isStringArray(v.services)) {
    return false;
  }
  if (v.root_span_name !== null && typeof v.root_span_name !== "string") {
    return false;
  }
  return true;
}

function isTraceSpanItem(v: unknown): v is TraceSpanItem {
  if (!isRecord(v)) {
    return false;
  }
  const stringKeys = [
    "timestamp",
    "service_name",
    "environment",
    "span_name",
    "path",
    "method",
    "trace_id",
  ] as const;
  for (const k of stringKeys) {
    if (typeof v[k] !== "string") {
      return false;
    }
  }
  if (typeof v.status_code !== "number" || typeof v.latency_ms !== "number") {
    return false;
  }
  if (v.span_id !== null && typeof v.span_id !== "string") {
    return false;
  }
  if (v.parent_span_id !== null && typeof v.parent_span_id !== "string") {
    return false;
  }
  if (v.request_id !== null && typeof v.request_id !== "string") {
    return false;
  }
  if (v.otlp_status_code !== null && typeof v.otlp_status_code !== "number") {
    return false;
  }
  return true;
}

/** Returns parsed body or `null` if JSON shape does not match `QueryExplorerResponse`. */
export function parseQueryExplorerResponse(raw: unknown): QueryExplorerResponse | null {
  if (!isRecord(raw)) {
    return null;
  }
  const keys = ["server_now", "from_timestamp", "to_timestamp", "query"] as const;
  for (const k of keys) {
    if (typeof raw[k] !== "string") {
      return null;
    }
  }
  if (!isStringArray(raw.columns)) {
    return null;
  }
  if (!Array.isArray(raw.rows) || !raw.rows.every(isQueryExplorerRow)) {
    return null;
  }
  if (typeof raw.truncated !== "boolean") {
    return null;
  }
  return raw as QueryExplorerResponse;
}

/** Returns parsed body or `null` if JSON shape does not match `TraceSearchResponse`. */
export function parseTraceSearchResponse(raw: unknown): TraceSearchResponse | null {
  if (!isRecord(raw)) {
    return null;
  }
  const sk = ["server_now", "from_timestamp", "to_timestamp", "project_id"] as const;
  for (const k of sk) {
    if (typeof raw[k] !== "string") {
      return null;
    }
  }
  if (typeof raw.total !== "number") {
    return null;
  }
  if (!Array.isArray(raw.items) || !raw.items.every(isTraceSummaryItem)) {
    return null;
  }
  return raw as TraceSearchResponse;
}

/** Returns parsed body or `null` if JSON shape does not match `TraceDetailResponse`. */
export function parseTraceDetailResponse(raw: unknown): TraceDetailResponse | null {
  if (!isRecord(raw)) {
    return null;
  }
  if (typeof raw.trace_id !== "string") {
    return null;
  }
  if (raw.first_seen !== null && typeof raw.first_seen !== "string") {
    return null;
  }
  if (raw.last_seen !== null && typeof raw.last_seen !== "string") {
    return null;
  }
  if (typeof raw.error_count !== "number") {
    return null;
  }
  if (!Array.isArray(raw.items) || !raw.items.every(isTraceSpanItem)) {
    return null;
  }
  return raw as TraceDetailResponse;
}

const ORG_ROLES = ["owner", "admin", "member", "viewer"] as const;

function isOrgRole(v: unknown): v is DashboardOrganizationSummary["role"] {
  return typeof v === "string" && (ORG_ROLES as readonly string[]).includes(v);
}

function isDashboardProjectSummary(v: unknown): v is DashboardProjectSummary {
  if (!isRecord(v)) {
    return false;
  }
  if (typeof v.project_id !== "string" || typeof v.project_name !== "string") {
    return false;
  }
  if (v.organization_id !== null && typeof v.organization_id !== "string") {
    return false;
  }
  return true;
}

function isDashboardOrganizationSummary(v: unknown): v is DashboardOrganizationSummary {
  if (!isRecord(v)) {
    return false;
  }
  if (typeof v.organization_id !== "string" || typeof v.organization_name !== "string") {
    return false;
  }
  if (!isOrgRole(v.role)) {
    return false;
  }
  if (!Array.isArray(v.projects) || !v.projects.every(isDashboardProjectSummary)) {
    return false;
  }
  return true;
}

/** `GET /dashboard/organizations` */
export function parseDashboardOrganizationListResponse(raw: unknown): DashboardOrganizationListResponse | null {
  if (!isRecord(raw)) {
    return null;
  }
  if (!Array.isArray(raw.organizations) || !raw.organizations.every(isDashboardOrganizationSummary)) {
    return null;
  }
  return raw as DashboardOrganizationListResponse;
}

const MEMBER_ROLES = ORG_ROLES;

function isMemberRole(v: unknown): v is DashboardMembershipItem["role"] {
  return typeof v === "string" && (MEMBER_ROLES as readonly string[]).includes(v);
}

function isDashboardMembershipItem(v: unknown): v is DashboardMembershipItem {
  if (!isRecord(v)) {
    return false;
  }
  if (typeof v.user_id !== "string" || typeof v.email !== "string" || typeof v.created_at !== "string") {
    return false;
  }
  if (!isMemberRole(v.role)) {
    return false;
  }
  if (v.invited_email !== null && typeof v.invited_email !== "string") {
    return false;
  }
  return true;
}

/** `GET …/organizations/…/members` — body is `{ members: [...] }`. */
export function parseDashboardMembershipItemsPayload(raw: unknown): DashboardMembershipItem[] | null {
  if (!isRecord(raw)) {
    return null;
  }
  if (!Array.isArray(raw.members) || !raw.members.every(isDashboardMembershipItem)) {
    return null;
  }
  return raw.members;
}

/** `GET /dashboard/internal-metrics` */
export function parseDashboardInternalMetricsResponse(raw: unknown): DashboardInternalMetricsResponse | null {
  if (!isRecord(raw)) {
    return null;
  }
  if (typeof raw.enabled !== "boolean") {
    return null;
  }
  if (raw.reason !== null && typeof raw.reason !== "string") {
    return null;
  }
  if (raw.metrics !== null && raw.metrics !== undefined && typeof raw.metrics !== "object") {
    return null;
  }
  return raw as DashboardInternalMetricsResponse;
}

/** `GET /dashboard/system-diagnostics` */
export function parseDashboardSystemDiagnosticsResponse(raw: unknown): DashboardSystemDiagnosticsResponse | null {
  if (!isRecord(raw)) {
    return null;
  }
  if (typeof raw.generated_at !== "string") {
    return null;
  }
  const objectKeys = ["topology", "scheduler", "replay_queue", "ingestion_freshness", "config_diagnostics"] as const;
  for (const k of objectKeys) {
    if (!isRecord(raw[k])) {
      return null;
    }
  }
  return raw as DashboardSystemDiagnosticsResponse;
}

/** `GET` / `PUT` `/dashboard/event-plane-cutover` */
export function parseEventPlaneCutoverSettings(raw: unknown): { use_snapshot_read: boolean } | null {
  if (!isRecord(raw)) {
    return null;
  }
  if (typeof raw.use_snapshot_read !== "boolean") {
    return null;
  }
  return { use_snapshot_read: raw.use_snapshot_read };
}

/** `POST /dashboard/alert-test` */
export function parseDashboardAlertTestResponse(raw: unknown): DashboardAlertTestResponse | null {
  if (!isRecord(raw)) {
    return null;
  }
  if (typeof raw.status !== "string" || typeof raw.delivered_via !== "string") {
    return null;
  }
  if (raw.reason_code !== null && typeof raw.reason_code !== "string") {
    return null;
  }
  if (raw.reason_message !== null && typeof raw.reason_message !== "string") {
    return null;
  }
  if (typeof raw.attempt_count !== "number") {
    return null;
  }
  if (raw.delivered_at !== null && typeof raw.delivered_at !== "string") {
    return null;
  }
  if (raw.provider_message_id !== null && typeof raw.provider_message_id !== "string") {
    return null;
  }
  if (raw.destination_email !== null && typeof raw.destination_email !== "string") {
    return null;
  }
  return raw as DashboardAlertTestResponse;
}
