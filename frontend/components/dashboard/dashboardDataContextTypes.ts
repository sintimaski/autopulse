import type { Dispatch, SetStateAction } from "react";

import { computeOperationalSignals, M5_ALERT_DEFAULTS } from "../../utils/dashboardData";
import type { DashboardAuthSessionIssue } from "./useDashboardAuthSession";
import type { PersistedLogsClientSlice } from "./dashboardPersistentScope";
import type {
  AlertChannelCapability,
  AlertDispatchesResponse,
  AlertDispatchItem,
  AlertSettings,
  DashboardApiKeyItem,
  DashboardOnboardingStatusResponse,
  DashboardSessionResponse,
  DashboardWidgetsResponse,
  DiagnosisErrorGroupEventsResponse,
  DiagnosisFailureRoutesResponse,
  DiagnosisTimelineResponse,
  RecentJobFailuresResponse,
  ErrorGroupItem,
  ErrorGroupsResponse,
  GroupBy,
  LogQueryValidationResponse,
  OverviewBucket,
  OverviewExtendedResponse,
  OverviewResponse,
  RequestItem,
  RequestsResponse,
  RetentionSettings,
  SortDir,
  SortKey,
  ThemePreference,
  ERROR_GROUP_LIMIT_OPTIONS,
  GROUP_OPTIONS,
  METHOD_OPTIONS,
  REQUEST_LIMIT_OPTIONS,
  RUNBOOK_ALERTS_CMD,
  RUNBOOK_RETENTION_CMD,
  STATUS_CLASS_OPTIONS,
  WINDOW_OPTIONS,
} from "./dashboardTypes";

export type SavedSqlFilterPreset = {
  id: string;
  name: string;
  where: string;
  createdAt: string;
  updatedAt: string;
};

/** Optional toolbar draft merged into save when fields are not yet applied to context. */
export type SavedScopePresetSaveDraft = Partial<{
  isAbsoluteWindow: boolean;
  windowMinutes: number;
  windowFromTimestamp: string;
  windowToTimestamp: string;
  method: string;
  statusClass: string;
  minLatencyMs: string;
  maxLatencyMs: string;
  pathQuery: string;
  serverEnvironmentQuery: string;
  serverServiceQuery: string;
  errorGroupSort: "last_seen" | "count";
}>;

export type SavedScopePreset = {
  id: string;
  name: string;
  scope: {
    isAbsoluteWindow: boolean;
    windowMinutes: number;
    windowFromTimestamp: string;
    windowToTimestamp: string;
    method: string;
    statusClass: string;
    minLatencyMs: string;
    maxLatencyMs: string;
    pathQuery: string;
    serverEnvironmentQuery: string;
    serverServiceQuery: string;
    requestLimit: number;
    errorGroupLimit: number;
    errorGroupSort: "last_seen" | "count";
    sqlFilterApplied: string;
    sqlFilterEnabled: boolean;
  };
  createdAt: string;
  updatedAt: string;
};

