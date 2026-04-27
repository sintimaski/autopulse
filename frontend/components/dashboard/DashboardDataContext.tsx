"use client";

import { usePathname } from "next/navigation";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";

import {
  computeOperationalSignals,
  M5_ALERT_DEFAULTS,
  resolveSparklineSeries,
  type OverviewBucket,
} from "../../utils/dashboardData";
import {
  buildDashboardFetchError,
  buildDashboardNetworkError,
  type DashboardFetchResult,
} from "../../utils/dashboardFetchErrors";
import {
  buildApiUrl,
  buildUpdatesWebsocketUrl,
  apiKey,
  type AlertDispatchesResponse,
  type AlertDispatchItem,
  compareValues,
  ERROR_GROUP_LIMIT_OPTIONS,
  GROUP_OPTIONS,
  METHOD_OPTIONS,
  REQUEST_LIMIT_OPTIONS,
  RUNBOOK_ALERTS_CMD,
  RUNBOOK_RETENTION_CMD,
  STATUS_CLASS_OPTIONS,
  WINDOW_OPTIONS,
  type AlertSettings,
  type DiagnosisErrorGroupEventsResponse,
  type DiagnosisFailureRoutesResponse,
  type DiagnosisTimelineResponse,
  type ErrorGroupItem,
  type ErrorGroupsResponse,
  type GroupBy,
  type OverviewResponse,
  type OverviewExtendedResponse,
  type RequestItem,
  type RequestsResponse,
  type RetentionSettings,
  type LogQueryValidationResponse,
  type SortDir,
  type SortKey,
  type ThemePreference,
  type ThemeSettings,
} from "./dashboardTypes";
import {
  normalizeCommaSeparated,
  splitCommaSeparated,
} from "./dashboardQueryState";
import {
  buildDashboardDataCacheScopeKey,
  readDashboardSnapshot,
  writeDashboardSnapshot,
} from "./dashboardSnapshotCache";
import { wrapEventSqlWhereForValidate } from "./eventSqlFilter";
import { toDashboardRoutePath } from "./dashboardRoutePath";

