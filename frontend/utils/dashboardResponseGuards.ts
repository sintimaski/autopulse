import type {
  AlertCapabilitiesResponse,
  AlertChannelCapability,
  AlertSettings,
  DashboardAlertTestResponse,
  DashboardApiKeyIssueResponse,
  DashboardApiKeyItem,
  DashboardApiKeyListResponse,
  DashboardApiKeyRotateResponse,
  DashboardBootstrapResponse,
  DashboardInternalMetricsResponse,
  DashboardOperatorHealthResponse,
  DashboardOperatorHealthSubsystem,
  OperatorHealthStatus,
  DashboardStudioNavPage,
  DashboardMembershipItem,
  DashboardOnboardingStatusResponse,
  DashboardOrganizationListResponse,
  DashboardOrganizationSummary,
  DashboardProjectSummary,
  DashboardSystemDiagnosticsResponse,
  LogQueryValidationResponse,
  QueryExplorerResponse,
  RetentionSettings,
  ThemePreference,
  ThemeSettings,
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

function isOperatorHealthStatus(v: unknown): v is OperatorHealthStatus {
  return (
    v === "healthy" ||
    v === "degraded" ||
    v === "critical" ||
    v === "unknown" ||
    v === "not_configured"
  );
}

function isDashboardOperatorHealthSubsystem(v: unknown): v is DashboardOperatorHealthSubsystem {
  if (!isRecord(v)) {
    return false;
  }
  if (typeof v.id !== "string" || typeof v.label !== "string" || typeof v.summary !== "string") {
    return false;
  }
  if (!isOperatorHealthStatus(v.status)) {
    return false;
  }
  if (v.settings_anchor !== null && typeof v.settings_anchor !== "string") {
    return false;
  }
  return true;
}

/** `GET /dashboard/operator-health` */
export function parseDashboardOperatorHealthResponse(raw: unknown): DashboardOperatorHealthResponse | null {
  if (!isRecord(raw)) {
    return null;
  }
  if (typeof raw.enabled !== "boolean") {
    return null;
  }
  if (raw.reason !== null && typeof raw.reason !== "string") {
    return null;
  }
  if (typeof raw.generated_at !== "string") {
    return null;
  }
  if (!isOperatorHealthStatus(raw.overall_status)) {
    return null;
  }
  if (!Array.isArray(raw.subsystems) || !raw.subsystems.every(isDashboardOperatorHealthSubsystem)) {
    return null;
  }
  return raw as DashboardOperatorHealthResponse;
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

function isThemePreference(v: unknown): v is ThemePreference {
  return v === "system" || v === "light" || v === "dark";
}

function isRetentionPlan(v: unknown): v is RetentionSettings["retention_plan"] {
  return v === "starter" || v === "standard" || v === "extended";
}

function isArchivalStatus(v: unknown): v is RetentionSettings["archival_status"] {
  return v === "idle" || v === "running" || v === "failed";
}

/** `GET` / `PUT` `/dashboard/theme-settings` */
export function parseThemeSettings(raw: unknown): ThemeSettings | null {
  if (!isRecord(raw)) {
    return null;
  }
  if (!isThemePreference(raw.theme_preference)) {
    return null;
  }
  if (typeof raw.exclude_lumonox_traffic !== "boolean") {
    return null;
  }
  return raw as ThemeSettings;
}

/** `GET` / `PUT` `/dashboard/retention-settings` */
export function parseRetentionSettings(raw: unknown): RetentionSettings | null {
  if (!isRecord(raw)) {
    return null;
  }
  if (typeof raw.raw_events_days !== "number" || typeof raw.logs_query_max_window_minutes !== "number") {
    return null;
  }
  if (raw.retention_max_db_size_mb !== null && typeof raw.retention_max_db_size_mb !== "number") {
    return null;
  }
  if (raw.retention_max_log_rows !== null && typeof raw.retention_max_log_rows !== "number") {
    return null;
  }
  if (!isRetentionPlan(raw.retention_plan)) {
    return null;
  }
  if (typeof raw.archival_enabled !== "boolean") {
    return null;
  }
  if (raw.archival_mode !== "db_archive") {
    return null;
  }
  if (!isArchivalStatus(raw.archival_status)) {
    return null;
  }
  if (raw.archival_last_success_at !== null && typeof raw.archival_last_success_at !== "string") {
    return null;
  }
  if (raw.archival_last_error !== null && typeof raw.archival_last_error !== "string") {
    return null;
  }
  return raw as RetentionSettings;
}

/** `GET` / `PUT` `/dashboard/alert-settings` */
export function parseAlertSettings(raw: unknown): AlertSettings | null {
  if (!isRecord(raw)) {
    return null;
  }
  if (typeof raw.enabled !== "boolean") {
    return null;
  }
  if (raw.destination_email !== null && typeof raw.destination_email !== "string") {
    return null;
  }
  if (typeof raw.email_enabled !== "boolean" || typeof raw.slack_enabled !== "boolean") {
    return null;
  }
  if (raw.slack_webhook_url !== null && typeof raw.slack_webhook_url !== "string") {
    return null;
  }
  if (typeof raw.discord_enabled !== "boolean") {
    return null;
  }
  if (raw.discord_webhook_url !== null && typeof raw.discord_webhook_url !== "string") {
    return null;
  }
  if (typeof raw.webhook_enabled !== "boolean") {
    return null;
  }
  if (raw.webhook_url !== null && typeof raw.webhook_url !== "string") {
    return null;
  }
  const numericKeys = [
    "error_spike_ratio_threshold",
    "error_spike_min_requests",
    "error_spike_window_minutes",
    "outage_min_requests",
    "outage_window_minutes",
    "cooldown_minutes",
  ] as const;
  for (const k of numericKeys) {
    if (typeof raw[k] !== "number") {
      return null;
    }
  }
  if (typeof raw.notifications_muted !== "boolean") {
    return null;
  }
  if (raw.notifications_snoozed_until !== null && typeof raw.notifications_snoozed_until !== "string") {
    return null;
  }
  if (
    raw.last_notifications_acknowledged_at !== null &&
    typeof raw.last_notifications_acknowledged_at !== "string"
  ) {
    return null;
  }
  return raw as AlertSettings;
}

const ALERT_CHANNEL_IDS = ["email", "slack", "discord", "webhook"] as const;

function isAlertChannelId(v: unknown): v is AlertChannelCapability["channel"] {
  return typeof v === "string" && (ALERT_CHANNEL_IDS as readonly string[]).includes(v);
}

const ALERT_CHANNEL_STATUSES = ["active", "configured", "planned", "unavailable"] as const;

function isAlertChannelStatus(v: unknown): v is AlertChannelCapability["status"] {
  return typeof v === "string" && (ALERT_CHANNEL_STATUSES as readonly string[]).includes(v);
}

function isAlertChannelCapability(v: unknown): v is AlertChannelCapability {
  if (!isRecord(v)) {
    return false;
  }
  if (!isAlertChannelId(v.channel) || !isAlertChannelStatus(v.status)) {
    return false;
  }
  if (typeof v.enabled !== "boolean" || typeof v.reason !== "string") {
    return false;
  }
  return true;
}

export function parseAlertCapabilitiesResponse(raw: unknown): AlertCapabilitiesResponse | null {
  if (!isRecord(raw)) {
    return null;
  }
  if (!Array.isArray(raw.channels) || !raw.channels.every(isAlertChannelCapability)) {
    return null;
  }
  return raw as AlertCapabilitiesResponse;
}

function isDashboardApiKeyItem(v: unknown): v is DashboardApiKeyItem {
  if (!isRecord(v)) {
    return false;
  }
  if (typeof v.key_id !== "string" || typeof v.created_at !== "string") {
    return false;
  }
  if (v.revoked_at !== null && typeof v.revoked_at !== "string") {
    return false;
  }
  return true;
}

/** `GET /dashboard/auth/api-keys` */
export function parseDashboardApiKeyListResponse(raw: unknown): DashboardApiKeyListResponse | null {
  if (!isRecord(raw)) {
    return null;
  }
  if (!Array.isArray(raw.items) || !raw.items.every(isDashboardApiKeyItem)) {
    return null;
  }
  return raw as DashboardApiKeyListResponse;
}

/** `POST /dashboard/auth/api-keys/issue` */
export function parseDashboardApiKeyIssueResponse(raw: unknown): DashboardApiKeyIssueResponse | null {
  if (!isRecord(raw)) {
    return null;
  }
  if (typeof raw.key_id !== "string" || typeof raw.api_key !== "string" || typeof raw.created_at !== "string") {
    return null;
  }
  return raw as DashboardApiKeyIssueResponse;
}

/** `POST /dashboard/auth/api-keys/rotate` */
export function parseDashboardApiKeyRotateResponse(raw: unknown): DashboardApiKeyRotateResponse | null {
  if (!isRecord(raw)) {
    return null;
  }
  const keys = ["revoked_key_id", "replacement_key_id", "replacement_api_key", "rotated_at"] as const;
  for (const k of keys) {
    if (typeof raw[k] !== "string") {
      return null;
    }
  }
  return raw as DashboardApiKeyRotateResponse;
}

const ONBOARDING_STEPS = [
  "authenticate_session",
  "confirm_project",
  "provision_ingest_key",
  "send_first_event",
  "open_diagnosis",
  "completed",
] as const;

function isOnboardingStep(v: unknown): v is DashboardOnboardingStatusResponse["current_step"] {
  return typeof v === "string" && (ONBOARDING_STEPS as readonly string[]).includes(v);
}

/** `GET` bootstrap / `POST` onboarding-complete */
export function parseDashboardOnboardingStatusResponse(raw: unknown): DashboardOnboardingStatusResponse | null {
  if (!isRecord(raw)) {
    return null;
  }
  const boolKeys = [
    "session_authenticated",
    "project_ready",
    "ingest_key_ready",
    "first_event_received",
    "first_diagnostic_signal_ready",
    "onboarding_completed",
  ] as const;
  for (const k of boolKeys) {
    if (typeof raw[k] !== "boolean") {
      return null;
    }
  }
  if (typeof raw.next_recommended_action !== "string" || !isOnboardingStep(raw.current_step)) {
    return null;
  }
  return raw as DashboardOnboardingStatusResponse;
}

function isDashboardStudioNavPage(v: unknown): v is DashboardStudioNavPage {
  if (!isRecord(v)) {
    return false;
  }
  if (typeof v.page_id !== "string" || !v.page_id.trim()) {
    return false;
  }
  if (typeof v.pathname !== "string" || !v.pathname.startsWith("/")) {
    return false;
  }
  if (typeof v.sidebar_label !== "string" || !v.sidebar_label.trim()) {
    return false;
  }
  if (typeof v.page_title !== "string" || !v.page_title.trim()) {
    return false;
  }
  if (v.page_subtitle !== null && typeof v.page_subtitle !== "string") {
    return false;
  }
  if (typeof v.icon !== "string" || !v.icon.trim()) {
    return false;
  }
  if (v.nav_section_heading !== null && typeof v.nav_section_heading !== "string") {
    return false;
  }
  if (typeof v.nav_order !== "number" || !Number.isFinite(v.nav_order)) {
    return false;
  }
  return true;
}

/** `GET /dashboard/bootstrap` */
export function parseDashboardBootstrapResponse(raw: unknown): DashboardBootstrapResponse | null {
  if (!isRecord(raw)) {
    return null;
  }
  const retention = parseRetentionSettings(raw.retention_settings);
  const alert_settings = parseAlertSettings(raw.alert_settings);
  const theme_settings = parseThemeSettings(raw.theme_settings);
  const api_keys = parseDashboardApiKeyListResponse(raw.api_keys);
  const alert_capabilities = parseAlertCapabilitiesResponse(raw.alert_capabilities);
  if (!retention || !alert_settings || !theme_settings || !api_keys || !alert_capabilities) {
    return null;
  }
  let onboarding_status: DashboardOnboardingStatusResponse | null = null;
  if (raw.onboarding_status !== null && raw.onboarding_status !== undefined) {
    const parsed = parseDashboardOnboardingStatusResponse(raw.onboarding_status);
    if (!parsed) {
      return null;
    }
    onboarding_status = parsed;
  }
  let studio_nav_pages: DashboardStudioNavPage[] = [];
  if (raw.studio_nav_pages !== undefined && raw.studio_nav_pages !== null) {
    if (!Array.isArray(raw.studio_nav_pages) || !raw.studio_nav_pages.every(isDashboardStudioNavPage)) {
      return null;
    }
    studio_nav_pages = raw.studio_nav_pages as DashboardStudioNavPage[];
  }
  return {
    retention_settings: retention,
    alert_settings,
    theme_settings,
    api_keys,
    alert_capabilities,
    onboarding_status,
    studio_nav_pages,
  };
}

/** `POST /dashboard/log-query/validate` */
export function parseLogQueryValidationResponse(raw: unknown): LogQueryValidationResponse | null {
  if (!isRecord(raw)) {
    return null;
  }
  if (typeof raw.valid !== "boolean" || typeof raw.normalized_query !== "string") {
    return null;
  }
  if (raw.error !== null && typeof raw.error !== "string") {
    return null;
  }
  return raw as LogQueryValidationResponse;
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