export type DashboardDataContextValue = {
  /** True when the dashboard session cookie is authenticated (not the project ingest API key). */
  hasDashboardSession: boolean;
  sessionEmail: string | null;
  /** Role in the organization for the session's active project (from ``/dashboard/auth/session``). */
  sessionMembershipRole: DashboardSessionResponse["membership_role"];
  /** Ingest and dashboard traffic are queried for this project id (cookie session). */
  sessionProjectId: string | null;
  sessionOrganizationId: string | null;
  /** False until `/dashboard/auth/session` has completed (avoids flashing sign-in while cookies are validated). */
  authSessionResolved: boolean;
  /** When there is no session, whether the API rejected cookies vs a connectivity problem. */
  dashboardAuthSessionIssue: DashboardAuthSessionIssue;
  windowMinutes: number;
  windowFromTimestamp: string;
  windowToTimestamp: string;
  serverNowTimestamp: string | null;
  isAbsoluteWindow: boolean;
  method: string;
  statusClass: string;
  requestLimit: number;
  requestPage: number;
  errorGroupLimit: number;
  errorGroupPage: number;
  minLatencyMs: string;
  maxLatencyMs: string;
  serverServiceQuery: string;
  serverEnvironmentQuery: string;
  serverServiceTags: string[];
  serverEnvironmentTags: string[];
  pathQuery: string;
  groupBy: GroupBy;
  sortKey: SortKey;
  sortDir: SortDir;
  envTags: Set<string>;
  serviceTags: Set<string>;
  overview: OverviewResponse | null;
  overviewExtended: OverviewExtendedResponse | null;
  dashboardWidgets: DashboardWidgetsResponse | null;
  requests: RequestsResponse | null;
  errorGroups: ErrorGroupsResponse | null;
  diagnosisTimeline: DiagnosisTimelineResponse | null;
  diagnosisFailures: DiagnosisFailureRoutesResponse | null;
  diagnosisErrorGroupEvents: DiagnosisErrorGroupEventsResponse | null;
  recentJobFailures: RecentJobFailuresResponse | null;
  alertSettings: AlertSettings | null;
  apiKeys: DashboardApiKeyItem[];
  lastIssuedApiKey: string | null;
  alertDispatches: AlertDispatchesResponse | null;
  alertCapabilities: AlertChannelCapability[];
  onboardingStatus: DashboardOnboardingStatusResponse | null;
  /**
   * Set when `/dashboard/bootstrap` fails while signed in. UI should show a non-blocking banner with
   * {@link retryWorkspaceBootstrap}; does not replace per-request `errorMessage` from traffic fetches.
   */
  workspaceBootstrapError: string | null;
  retryWorkspaceBootstrap: () => void;
  retentionSettings: RetentionSettings | null;
  themePreference: ThemePreference;
  excludeAutopulseTraffic: boolean;
  errorGroupSort: "last_seen" | "count";
  loading: boolean;
  errorMessage: string | null;
  refreshToken: number;
  /** When true, WebSocket/poll/visibility-driven refresh is paused (Diagnosis/Requests sticky bar). Scope changes still fetch. */
  liveDataPaused: boolean;
  toggleLiveDataPaused: () => void;
  runbookMessage: string | null;
  alertSettingsMessage: string | null;
  alertSettingsSaving: boolean;
  themeSettingsSaving: boolean;
  expandedRequestIds: Set<string>;
  setRequestLimit: (n: number) => void;
  setRequestPage: Dispatch<SetStateAction<number>>;
  setErrorGroupLimit: (n: number) => void;
  setErrorGroupPage: Dispatch<SetStateAction<number>>;
  setMinLatencyMs: Dispatch<SetStateAction<string>>;
  setMaxLatencyMs: Dispatch<SetStateAction<string>>;
  setServerServiceQuery: Dispatch<SetStateAction<string>>;
  setServerEnvironmentQuery: Dispatch<SetStateAction<string>>;
  setServerServiceTags: (tags: string[]) => void;
  setServerEnvironmentTags: (tags: string[]) => void;
  setPathQuery: Dispatch<SetStateAction<string>>;
  setGroupBy: Dispatch<SetStateAction<GroupBy>>;
  setErrorGroupSort: (s: "last_seen" | "count") => void;
  setRefreshToken: Dispatch<SetStateAction<number>>;
  onServerWindowChange: (minutes: number) => void;
  setAbsoluteWindow: (fromIso: string, toIso: string) => void;
  clearAbsoluteWindow: () => void;
  onServerMethodChange: (value: string) => void;
  onServerStatusClassChange: (value: string) => void;
  toggleEnv: (value: string) => void;
  toggleService: (value: string) => void;
  clearClientFilters: () => void;
  /** Replace logs page client filters (group/sort/tags) from URL or defaults. */
  hydrateLogsViewFromUrl: (next: PersistedLogsClientSlice) => void;
  copyRunbookCommand: (command: string, label: string) => Promise<void>;
  saveAlertSettings: (next: AlertSettings) => Promise<boolean>;
  saveThemePreference: (next: ThemePreference) => Promise<boolean>;
  saveExcludeAutopulseTraffic: (next: boolean) => Promise<boolean>;
  saveRetentionSettings: (next: RetentionSettings) => Promise<boolean>;
  refreshApiKeys: () => Promise<void>;
  /** Rebind the dashboard cookie session to another project you belong to (refreshes data). */
  setActiveDashboardProject: (projectId: string) => Promise<boolean>;
  signOutDashboard: () => Promise<void>;
  /** Persists project onboarding completion after first ingest (server-validated). */
  completeOnboarding: () => Promise<boolean>;
  issueApiKey: () => Promise<boolean>;
  rotateApiKey: (keyId: string) => Promise<boolean>;
  revokeApiKey: (keyId: string) => Promise<boolean>;
  validateSqlFilterDraft: () => Promise<LogQueryValidationResponse | null>;
  applySqlFilter: () => Promise<boolean>;
  disableSqlFilter: () => void;
  setSqlFilterDraft: Dispatch<SetStateAction<string>>;
  setSqlFilterApplied: Dispatch<SetStateAction<string>>;
  setSqlFilterEnabled: Dispatch<SetStateAction<boolean>>;
  updateAlertSettingsDraft: (next: AlertSettings) => void;
  toggleRequestRow: (id: string) => void;
  onSortHeader: (key: SortKey) => void;
  rawItems: RequestItem[];
  availableEnvironments: string[];
  availableServices: string[];
  filteredSorted: RequestItem[];
  topFailingRoutes: [string, number][];
  recentErrorsPreview: ErrorGroupItem[];
  displayedErrorGroups: ErrorGroupItem[];
  recentAlertDispatches: AlertDispatchItem[];
  grouped: { key: string; label: string; items: RequestItem[] }[];
  sparklineSeries: OverviewBucket[];
  operationalSignals: ReturnType<typeof computeOperationalSignals>;
  sqlFilterDraft: string;
  sqlFilterApplied: string;
  sqlFilterEnabled: boolean;
  sqlFilterValidation: LogQueryValidationResponse | null;
  sqlFilterValidating: boolean;
  savedSqlFilterPresets: SavedSqlFilterPreset[];
  savedScopePresets: SavedScopePreset[];
  saveSqlFilterPreset: (name: string, where: string) => {
    ok: boolean;
    error?: string;
  };
  removeSqlFilterPreset: (id: string) => void;
  applySavedSqlFilterPreset: (id: string) => void;
  saveScopePreset: (
    name: string,
    draft?: SavedScopePresetSaveDraft,
  ) => {
    ok: boolean;
    error?: string;
  };
  removeScopePreset: (id: string) => void;
  applySavedScopePreset: (id: string) => {
    ok: boolean;
    error?: string;
  };
  WINDOW_OPTIONS: typeof WINDOW_OPTIONS;
  METHOD_OPTIONS: typeof METHOD_OPTIONS;
  STATUS_CLASS_OPTIONS: typeof STATUS_CLASS_OPTIONS;
  REQUEST_LIMIT_OPTIONS: typeof REQUEST_LIMIT_OPTIONS;
  ERROR_GROUP_LIMIT_OPTIONS: typeof ERROR_GROUP_LIMIT_OPTIONS;
  GROUP_OPTIONS: typeof GROUP_OPTIONS;
  RUNBOOK_ALERTS_CMD: typeof RUNBOOK_ALERTS_CMD;
  RUNBOOK_RETENTION_CMD: typeof RUNBOOK_RETENTION_CMD;
  M5_ALERT_DEFAULTS: typeof M5_ALERT_DEFAULTS;
};