export type DashboardDataContextValue = {
  hasApiKey: boolean;
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
  requests: RequestsResponse | null;
  errorGroups: ErrorGroupsResponse | null;
  diagnosisTimeline: DiagnosisTimelineResponse | null;
  diagnosisFailures: DiagnosisFailureRoutesResponse | null;
  diagnosisErrorGroupEvents: DiagnosisErrorGroupEventsResponse | null;
  alertSettings: AlertSettings | null;
  alertDispatches: AlertDispatchesResponse | null;
  retentionSettings: RetentionSettings | null;
  themePreference: ThemePreference;
  excludeAutopulseTraffic: boolean;
  errorGroupSort: "last_seen" | "count";
  loading: boolean;
  errorMessage: string | null;
  refreshToken: number;
  runbookMessage: string | null;
  alertSettingsMessage: string | null;
  alertSettingsSaving: boolean;
  themeSettingsSaving: boolean;
  expandedRequestIds: Set<string>;
  setRequestLimit: (n: number) => void;
  setRequestPage: React.Dispatch<React.SetStateAction<number>>;
  setErrorGroupLimit: (n: number) => void;
  setErrorGroupPage: React.Dispatch<React.SetStateAction<number>>;
  setMinLatencyMs: React.Dispatch<React.SetStateAction<string>>;
  setMaxLatencyMs: React.Dispatch<React.SetStateAction<string>>;
  setServerServiceQuery: React.Dispatch<React.SetStateAction<string>>;
  setServerEnvironmentQuery: React.Dispatch<React.SetStateAction<string>>;
  setServerServiceTags: (tags: string[]) => void;
  setServerEnvironmentTags: (tags: string[]) => void;
  setPathQuery: React.Dispatch<React.SetStateAction<string>>;
  setGroupBy: React.Dispatch<React.SetStateAction<GroupBy>>;
  setErrorGroupSort: (s: "last_seen" | "count") => void;
  setRefreshToken: React.Dispatch<React.SetStateAction<number>>;
  onServerWindowChange: (minutes: number) => void;
  setAbsoluteWindow: (fromIso: string, toIso: string) => void;
  clearAbsoluteWindow: () => void;
  onServerMethodChange: (value: string) => void;
  onServerStatusClassChange: (value: string) => void;
  toggleEnv: (value: string) => void;
  toggleService: (value: string) => void;
  clearClientFilters: () => void;
  copyRunbookCommand: (command: string, label: string) => Promise<void>;
  saveAlertSettings: (next: AlertSettings) => Promise<boolean>;
  saveThemePreference: (next: ThemePreference) => Promise<boolean>;
  saveExcludeAutopulseTraffic: (next: boolean) => Promise<boolean>;
  saveRetentionSettings: (next: RetentionSettings) => Promise<boolean>;
  validateSqlFilterDraft: () => Promise<LogQueryValidationResponse | null>;
  applySqlFilter: () => Promise<boolean>;
  disableSqlFilter: () => void;
  setSqlFilterDraft: React.Dispatch<React.SetStateAction<string>>;
  setSqlFilterApplied: React.Dispatch<React.SetStateAction<string>>;
  setSqlFilterEnabled: React.Dispatch<React.SetStateAction<boolean>>;
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

const DashboardDataContext = createContext<DashboardDataContextValue | null>(null);

export function useDashboardData(): DashboardDataContextValue {
  const ctx = useContext(DashboardDataContext);
  if (!ctx) {
    throw new Error("useDashboardData must be used within DashboardDataProvider");
  }
  return ctx;
}

export function DashboardDataProvider({ children }: { children: ReactNode }) {
  const hasApiKey = Boolean(apiKey);

  const [windowMinutes, setWindowMinutes] = useState(60);
  const [absoluteWindow, setAbsoluteWindowState] = useState<{ from: string; to: string } | null>(null);
  const [method, setMethod] = useState("ALL");
  const [statusClass, setStatusClass] = useState("ALL");
  const [requestLimit, setRequestLimit] = useState(100);
  const [requestPage, setRequestPage] = useState(0);
  const [errorGroupLimit, setErrorGroupLimit] = useState(25);
  const [errorGroupPage, setErrorGroupPage] = useState(0);
  const [minLatencyMs, setMinLatencyMs] = useState("");
  const [maxLatencyMs, setMaxLatencyMs] = useState("");
  const [serverServiceQuery, setServerServiceQuery] = useState("");
  const [serverEnvironmentQuery, setServerEnvironmentQuery] = useState("");
  const [pathQuery, setPathQuery] = useState("");
  const [groupBy, setGroupBy] = useState<GroupBy>("none");
  const [sortKey, setSortKey] = useState<SortKey>("timestamp");
  const [sortDir, setSortDir] = useState<SortDir>("desc");
  const [envTags, setEnvTags] = useState<Set<string>>(new Set());
  const [serviceTags, setServiceTags] = useState<Set<string>>(new Set());
  const [overview, setOverview] = useState<OverviewResponse | null>(null);
  const [overviewExtended, setOverviewExtended] = useState<OverviewExtendedResponse | null>(null);
  const [requests, setRequests] = useState<RequestsResponse | null>(null);
  const [errorGroups, setErrorGroups] = useState<ErrorGroupsResponse | null>(null);
  const [diagnosisTimeline, setDiagnosisTimeline] = useState<DiagnosisTimelineResponse | null>(null);
  const [diagnosisFailures, setDiagnosisFailures] = useState<DiagnosisFailureRoutesResponse | null>(null);
  const [diagnosisErrorGroupEvents, setDiagnosisErrorGroupEvents] = useState<DiagnosisErrorGroupEventsResponse | null>(null);
  const [alertSettings, setAlertSettings] = useState<AlertSettings | null>(null);
  const [alertDispatches, setAlertDispatches] = useState<AlertDispatchesResponse | null>(null);
  const [retentionSettings, setRetentionSettings] = useState<RetentionSettings | null>(null);
  const [themePreference, setThemePreference] = useState<ThemePreference>("system");
  const [excludeAutopulseTraffic, setExcludeAutopulseTraffic] = useState(true);
  const [errorGroupSort, setErrorGroupSort] = useState<"last_seen" | "count">("last_seen");
  const [loading, setLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [refreshToken, setRefreshToken] = useState(0);
  const [runbookMessage, setRunbookMessage] = useState<string | null>(null);
  const [alertSettingsMessage, setAlertSettingsMessage] = useState<string | null>(null);
  const [alertSettingsSaving, setAlertSettingsSaving] = useState(false);
  const [themeSettingsSaving, setThemeSettingsSaving] = useState(false);
  const [sqlFilterDraft, setSqlFilterDraft] = useState("");
  const [sqlFilterApplied, setSqlFilterApplied] = useState("");
  const [sqlFilterEnabled, setSqlFilterEnabled] = useState(false);
  const [sqlFilterValidation, setSqlFilterValidation] = useState<LogQueryValidationResponse | null>(null);
  const [sqlFilterValidating, setSqlFilterValidating] = useState(false);
  const runbookTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const wsReconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const wsRefreshDebounceTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  /** Ensures a refresh runs during steady ingest even if debounce keeps resetting. */
  const wsRefreshMaxWaitTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const wsHeartbeatTimer = useRef<ReturnType<typeof setInterval> | null>(null);
  const hasLoadedDashboardData = useRef(false);
  const rawDashboardPathname = usePathname();
  const dashboardRoutePath = useMemo(
    () => toDashboardRoutePath(rawDashboardPathname),
    [rawDashboardPathname],
  );
  const [expandedRequestIds, setExpandedRequestIds] = useState<Set<string>>(() => new Set());
  const serverEnvironmentTags = useMemo(
    () => splitCommaSeparated(serverEnvironmentQuery),
    [serverEnvironmentQuery],
  );
  const serverServiceTags = useMemo(() => splitCommaSeparated(serverServiceQuery), [serverServiceQuery]);

  const serverNowTimestamp = overview?.server_now ?? requests?.server_now ?? errorGroups?.server_now ?? null;
  const toIsoWindow = useMemo(() => {
    if (!absoluteWindow) {
      return null;
    }
    const fromMs = new Date(absoluteWindow.from).getTime();
    const toMs = new Date(absoluteWindow.to).getTime();
    if (!Number.isFinite(fromMs) || !Number.isFinite(toMs) || fromMs >= toMs) {
      return null;
    }
    return absoluteWindow;
  }, [absoluteWindow]);

  // Settings endpoints rarely change; load once per API key (saves also update local state).
  useEffect(() => {
    if (!apiKey) {
      return;
    }
    let cancelled = false;
    const run = async () => {
      const headers = { Authorization: `Bearer ${apiKey}` };
      try {
        const results = (await Promise.all([
          fetch(buildApiUrl("/dashboard/retention-settings"), { headers }),
          fetch(buildApiUrl("/dashboard/alert-settings"), { headers }),
          fetch(buildApiUrl("/dashboard/theme-settings"), { headers }),
        ]).then(([retentionSettingsResponse, alertSettingsResponse, themeSettingsResponse]) => [
          { endpoint: "retention-settings" as const, response: retentionSettingsResponse },
          { endpoint: "alert-settings" as const, response: alertSettingsResponse },
          { endpoint: "theme-settings" as const, response: themeSettingsResponse },
        ])) as DashboardFetchResult[];

        const fetchError = buildDashboardFetchError(results);
        if (fetchError) {
          throw new Error(fetchError);
        }

        const [retentionSettingsData, alertSettingsData, themeSettingsData] = (await Promise.all(
          results.map(async ({ response }) => response.json()),
        )) as [RetentionSettings, AlertSettings, ThemeSettings];

        if (cancelled) {
          return;
        }
        setRetentionSettings(retentionSettingsData);
        setAlertSettings(alertSettingsData);
        setThemePreference(themeSettingsData.theme_preference);
        setExcludeAutopulseTraffic(themeSettingsData.exclude_autopulse_traffic);
      } catch (error) {
        if (cancelled) {
          return;
        }
        setErrorMessage((prev) => prev ?? buildDashboardNetworkError(error));
      }
    };

    void run();
    return () => {
      cancelled = true;
    };
  }, [apiKey]);

  useEffect(() => {
    if (!apiKey) {
      return;
    }

    const run = async () => {
      const routePath = dashboardRoutePath;
      if (routePath === "/settings") {
        return;
      }

      const includeExtended = routePath === "/dashboard" || routePath === "/diagnosis";
      const includeErrorGroups = routePath === "/dashboard" || routePath === "/diagnosis";
      const includeDiagnosis = routePath === "/diagnosis";
      const includeAlertDispatches = routePath === "/alerts";
      const useSnapshot = routePath === "/dashboard";

      const isInitialLoad = !hasLoadedDashboardData.current;
      if (isInitialLoad) {
        setLoading(true);
      }
      setErrorMessage(null);
      try {
        const headers = { Authorization: `Bearer ${apiKey}` };
        const overviewParams = new URLSearchParams();
        if (toIsoWindow) {
          overviewParams.set("from_timestamp", toIsoWindow.from);
          overviewParams.set("to_timestamp", toIsoWindow.to);
        } else {
          overviewParams.set("window_minutes", String(windowMinutes));
        }

        const requestsParams = new URLSearchParams({
          limit: String(requestLimit),
          offset: String(requestPage * requestLimit),
        });
        if (toIsoWindow) {
          requestsParams.set("from_timestamp", toIsoWindow.from);
          requestsParams.set("to_timestamp", toIsoWindow.to);
        } else {
          requestsParams.set("window_minutes", String(windowMinutes));
        }
        if (method !== "ALL") {
          requestsParams.set("method", method);
        }
        if (statusClass !== "ALL") {
          requestsParams.set("status_class", statusClass);
        }
        const minLatency = Number(minLatencyMs);
        if (minLatencyMs.trim() !== "" && Number.isFinite(minLatency) && minLatency >= 0) {
          requestsParams.set("min_latency_ms", String(minLatency));
        }
        const maxLatency = Number(maxLatencyMs);
        if (maxLatencyMs.trim() !== "" && Number.isFinite(maxLatency) && maxLatency >= 0) {
          requestsParams.set("max_latency_ms", String(maxLatency));
        }
        const serverPath = pathQuery.trim();
        if (serverPath) {
          requestsParams.set("path_contains", serverPath);
        }
        const envCsv = normalizeCommaSeparated(serverEnvironmentQuery);
        if (envCsv) {
          requestsParams.set("environments", envCsv);
        }
        const serviceCsv = normalizeCommaSeparated(serverServiceQuery);
        if (serviceCsv) {
          requestsParams.set("services", serviceCsv);
        }
        if (sqlFilterEnabled && sqlFilterApplied.trim()) {
          overviewParams.set("event_sql_filter", sqlFilterApplied.trim());
          requestsParams.set("event_sql_filter", sqlFilterApplied.trim());
        }

        const errorGroupsParams = new URLSearchParams({
          limit: String(errorGroupLimit),
          offset: String(errorGroupPage * errorGroupLimit),
        });
        if (toIsoWindow) {
          errorGroupsParams.set("from_timestamp", toIsoWindow.from);
          errorGroupsParams.set("to_timestamp", toIsoWindow.to);
        } else {
          errorGroupsParams.set("window_minutes", String(windowMinutes));
        }
        if (method !== "ALL") {
          errorGroupsParams.set("method", method);
        }
        if (statusClass !== "ALL") {
          errorGroupsParams.set("status_class", statusClass);
        }
        if (minLatencyMs.trim() !== "" && Number.isFinite(minLatency) && minLatency >= 0) {
          errorGroupsParams.set("min_latency_ms", String(minLatency));
        }
        if (maxLatencyMs.trim() !== "" && Number.isFinite(maxLatency) && maxLatency >= 0) {
          errorGroupsParams.set("max_latency_ms", String(maxLatency));
        }
        if (serverPath) {
          errorGroupsParams.set("path_contains", serverPath);
        }
        if (envCsv) {
          errorGroupsParams.set("environments", envCsv);
        }
        if (serviceCsv) {
          errorGroupsParams.set("services", serviceCsv);
        }
        if (sqlFilterEnabled && sqlFilterApplied.trim()) {
          errorGroupsParams.set("event_sql_filter", sqlFilterApplied.trim());
        }
        const alertDispatchesParams = new URLSearchParams({
          from_timestamp: new Date(
            new Date(toIsoWindow?.to ?? new Date().toISOString()).getTime() - 7 * 24 * 60 * 60 * 1000,
          ).toISOString(),
          to_timestamp: toIsoWindow?.to ?? new Date().toISOString(),
          limit: "25",
          offset: "0",
        });
        const diagnosisSharedParams = new URLSearchParams();
        if (toIsoWindow) {
          diagnosisSharedParams.set("from_timestamp", toIsoWindow.from);
          diagnosisSharedParams.set("to_timestamp", toIsoWindow.to);
        } else {
          diagnosisSharedParams.set("window_minutes", String(windowMinutes));
        }
        if (method !== "ALL") {
          diagnosisSharedParams.set("method", method);
        }
        if (statusClass !== "ALL") {
          diagnosisSharedParams.set("status_class", statusClass);
        }
        if (envCsv) {
          diagnosisSharedParams.set("environments", envCsv);
        }
        if (serviceCsv) {
          diagnosisSharedParams.set("services", serviceCsv);
        }
        if (serverPath) {
          diagnosisSharedParams.set("path_contains", serverPath);
        }
        if (minLatencyMs.trim() !== "" && Number.isFinite(minLatency) && minLatency >= 0) {
          diagnosisSharedParams.set("min_latency_ms", String(minLatency));
        }
        if (maxLatencyMs.trim() !== "" && Number.isFinite(maxLatency) && maxLatency >= 0) {
          diagnosisSharedParams.set("max_latency_ms", String(maxLatency));
        }
        if (sqlFilterEnabled && sqlFilterApplied.trim()) {
          diagnosisSharedParams.set("event_sql_filter", sqlFilterApplied.trim());
        }

        const scopeKey = buildDashboardDataCacheScopeKey({
          windowFrom: toIsoWindow?.from ?? "",
          windowTo: toIsoWindow?.to ?? "",
          windowMinutes,
          isAbsoluteWindow: Boolean(toIsoWindow),
          method,
          statusClass,
          minLatencyMs,
          maxLatencyMs,
          pathQuery: serverPath,
          serverEnvironmentQuery: envCsv,
          serverServiceQuery: serviceCsv,
          requestLimit,
          requestPage,
          errorGroupLimit,
          errorGroupPage,
          errorGroupSort,
          sqlFilterEnabled,
          sqlFilterApplied,
        });
        const cached = useSnapshot ? readDashboardSnapshot(scopeKey) : null;
        if (cached) {
          setOverview(cached.overview);
          setOverviewExtended(cached.overviewExtended);
          setRequests(cached.requests);
          setErrorGroups(cached.errorGroups);
          setDiagnosisTimeline(cached.diagnosisTimeline ?? null);
          setDiagnosisFailures(cached.diagnosisFailures ?? null);
          setAlertDispatches(cached.alertDispatches ?? null);
        }

        const fetchTasks: Array<{
          endpoint: DashboardFetchResult["endpoint"];
          promise: Promise<Response>;
        }> = [
          {
            endpoint: "overview",
            promise: fetch(buildApiUrl(`/dashboard/overview?${overviewParams.toString()}`), {
              headers,
            }),
          },
        ];
        if (includeExtended) {
          fetchTasks.push({
            endpoint: "overview-extended",
            promise: fetch(buildApiUrl(`/dashboard/overview/extended?${overviewParams.toString()}`), {
              headers,
            }),
          });
        }
        fetchTasks.push({
          endpoint: "requests",
          promise: fetch(buildApiUrl(`/dashboard/requests?${requestsParams.toString()}`), { headers }),
        });
        if (includeErrorGroups) {
          fetchTasks.push({
            endpoint: "error-groups",
            promise: fetch(buildApiUrl(`/dashboard/error-groups?${errorGroupsParams.toString()}`), {
              headers,
            }),
          });
        }
        if (includeDiagnosis) {
          fetchTasks.push({
            endpoint: "diagnosis-timeline",
            promise: fetch(
              buildApiUrl(`/dashboard/diagnosis/timeline?${diagnosisSharedParams.toString()}`),
              { headers },
            ),
          });
          fetchTasks.push({
            endpoint: "diagnosis-failures",
            promise: fetch(
              buildApiUrl(`/dashboard/diagnosis/failures-by-route?${diagnosisSharedParams.toString()}`),
              { headers },
            ),
          });
        }
        if (includeAlertDispatches) {
          fetchTasks.push({
            endpoint: "alert-dispatches",
            promise: fetch(
              buildApiUrl(`/dashboard/alert-dispatches?${alertDispatchesParams.toString()}`),
              { headers },
            ),
          });
        }

        const results: DashboardFetchResult[] = await Promise.all(
          fetchTasks.map(async ({ endpoint, promise }) => ({
            endpoint,
            response: await promise,
          })),
        );

        const fetchError = buildDashboardFetchError(results);
        if (fetchError) {
          throw new Error(fetchError);
        }

        const byEndpoint = new Map<DashboardFetchResult["endpoint"], unknown>();
        await Promise.all(
          results.map(async ({ endpoint, response }) => {
            byEndpoint.set(endpoint, await response.json());
          }),
        );

        const overviewData = byEndpoint.get("overview") as OverviewResponse;
        const requestsData = byEndpoint.get("requests") as RequestsResponse;

        setOverview(overviewData);
        setRequests(requestsData);

        if (includeExtended) {
          setOverviewExtended(byEndpoint.get("overview-extended") as OverviewExtendedResponse);
        } else {
          setOverviewExtended(null);
        }
        if (includeErrorGroups) {
          setErrorGroups(byEndpoint.get("error-groups") as ErrorGroupsResponse);
        } else {
          setErrorGroups(null);
        }
        if (includeDiagnosis) {
          setDiagnosisTimeline(byEndpoint.get("diagnosis-timeline") as DiagnosisTimelineResponse);
          setDiagnosisFailures(byEndpoint.get("diagnosis-failures") as DiagnosisFailureRoutesResponse);
        } else {
          setDiagnosisTimeline(null);
          setDiagnosisFailures(null);
        }
        if (includeAlertDispatches) {
          setAlertDispatches(byEndpoint.get("alert-dispatches") as AlertDispatchesResponse);
        } else {
          setAlertDispatches(null);
        }

        if (useSnapshot && includeExtended && includeErrorGroups) {
          writeDashboardSnapshot(scopeKey, {
            overview: overviewData,
            overviewExtended: byEndpoint.get("overview-extended") as OverviewExtendedResponse,
            requests: requestsData,
            errorGroups: byEndpoint.get("error-groups") as ErrorGroupsResponse,
          });
        }
        hasLoadedDashboardData.current = true;
      } catch (error) {
        if (!hasLoadedDashboardData.current) {
          setErrorMessage(buildDashboardNetworkError(error));
        }
      } finally {
        if (isInitialLoad) {
          setLoading(false);
        }
      }
    };

    void run();
  }, [
    dashboardRoutePath,
    method,
    statusClass,
    toIsoWindow,
    windowMinutes,
    refreshToken,
    requestLimit,
    requestPage,
    errorGroupLimit,
    errorGroupPage,
    minLatencyMs,
    maxLatencyMs,
    pathQuery,
    serverEnvironmentQuery,
    serverServiceQuery,
    sqlFilterEnabled,
    sqlFilterApplied,
  ]);

  useEffect(() => {
    return () => {
      if (runbookTimer.current) {
        clearTimeout(runbookTimer.current);
      }
      if (wsReconnectTimer.current) {
        clearTimeout(wsReconnectTimer.current);
      }
      if (wsRefreshDebounceTimer.current) {
        clearTimeout(wsRefreshDebounceTimer.current);
      }
      if (wsRefreshMaxWaitTimer.current) {
        clearTimeout(wsRefreshMaxWaitTimer.current);
      }
      if (wsHeartbeatTimer.current) {
        clearInterval(wsHeartbeatTimer.current);
      }
    };
  }, []);

  useEffect(() => {
    if (!apiKey) {
      return;
    }
    const wsUrl = buildUpdatesWebsocketUrl(apiKey);
    const INGEST_REFRESH_DEBOUNCE_MS = 500;
    const INGEST_REFRESH_MAX_WAIT_MS = 2500;

    const clearIngestRefreshTimers = () => {
      if (wsRefreshDebounceTimer.current) {
        clearTimeout(wsRefreshDebounceTimer.current);
        wsRefreshDebounceTimer.current = null;
      }
      if (wsRefreshMaxWaitTimer.current) {
        clearTimeout(wsRefreshMaxWaitTimer.current);
        wsRefreshMaxWaitTimer.current = null;
      }
    };

    const scheduleIngestRefresh = () => {
      if (wsRefreshDebounceTimer.current) {
        clearTimeout(wsRefreshDebounceTimer.current);
      }
      wsRefreshDebounceTimer.current = setTimeout(() => {
        wsRefreshDebounceTimer.current = null;
        if (wsRefreshMaxWaitTimer.current) {
          clearTimeout(wsRefreshMaxWaitTimer.current);
          wsRefreshMaxWaitTimer.current = null;
        }
        setRefreshToken((token) => token + 1);
      }, INGEST_REFRESH_DEBOUNCE_MS);

      if (!wsRefreshMaxWaitTimer.current) {
        wsRefreshMaxWaitTimer.current = setTimeout(() => {
          wsRefreshMaxWaitTimer.current = null;
          if (wsRefreshDebounceTimer.current) {
            clearTimeout(wsRefreshDebounceTimer.current);
            wsRefreshDebounceTimer.current = null;
          }
          setRefreshToken((token) => token + 1);
        }, INGEST_REFRESH_MAX_WAIT_MS);
      }
    };

    let ws: WebSocket | null = null;
    let cancelled = false;
    let reconnectAttempt = 0;

    const connect = () => {
      if (cancelled) {
        return;
      }
      ws = new WebSocket(wsUrl);
      ws.onopen = () => {
        reconnectAttempt = 0;
        if (wsHeartbeatTimer.current) {
          clearInterval(wsHeartbeatTimer.current);
        }
        wsHeartbeatTimer.current = setInterval(() => {
          if (!ws || ws.readyState !== WebSocket.OPEN) {
            return;
          }
          ws.send("ping");
        }, 20000);
      };
      ws.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data) as { type?: string };
          if (payload.type !== "ingest") {
            return;
          }
        } catch {
          return;
        }
        scheduleIngestRefresh();
      };
      ws.onclose = () => {
        clearIngestRefreshTimers();
        if (wsHeartbeatTimer.current) {
          clearInterval(wsHeartbeatTimer.current);
          wsHeartbeatTimer.current = null;
        }
        if (cancelled) {
          return;
        }
        reconnectAttempt += 1;
        const delayMs = Math.min(30_000, 1000 * 2 ** Math.min(reconnectAttempt, 5));
        wsReconnectTimer.current = setTimeout(connect, delayMs);
      };
      ws.onerror = () => {
        ws?.close();
      };
    };

    connect();
    return () => {
      cancelled = true;
      if (wsReconnectTimer.current) {
        clearTimeout(wsReconnectTimer.current);
      }
      clearIngestRefreshTimers();
      if (wsHeartbeatTimer.current) {
        clearInterval(wsHeartbeatTimer.current);
      }
      ws?.close();
    };
  }, [apiKey]);

  const rawItems = useMemo(() => requests?.items ?? [], [requests]);

  const onServerWindowChange = useCallback((minutes: number) => {
    setAbsoluteWindowState(null);
    setWindowMinutes(minutes);
    setRequestPage(0);
    setErrorGroupPage(0);
  }, []);
  const setAbsoluteWindow = useCallback((fromIso: string, toIso: string) => {
    const fromMs = new Date(fromIso).getTime();
    const toMs = new Date(toIso).getTime();
    if (!Number.isFinite(fromMs) || !Number.isFinite(toMs) || fromMs >= toMs) {
      return;
    }
    setAbsoluteWindowState({ from: new Date(fromMs).toISOString(), to: new Date(toMs).toISOString() });
    setRequestPage(0);
    setErrorGroupPage(0);
  }, []);
  const clearAbsoluteWindow = useCallback(() => {
    setAbsoluteWindowState(null);
    setRequestPage(0);
    setErrorGroupPage(0);
  }, []);

  const onServerMethodChange = useCallback((value: string) => {
    setMethod(value);
    setRequestPage(0);
    setErrorGroupPage(0);
  }, []);

  const onServerStatusClassChange = useCallback((value: string) => {
    setStatusClass(value);
    setRequestPage(0);
    setErrorGroupPage(0);
  }, []);

  const availableEnvironments = useMemo(
    () => [...new Set(rawItems.map((i) => i.environment))].sort(),
    [rawItems],
  );
  const availableServices = useMemo(
    () => [...new Set(rawItems.map((i) => i.service_name))].sort(),
    [rawItems],
  );

  const setServerEnvironmentTags = useCallback((tags: string[]) => {
    setServerEnvironmentQuery(normalizeCommaSeparated(tags.join(",")));
    setRequestPage(0);
    setErrorGroupPage(0);
  }, []);

  const setServerServiceTags = useCallback((tags: string[]) => {
    setServerServiceQuery(normalizeCommaSeparated(tags.join(",")));
    setRequestPage(0);
    setErrorGroupPage(0);
  }, []);

  const toggleValueInSet = useCallback(
    (setter: React.Dispatch<React.SetStateAction<Set<string>>>, value: string) => {
      setter((prev) => {
        const next = new Set(prev);
        if (next.has(value)) {
          next.delete(value);
        } else {
          next.add(value);
        }
        return next;
      });
    },
    [],
  );

  const toggleEnv = useCallback((value: string) => {
    toggleValueInSet(setEnvTags, value);
  }, [toggleValueInSet]);

  const toggleService = useCallback((value: string) => {
    toggleValueInSet(setServiceTags, value);
  }, [toggleValueInSet]);

  const clearClientFilters = useCallback(() => {
    setPathQuery("");
    setMinLatencyMs("");
    setMaxLatencyMs("");
    setServerServiceQuery("");
    setServerEnvironmentQuery("");
    setEnvTags(new Set());
    setServiceTags(new Set());
    setGroupBy("none");
    setSortKey("timestamp");
    setSortDir("desc");
  }, []);

  const copyRunbookCommand = useCallback(async (command: string, label: string) => {
    try {
      await navigator.clipboard.writeText(command);
      if (runbookTimer.current) {
        clearTimeout(runbookTimer.current);
      }
      setRunbookMessage(`${label} copied to clipboard.`);
      runbookTimer.current = setTimeout(() => setRunbookMessage(null), 2800);
    } catch {
      setRunbookMessage("Clipboard unavailable — copy the command text manually.");
    }
  }, []);

  const saveAlertSettings = useCallback(
    async (next: AlertSettings): Promise<boolean> => {
      if (!apiKey) {
        return false;
      }
      setAlertSettingsSaving(true);
      setAlertSettingsMessage(null);
      try {
        const response = await fetch(buildApiUrl("/dashboard/alert-settings"), {
          method: "PUT",
          headers: {
            Authorization: `Bearer ${apiKey}`,
            "Content-Type": "application/json",
          },
          body: JSON.stringify(next),
        });
        if (!response.ok) {
          throw new Error(`alert-settings update failed (${response.status})`);
        }
        const updated = (await response.json()) as AlertSettings;
        setAlertSettings(updated);
        setAlertSettingsMessage("Alert settings saved.");
        return true;
      } catch {
        setAlertSettingsMessage("Failed to save alert settings. Try again.");
        return false;
      } finally {
        setAlertSettingsSaving(false);
      }
    },
    [],
  );

  const updateAlertSettingsDraft = useCallback((next: AlertSettings) => {
    setAlertSettings(next);
  }, []);

  const saveThemePreference = useCallback(
    async (next: ThemePreference): Promise<boolean> => {
      if (!apiKey) {
        return false;
      }
      setThemeSettingsSaving(true);
      try {
        const response = await fetch(buildApiUrl("/dashboard/theme-settings"), {
          method: "PUT",
          headers: {
            Authorization: `Bearer ${apiKey}`,
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            theme_preference: next,
            exclude_autopulse_traffic: excludeAutopulseTraffic,
          }),
        });
        if (!response.ok) {
          throw new Error(`theme-settings update failed (${response.status})`);
        }
        const updated = (await response.json()) as ThemeSettings;
        setThemePreference(updated.theme_preference);
        setExcludeAutopulseTraffic(updated.exclude_autopulse_traffic);
        return true;
      } catch {
        return false;
      } finally {
        setThemeSettingsSaving(false);
      }
    },
    [excludeAutopulseTraffic],
  );

  const saveExcludeAutopulseTraffic = useCallback(
    async (next: boolean): Promise<boolean> => {
      if (!apiKey) {
        return false;
      }
      setThemeSettingsSaving(true);
      try {
        const response = await fetch(buildApiUrl("/dashboard/theme-settings"), {
          method: "PUT",
          headers: {
            Authorization: `Bearer ${apiKey}`,
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            theme_preference: themePreference,
            exclude_autopulse_traffic: next,
          }),
        });
        if (!response.ok) {
          throw new Error(`theme-settings update failed (${response.status})`);
        }
        const updated = (await response.json()) as ThemeSettings;
        setThemePreference(updated.theme_preference);
        setExcludeAutopulseTraffic(updated.exclude_autopulse_traffic);
        setRefreshToken((n) => n + 1);
        return true;
      } catch {
        return false;
      } finally {
        setThemeSettingsSaving(false);
      }
    },
    [themePreference],
  );

  const saveRetentionSettings = useCallback(
    async (next: RetentionSettings): Promise<boolean> => {
      if (!apiKey) {
        return false;
      }
      try {
        const response = await fetch(buildApiUrl("/dashboard/retention-settings"), {
          method: "PUT",
          headers: {
            Authorization: `Bearer ${apiKey}`,
            "Content-Type": "application/json",
          },
          body: JSON.stringify(next),
        });
        if (!response.ok) {
          throw new Error(`retention-settings update failed (${response.status})`);
        }
        const updated = (await response.json()) as RetentionSettings;
        setRetentionSettings(updated);
        return true;
      } catch {
        return false;
      }
    },
    [],
  );

  const validateSqlFilterDraft = useCallback(async (): Promise<LogQueryValidationResponse | null> => {
    if (!apiKey) {
      return null;
    }
    const wrapped = wrapEventSqlWhereForValidate(sqlFilterDraft);
    if (!wrapped) {
      const empty: LogQueryValidationResponse = {
        valid: false,
        normalized_query: "",
        error: "Enter a WHERE fragment (e.g. status_code >= 500).",
      };
      setSqlFilterValidation(empty);
      return empty;
    }
    setSqlFilterValidating(true);
    try {
      const response = await fetch(buildApiUrl("/dashboard/log-query/validate"), {
        method: "POST",
        headers: {
          Authorization: `Bearer ${apiKey}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ query: wrapped, page_size: 100 }),
      });
      const payload = (await response.json()) as LogQueryValidationResponse;
      setSqlFilterValidation(payload);
      return payload;
    } catch {
      const fallback: LogQueryValidationResponse = {
        valid: false,
        normalized_query: wrapped,
        error: "Validation request failed",
      };
      setSqlFilterValidation(fallback);
      return fallback;
    } finally {
      setSqlFilterValidating(false);
    }
  }, [apiKey, sqlFilterDraft]);

  const applySqlFilter = useCallback(async (): Promise<boolean> => {
    const result = await validateSqlFilterDraft();
    if (!result?.valid) {
      return false;
    }
    const applied = sqlFilterDraft.trim();
    setSqlFilterApplied(applied);
    setSqlFilterEnabled(true);
    setRequestPage(0);
    setErrorGroupPage(0);
    return true;
  }, [sqlFilterDraft, validateSqlFilterDraft]);

  const disableSqlFilter = useCallback(() => {
    setSqlFilterEnabled(false);
    setRequestPage(0);
    setErrorGroupPage(0);
  }, []);

  const toggleRequestRow = useCallback((id: string) => {
    setExpandedRequestIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  }, []);

  const onSortHeader = useCallback(
    (key: SortKey) => {
      if (sortKey === key) {
        setSortDir((d) => (d === "asc" ? "desc" : "asc"));
      } else {
        setSortKey(key);
        setSortDir(key === "timestamp" || key === "status_code" || key === "latency_ms" ? "desc" : "asc");
      }
    },
    [sortKey],
  );

  const filteredSorted = useMemo(() => {
    const q = pathQuery.trim().toLowerCase();
    let rows = rawItems.filter((item) => {
      if (q && !item.path.toLowerCase().includes(q)) {
        return false;
      }
      if (envTags.size > 0 && !envTags.has(item.environment)) {
        return false;
      }
      if (serviceTags.size > 0 && !serviceTags.has(item.service_name)) {
        return false;
      }
      return true;
    });

    rows = [...rows].sort((a, b) => {
      const va = a[sortKey];
      const vb = b[sortKey];
      if (sortKey === "timestamp") {
        const ta = new Date(va as string).getTime();
        const tb = new Date(vb as string).getTime();
        return sortDir === "asc" ? ta - tb : tb - ta;
      }
      return compareValues(va as string | number, vb as string | number, sortDir);
    });

    return rows;
  }, [rawItems, pathQuery, envTags, serviceTags, sortKey, sortDir]);

  const topFailingRoutes = useMemo(() => {
    const counts = new Map<string, number>();
    for (const item of rawItems) {
      if (item.status_code >= 500) {
        counts.set(item.path, (counts.get(item.path) ?? 0) + 1);
      }
    }
    return [...counts.entries()]
      .sort((a, b) => b[1] - a[1])
      .slice(0, 5);
  }, [rawItems]);

  const recentErrorsPreview = useMemo(() => {
    const items = errorGroups?.items;
    if (!items?.length) {
      return [];
    }
    return [...items]
      .sort(
        (a, b) =>
          new Date(b.last_seen).getTime() -
          new Date(a.last_seen).getTime(),
      )
      .slice(0, 5);
  }, [errorGroups]);

  useEffect(() => {
    if (!apiKey) {
      return;
    }
    if (dashboardRoutePath !== "/diagnosis") {
      queueMicrotask(() => {
        setDiagnosisErrorGroupEvents(null);
      });
      return;
    }
    const groupKey = recentErrorsPreview[0]?.group_key;
    if (!groupKey) {
      queueMicrotask(() => {
        setDiagnosisErrorGroupEvents(null);
      });
      return;
    }
    const params = new URLSearchParams({
      group_key: groupKey,
      limit: "20",
      offset: "0",
    });
    if (toIsoWindow) {
      params.set("from_timestamp", toIsoWindow.from);
      params.set("to_timestamp", toIsoWindow.to);
    } else {
      params.set("window_minutes", String(windowMinutes));
    }
    if (sqlFilterEnabled && sqlFilterApplied.trim()) {
      params.set("event_sql_filter", sqlFilterApplied.trim());
    }
    void fetch(buildApiUrl(`/dashboard/diagnosis/error-group-events?${params.toString()}`), {
      headers: { Authorization: `Bearer ${apiKey}` },
    })
      .then((response) => (response.ok ? response.json() : null))
      .then((payload) => {
        if (payload) {
          setDiagnosisErrorGroupEvents(payload as DiagnosisErrorGroupEventsResponse);
        }
      })
      .catch(() => {
        setDiagnosisErrorGroupEvents(null);
      });
  }, [
    apiKey,
    dashboardRoutePath,
    recentErrorsPreview,
    toIsoWindow,
    windowMinutes,
    sqlFilterEnabled,
    sqlFilterApplied,
  ]);

  const displayedErrorGroups = useMemo(() => {
    const source = errorGroups?.items;
    if (!source?.length) {
      return [];
    }
    const items = [...source];
    if (errorGroupSort === "count") {
      items.sort((a, b) => {
        if (b.count !== a.count) {
          return b.count - a.count;
        }
        return new Date(b.last_seen).getTime() - new Date(a.last_seen).getTime();
      });
    } else {
      items.sort((a, b) => {
        const t = new Date(b.last_seen).getTime() - new Date(a.last_seen).getTime();
        if (t !== 0) {
          return t;
        }
        return b.count - a.count;
      });
    }
    return items;
  }, [errorGroups, errorGroupSort]);

  const recentAlertDispatches = useMemo<AlertDispatchItem[]>(
    () => alertDispatches?.items ?? [],
    [alertDispatches],
  );

  const grouped = useMemo(() => {
    if (groupBy === "none") {
      return [{ key: "all", label: "All traffic", items: filteredSorted }];
    }
    const map = new Map<string, RequestItem[]>();
    for (const item of filteredSorted) {
      const k = String(item[groupBy as keyof RequestItem] ?? "");
      if (!map.has(k)) {
        map.set(k, []);
      }
      map.get(k)!.push(item);
    }
    const keys = [...map.keys()].sort((a, b) => a.localeCompare(b));
    return keys.map((key) => ({
      key,
      label: key || "(empty)",
      items: map.get(key)!,
    }));
  }, [filteredSorted, groupBy]);

  const sparklineSeries = useMemo(
    () =>
      resolveSparklineSeries(overview, requests, {
        // Keep dashboard cards/charts scoped to overview response only.
        preferRequests: false,
      }),
    [overview, requests],
  );

  const operationalSignals = useMemo(
    () => computeOperationalSignals(overview, M5_ALERT_DEFAULTS),
    [overview],
  );

  const value = useMemo(
    (): DashboardDataContextValue => ({
      hasApiKey,
      windowMinutes,
      windowFromTimestamp:
        toIsoWindow?.from ?? overview?.from_timestamp ?? requests?.from_timestamp ?? "",
      windowToTimestamp: toIsoWindow?.to ?? overview?.to_timestamp ?? requests?.to_timestamp ?? "",
      serverNowTimestamp,
      isAbsoluteWindow: absoluteWindow !== null,
      method,
      statusClass,
      requestLimit,
      requestPage,
      errorGroupLimit,
      errorGroupPage,
      minLatencyMs,
      maxLatencyMs,
      serverServiceQuery,
      serverEnvironmentQuery,
      serverServiceTags,
      serverEnvironmentTags,
      pathQuery,
      groupBy,
      sortKey,
      sortDir,
      envTags,
      serviceTags,
      overview,
      overviewExtended,
      requests,
      errorGroups,
      diagnosisTimeline,
      diagnosisFailures,
      diagnosisErrorGroupEvents,
      alertSettings,
      alertDispatches,
      retentionSettings,
      themePreference,
      excludeAutopulseTraffic,
      errorGroupSort,
      loading,
      errorMessage,
      refreshToken,
      runbookMessage,
      alertSettingsMessage,
      alertSettingsSaving,
      themeSettingsSaving,
      expandedRequestIds,
      setRequestLimit,
      setRequestPage,
      setErrorGroupLimit,
      setErrorGroupPage,
      setMinLatencyMs,
      setMaxLatencyMs,
      setServerServiceQuery,
      setServerEnvironmentQuery,
      setServerServiceTags,
      setServerEnvironmentTags,
      setPathQuery,
      setGroupBy,
      setErrorGroupSort,
      setRefreshToken,
      onServerWindowChange,
      setAbsoluteWindow,
      clearAbsoluteWindow,
      onServerMethodChange,
      onServerStatusClassChange,
      toggleEnv,
      toggleService,
      clearClientFilters,
      copyRunbookCommand,
      saveAlertSettings,
      saveThemePreference,
      saveExcludeAutopulseTraffic,
      saveRetentionSettings,
      validateSqlFilterDraft,
      applySqlFilter,
      disableSqlFilter,
      setSqlFilterDraft,
      setSqlFilterApplied,
      setSqlFilterEnabled,
      updateAlertSettingsDraft,
      toggleRequestRow,
      onSortHeader,
      rawItems,
      availableEnvironments,
      availableServices,
      filteredSorted,
      topFailingRoutes,
      recentErrorsPreview,
      displayedErrorGroups,
      recentAlertDispatches,
      grouped,
      sparklineSeries,
      operationalSignals,
      sqlFilterDraft,
      sqlFilterApplied,
      sqlFilterEnabled,
      sqlFilterValidation,
      sqlFilterValidating,
      WINDOW_OPTIONS,
      METHOD_OPTIONS,
      STATUS_CLASS_OPTIONS,
      REQUEST_LIMIT_OPTIONS,
      ERROR_GROUP_LIMIT_OPTIONS,
      GROUP_OPTIONS,
      RUNBOOK_ALERTS_CMD,
      RUNBOOK_RETENTION_CMD,
      M5_ALERT_DEFAULTS,
    }),
    [
      hasApiKey,
      windowMinutes,
      toIsoWindow,
      absoluteWindow,
      overview,
      overviewExtended,
      requests,
      errorGroups,
      diagnosisTimeline,
      diagnosisFailures,
      diagnosisErrorGroupEvents,
      serverNowTimestamp,
      method,
      statusClass,
      requestLimit,
      requestPage,
      errorGroupLimit,
      errorGroupPage,
      minLatencyMs,
      maxLatencyMs,
      serverServiceQuery,
      serverEnvironmentQuery,
      serverServiceTags,
      serverEnvironmentTags,
      pathQuery,
      groupBy,
      sortKey,
      sortDir,
      envTags,
      serviceTags,
      alertSettings,
      alertDispatches,
      retentionSettings,
      themePreference,
      excludeAutopulseTraffic,
      errorGroupSort,
      loading,
      errorMessage,
      refreshToken,
      runbookMessage,
      alertSettingsMessage,
      alertSettingsSaving,
      themeSettingsSaving,
      expandedRequestIds,
      onServerWindowChange,
      setAbsoluteWindow,
      clearAbsoluteWindow,
      onServerMethodChange,
      onServerStatusClassChange,
      setServerServiceTags,
      setServerEnvironmentTags,
      toggleEnv,
      toggleService,
      clearClientFilters,
      copyRunbookCommand,
      saveAlertSettings,
      saveThemePreference,
      saveExcludeAutopulseTraffic,
      saveRetentionSettings,
      validateSqlFilterDraft,
      applySqlFilter,
      disableSqlFilter,
      setSqlFilterDraft,
      setSqlFilterApplied,
      setSqlFilterEnabled,
      updateAlertSettingsDraft,
      toggleRequestRow,
      onSortHeader,
      rawItems,
      availableEnvironments,
      availableServices,
      filteredSorted,
      topFailingRoutes,
      recentErrorsPreview,
      displayedErrorGroups,
      recentAlertDispatches,
      grouped,
      sparklineSeries,
      operationalSignals,
      sqlFilterDraft,
      sqlFilterApplied,
      sqlFilterEnabled,
      sqlFilterValidation,
      sqlFilterValidating,
    ],
  );

  return <DashboardDataContext.Provider value={value}>{children}</DashboardDataContext.Provider>;
}