export type DashboardHomeSliceValue = {
  overview: OverviewResponse | null;
  overviewExtended: OverviewExtendedResponse | null;
  dashboardWidgets: DashboardWidgetsResponse | null;
  requests: RequestsResponse | null;
  errorGroups: ErrorGroupsResponse | null;
  sparklineSeries: OverviewBucket[];
  operationalSignals: ReturnType<typeof computeOperationalSignals>;
  rawItems: RequestItem[];
  windowMinutes: number;
  isAbsoluteWindow: boolean;
  windowFromTimestamp: string;
  windowToTimestamp: string;
  method: string;
  statusClass: string;
  requestLimit: number;
  errorGroupLimit: number;
  errorGroupSort: "last_seen" | "count";
  minLatencyMs: string;
  maxLatencyMs: string;
  pathQuery: string;
  serverEnvironmentQuery: string;
  serverServiceQuery: string;
  sqlFilterApplied: string;
  sqlFilterEnabled: boolean;
  errorMessage: string | null;
  recentJobFailures: RecentJobFailuresResponse | null;
};

export type DashboardDiagnosisSliceValue = {
  diagnosisTimeline: DiagnosisTimelineResponse | null;
  diagnosisFailures: DiagnosisFailureRoutesResponse | null;
  diagnosisErrorGroupEvents: DiagnosisErrorGroupEventsResponse | null;
  errorGroups: ErrorGroupsResponse | null;
  recentJobFailures: RecentJobFailuresResponse | null;
};

export type DashboardAlertsSliceValue = {
  alertDispatches: AlertDispatchesResponse | null;
  alertSettings: AlertSettings | null;
  alertCapabilities: AlertChannelCapability[];
};

export type DashboardLogsSliceValue = {
  requests: RequestsResponse | null;
  filteredSorted: RequestItem[];
  grouped: { key: string; label: string; items: RequestItem[] }[];
  availableServices: string[];
  availableEnvironments: string[];
};
