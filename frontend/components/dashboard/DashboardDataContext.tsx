"use client";

import { usePathname } from "next/navigation";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useLayoutEffect,
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
import { parseDashboardDataQueryResponse } from "../../utils/dashboardQueryResponseGuards";
import {
  parseAlertSettings,
  parseDashboardApiKeyIssueResponse,
  parseDashboardApiKeyListResponse,
  parseDashboardApiKeyRotateResponse,
  parseDashboardOnboardingStatusResponse,
  parseLogQueryValidationResponse,
  parseRetentionSettings,
  parseThemeSettings,
} from "../../utils/dashboardResponseGuards";
import {
  type AlertDispatchesResponse,
  type AlertCapabilitiesResponse,
  type AlertChannelCapability,
  type AlertDispatchItem,
  compareValues,
  type DashboardApiKeyIssueResponse,
  type DashboardApiKeyItem,
  type DashboardApiKeyListResponse,
  type DashboardApiKeyRotateResponse,
  type DashboardDataQueryRequest,
  type DashboardDataQueryResponse,
  type DashboardOnboardingStatusResponse,
  type DashboardWidgetsResponse,
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
  type RecentJobFailuresResponse,
  type RequestItem,
  type RequestsResponse,
  type RetentionSettings,
  type LogQueryValidationResponse,
  type SortDir,
  type SortKey,
  type ThemePreference,
  type ThemeSettings,
} from "./dashboardTypes";
import { applyDashboardScopedQueryState } from "./applyDashboardScopedQuery";
import {
  mergePersistedScopedSession,
  readPersistedDashboardSession,
  type PersistedLogsClientSlice,
} from "./dashboardPersistentScope";
import {
  buildDashboardDataQueryRequest,
  planDashboardBatchQueryForRoute,
} from "./dashboardQueryBundle";
import { normalizeCommaSeparated, splitCommaSeparated, type DashboardScopedQueryState } from "./dashboardQueryState";
import {
  buildDashboardDataCacheScopeKey,
  readDashboardSnapshot,
  writeDashboardSnapshot,
} from "./dashboardSnapshotCache";
import {
  readStoredDashboardThemePreference,
  writeStoredDashboardThemePreference,
} from "./dashboardThemeStorage";
import {
  pinDashboardViewportScroll,
  scheduleDashboardScopeAnchorRepair,
  scheduleDashboardViewportScrollRestore,
} from "./dashboardViewportScroll";
import { wrapEventSqlWhereForValidate } from "./eventSqlFilter";
import { createBootstrapFailureOnboardingFallback } from "./dashboardBootstrapFallback";
import { dashboardMagicLinkHref, toDashboardRoutePath } from "./dashboardRoutePath";
import {
  coerceScopeNumber,
  savedPresetScopeToDashboardQuery,
} from "./dashboardScopePresetUtils";
import { useDashboardAuthSession } from "./useDashboardAuthSession";
import {
  useDashboardVisibilityRefreshBump,
  useDashboardWsDisconnectedFallbackPoll,
} from "./live/useDashboardLiveClientEffects";
import { useDashboardLiveWebSocket } from "./live/useDashboardLiveWebSocket";
import {
  buildOptionalGzipJsonRequest,
  LIVE_FETCH_SLOW_MS,
  LIVE_REFRESH_BACKOFF_DURATION_MS,
  trimDashboardWidgetPayload,
} from "./dashboardDataFetchUtils";
import {
  dashboardSessionFetch,
  dashboardSessionJsonPost,
  dashboardSessionJsonPut,
} from "./dashboardSessionFetch";
import { loadDashboardBootstrap } from "./dashboardWorkspaceBootstrap";
import type {
  DashboardAlertsSliceValue,
  DashboardDataContextValue,
  DashboardDiagnosisSliceValue,
  DashboardHomeSliceValue,
  DashboardLogsSliceValue,
  SavedScopePreset,
  SavedScopePresetSaveDraft,
  SavedSqlFilterPreset,
} from "./dashboardDataContextTypes";

export type {
  DashboardAlertsSliceValue,
  DashboardDataContextValue,
  DashboardDiagnosisSliceValue,
  DashboardHomeSliceValue,
  DashboardLogsSliceValue,
  SavedScopePreset,
  SavedScopePresetSaveDraft,
  SavedSqlFilterPreset,
} from "./dashboardDataContextTypes";

export const DashboardDataContext = createContext<DashboardDataContextValue | null>(null);
const DashboardHomeSliceContext = createContext<DashboardHomeSliceValue | null>(null);
const DashboardDiagnosisSliceContext = createContext<DashboardDiagnosisSliceValue | null>(null);
const DashboardAlertsSliceContext = createContext<DashboardAlertsSliceValue | null>(null);
const DashboardLogsSliceContext = createContext<DashboardLogsSliceValue | null>(null);

export function useDashboardData(): DashboardDataContextValue {
  const ctx = useContext(DashboardDataContext);
  if (!ctx) {
    throw new Error("useDashboardData must be used within DashboardDataProvider");
  }
  return ctx;
}

export function useDashboardHomeDataSlice(): DashboardHomeSliceValue {
  const ctx = useContext(DashboardHomeSliceContext);
  if (!ctx) {
    throw new Error("useDashboardHomeDataSlice must be used within DashboardDataProvider");
  }
  return ctx;
}

export function useDashboardDiagnosisDataSlice(): DashboardDiagnosisSliceValue {
  const ctx = useContext(DashboardDiagnosisSliceContext);
  if (!ctx) {
    throw new Error("useDashboardDiagnosisDataSlice must be used within DashboardDataProvider");
  }
  return ctx;
}

export function useDashboardAlertsDataSlice(): DashboardAlertsSliceValue {
  const ctx = useContext(DashboardAlertsSliceContext);
  if (!ctx) {
    throw new Error("useDashboardAlertsDataSlice must be used within DashboardDataProvider");
  }
  return ctx;
}

export function useDashboardLogsDataSlice(): DashboardLogsSliceValue {
  const ctx = useContext(DashboardLogsSliceContext);
  if (!ctx) {
    throw new Error("useDashboardLogsDataSlice must be used within DashboardDataProvider");
  }
  return ctx;
}

export function DashboardDataProvider({ children }: { children: ReactNode }) {
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
  const [dashboardWidgets, setDashboardWidgets] = useState<DashboardWidgetsResponse | null>(null);
  const [requests, setRequests] = useState<RequestsResponse | null>(null);
  const [errorGroups, setErrorGroups] = useState<ErrorGroupsResponse | null>(null);
  const [diagnosisTimeline, setDiagnosisTimeline] = useState<DiagnosisTimelineResponse | null>(null);
  const [diagnosisFailures, setDiagnosisFailures] = useState<DiagnosisFailureRoutesResponse | null>(null);
  const [diagnosisErrorGroupEvents, setDiagnosisErrorGroupEvents] = useState<DiagnosisErrorGroupEventsResponse | null>(null);
  const [recentJobFailures, setRecentJobFailures] = useState<RecentJobFailuresResponse | null>(null);
  const [alertSettings, setAlertSettings] = useState<AlertSettings | null>(null);
  const [apiKeys, setApiKeys] = useState<DashboardApiKeyItem[]>([]);
  const [lastIssuedApiKey, setLastIssuedApiKey] = useState<string | null>(null);
  const [alertDispatches, setAlertDispatches] = useState<AlertDispatchesResponse | null>(null);
  const [alertCapabilities, setAlertCapabilities] = useState<AlertChannelCapability[]>([]);
  const [onboardingStatus, setOnboardingStatus] = useState<DashboardOnboardingStatusResponse | null>(null);
  const [workspaceBootstrapError, setWorkspaceBootstrapError] = useState<string | null>(null);
  const [bootstrapRetryToken, setBootstrapRetryToken] = useState(0);
  const [retentionSettings, setRetentionSettings] = useState<RetentionSettings | null>(null);
  const [themePreference, setThemePreference] = useState<ThemePreference>(
    () => readStoredDashboardThemePreference() ?? "system",
  );
  const [excludeLumonoxTraffic, setExcludeLumonoxTraffic] = useState(true);
  const [errorGroupSort, setErrorGroupSort] = useState<"last_seen" | "count">("last_seen");
  const [loading, setLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [refreshToken, setRefreshToken] = useState(0);
  const liveRefreshPausedRef = useRef(false);
  const [liveDataPaused, setLiveDataPaused] = useState(false);
  const stretchAbsoluteEndAfterResumeRef = useRef(false);

  const {
    hasSession: hasDashboardSession,
    authSessionResolved,
    sessionEmail,
    membershipRole: sessionMembershipRole,
    sessionProjectId,
    sessionOrganizationId,
    sessionIssue: dashboardAuthSessionIssue,
    reloadSession: reloadDashboardAuthSession,
  } = useDashboardAuthSession();
  const [runbookMessage, setRunbookMessage] = useState<string | null>(null);
  const [alertSettingsMessage, setAlertSettingsMessage] = useState<string | null>(null);
  const [alertSettingsSaving, setAlertSettingsSaving] = useState(false);
  const [themeSettingsSaving, setThemeSettingsSaving] = useState(false);
  const [sqlFilterDraft, setSqlFilterDraft] = useState("");
  const [sqlFilterApplied, setSqlFilterApplied] = useState("");
  const [sqlFilterEnabled, setSqlFilterEnabled] = useState(false);
  const [sqlFilterValidation, setSqlFilterValidation] = useState<LogQueryValidationResponse | null>(null);
  const [sqlFilterValidating, setSqlFilterValidating] = useState(false);
  const [savedSqlFilterPresets, setSavedSqlFilterPresets] = useState<SavedSqlFilterPreset[]>([]);
  const [savedScopePresets, setSavedScopePresets] = useState<SavedScopePreset[]>([]);
  const runbookTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const liveFallbackRefreshTimer = useRef<ReturnType<typeof setInterval> | null>(null);
  const liveReconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const livePendingRefreshTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const liveSocketRef = useRef<WebSocket | null>(null);
  const liveLastRefreshAtRef = useRef(0);
  const liveWsBackoffUntilRef = useRef(0);
  const liveWsHandshakeFailuresRef = useRef(0);
  const hasLoadedDashboardData = useRef(false);
  const dashboardFetchRunId = useRef(0);
  const dashboardFetchInFlightRef = useRef(false);
  const dashboardQueuedRefreshRef = useRef(false);
  const [liveUpdatesConnected, setLiveUpdatesConnected] = useState(false);
  const rawDashboardPathname = usePathname();
  const dashboardRoutePath = useMemo(
    () => toDashboardRoutePath(rawDashboardPathname),
    [rawDashboardPathname],
  );

  const bumpDashboardDataRefresh = useCallback(() => {
    setRefreshToken((token) => token + 1);
  }, []);

  useEffect(() => {
    const scopedRoute =
      dashboardRoutePath === "/diagnosis" ||
      dashboardRoutePath === "/logs" ||
      dashboardRoutePath === "/requests" ||
      dashboardRoutePath === "/query-explorer";
    if (scopedRoute) {
      return;
    }
    if (!liveRefreshPausedRef.current) {
      return;
    }
    liveRefreshPausedRef.current = false;
    setLiveDataPaused(false);
  }, [dashboardRoutePath]);

  const [expandedRequestIds, setExpandedRequestIds] = useState<Set<string>>(() => new Set());
  /** Same as `expandedRequestIds` for synchronous reads inside toggle (before next paint). */
  const expandedRequestIdsRef = useRef<Set<string>>(new Set());
  useLayoutEffect(() => {
    expandedRequestIdsRef.current = expandedRequestIds;
  }, [expandedRequestIds]);
  /** Snapshot of request_id values from the last `requests` payload; used to prune stale row expansion only. */
  const prevVisibleRequestIdSetRef = useRef<Set<string>>(new Set());
  const hasHydratedPersistedScope = useRef(false);
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

  const effectiveScopeFromTs = useMemo(
    () => toIsoWindow?.from ?? overview?.from_timestamp ?? requests?.from_timestamp ?? "",
    [toIsoWindow?.from, overview?.from_timestamp, requests?.from_timestamp],
  );
  const effectiveScopeToTs = useMemo(
    () => toIsoWindow?.to ?? overview?.to_timestamp ?? requests?.to_timestamp ?? "",
    [toIsoWindow?.to, overview?.to_timestamp, requests?.to_timestamp],
  );

  useEffect(() => {
    if (!hasHydratedPersistedScope.current) {
      return;
    }
    if (
      dashboardRoutePath !== "/diagnosis" &&
      dashboardRoutePath !== "/logs" &&
      dashboardRoutePath !== "/requests" &&
      dashboardRoutePath !== "/query-explorer"
    ) {
      return;
    }
    const scopedForPersist: DashboardScopedQueryState = {
      isAbsoluteWindow: absoluteWindow !== null,
      windowMinutes,
      windowFromTimestamp: absoluteWindow?.from ?? "",
      windowToTimestamp: absoluteWindow?.to ?? "",
      method,
      statusClass,
      minLatencyMs,
      maxLatencyMs,
      pathQuery,
      serverEnvironmentQuery,
      serverServiceQuery,
      requestLimit,
      requestPage,
      errorGroupLimit,
      errorGroupPage,
      errorGroupSort,
      sqlFilterApplied,
      sqlFilterEnabled,
    };
    const timer = window.setTimeout(() => {
      const persistenceRoute =
        dashboardRoutePath === "/requests" || dashboardRoutePath === "/query-explorer"
          ? "/logs"
          : dashboardRoutePath;
      mergePersistedScopedSession(persistenceRoute, scopedForPersist, {
        groupBy,
        sortKey,
        sortDir,
        envTags: [...envTags],
        serviceTags: [...serviceTags],
      });
    }, 350);
    return () => window.clearTimeout(timer);
  }, [
    hasDashboardSession,
    dashboardRoutePath,
    absoluteWindow,
    windowMinutes,
    method,
    statusClass,
    minLatencyMs,
    maxLatencyMs,
    pathQuery,
    serverEnvironmentQuery,
    serverServiceQuery,
    requestLimit,
    requestPage,
    errorGroupLimit,
    errorGroupPage,
    errorGroupSort,
    sqlFilterApplied,
    sqlFilterEnabled,
    groupBy,
    sortKey,
    sortDir,
    envTags,
    serviceTags,
  ]);

  const retryWorkspaceBootstrap = useCallback(() => {
    setWorkspaceBootstrapError(null);
    setOnboardingStatus(null);
    setBootstrapRetryToken((t) => t + 1);
  }, []);

  // Keep settings and capabilities in sync with the same refresh cadence as traffic data.
  useEffect(() => {
    if (!hasDashboardSession) {
      return;
    }
    let cancelled = false;
    const controller = new AbortController();
    const run = async () => {
      try {
        const bootstrapData = await loadDashboardBootstrap(controller.signal, reloadDashboardAuthSession);

        if (cancelled) {
          return;
        }
        setWorkspaceBootstrapError(null);
        setRetentionSettings(bootstrapData.retention_settings);
        setAlertSettings(bootstrapData.alert_settings);
        setThemePreference(bootstrapData.theme_settings.theme_preference);
        writeStoredDashboardThemePreference(bootstrapData.theme_settings.theme_preference);
        setExcludeLumonoxTraffic(bootstrapData.theme_settings.exclude_lumonox_traffic);
        setApiKeys(bootstrapData.api_keys.items ?? []);
        setAlertCapabilities(bootstrapData.alert_capabilities.channels ?? []);
        setOnboardingStatus(bootstrapData.onboarding_status);
      } catch (error) {
        if (cancelled || (error instanceof DOMException && error.name === "AbortError")) {
          return;
        }
        setOnboardingStatus(createBootstrapFailureOnboardingFallback());
        setWorkspaceBootstrapError(buildDashboardNetworkError(error));
      }
    };

    void run();
    return () => {
      cancelled = true;
      controller.abort();
    };
  }, [hasDashboardSession, reloadDashboardAuthSession, bootstrapRetryToken, sessionProjectId]);

  useEffect(() => {
    if (!hasDashboardSession) {
      return;
    }
    const controller = new AbortController();
    const runId = ++dashboardFetchRunId.current;
    const isCancelled = () => controller.signal.aborted || runId !== dashboardFetchRunId.current;

    const run = async () => {
      const fetchStartedAt = Date.now();
      const routePath = dashboardRoutePath;
      if (routePath === "/settings") {
        return;
      }

      const isDocumentVisible =
        typeof document === "undefined" || document.visibilityState === "visible";
      const hasAdvancedScopeFilters =
        method !== "ALL" ||
        statusClass !== "ALL" ||
        minLatencyMs.trim() !== "" ||
        maxLatencyMs.trim() !== "" ||
        pathQuery.trim() !== "" ||
        normalizeCommaSeparated(serverEnvironmentQuery) !== "" ||
        normalizeCommaSeparated(serverServiceQuery) !== "" ||
        (sqlFilterEnabled && sqlFilterApplied.trim() !== "");
      const plan = planDashboardBatchQueryForRoute({
        routePath,
        isDocumentVisible,
        hasAdvancedScopeFilters,
        requestLimit,
        requestPage,
        errorGroupLimit,
        errorGroupPage,
      });
      const {
        includeExtended,
        includeWidgets,
        includeErrorGroups,
        includeDiagnosis,
        includeRecentJobFailures,
        includeAlertDispatches,
        useSnapshot,
        requestsLimitForRoute,
        requestsOffsetForRoute,
        errorGroupsLimitForRoute,
        errorGroupsOffsetForRoute,
      } = plan;

      const isInitialLoad = !hasLoadedDashboardData.current;
      if (isInitialLoad) {
        setLoading(true);
      }
      dashboardFetchInFlightRef.current = true;
      setErrorMessage(null);
      try {
        const serverPath = pathQuery.trim();
        const envCsv = normalizeCommaSeparated(serverEnvironmentQuery);
        const serviceCsv = normalizeCommaSeparated(serverServiceQuery);
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
          requestLimit: requestsLimitForRoute,
          requestPage: requestsOffsetForRoute === 0 ? 0 : requestPage,
          errorGroupLimit: errorGroupsLimitForRoute,
          errorGroupPage: errorGroupsOffsetForRoute === 0 ? 0 : errorGroupPage,
          errorGroupSort,
          sqlFilterEnabled,
          sqlFilterApplied,
        });
        const cached = useSnapshot ? readDashboardSnapshot(scopeKey) : null;
        if (cached) {
          setOverview(cached.overview);
          setOverviewExtended(cached.overviewExtended ?? null);
          setRequests(cached.requests);
          setErrorGroups(cached.errorGroups ?? null);
          setDiagnosisTimeline(cached.diagnosisTimeline ?? null);
          setDiagnosisFailures(cached.diagnosisFailures ?? null);
          setAlertDispatches(cached.alertDispatches ?? null);
          setRecentJobFailures(cached.recentJobFailures ?? null);
        }

        const scopeRequest: DashboardDataQueryRequest = buildDashboardDataQueryRequest({
          plan,
          toIsoWindow,
          windowMinutes,
          method,
          statusClass,
          minLatencyMs,
          maxLatencyMs,
          pathQuery,
          serverEnvironmentQuery,
          serverServiceQuery,
          sqlFilterEnabled,
          sqlFilterApplied,
        });
        const queryBody = await buildOptionalGzipJsonRequest(scopeRequest);
        const batchResponse = await dashboardSessionFetch(
          "/dashboard/query",
          {
            method: "POST",
            headers: queryBody.headers,
            body: queryBody.body,
          },
          controller.signal,
        );
        if (batchResponse.status === 401) {
          reloadDashboardAuthSession();
        }
        const elapsedMs = Date.now() - fetchStartedAt;
        if (!isCancelled()) {
          const status = batchResponse.status;
          if (
            elapsedMs >= LIVE_FETCH_SLOW_MS ||
            status === 429 ||
            status === 503 ||
            status >= 500
          ) {
            liveWsBackoffUntilRef.current = Date.now() + LIVE_REFRESH_BACKOFF_DURATION_MS;
          }
        }
        const results: DashboardFetchResult[] = [{ endpoint: "overview", response: batchResponse }];
        if (isCancelled()) {
          return;
        }

        const fetchError = buildDashboardFetchError(results);
        if (fetchError) {
          setErrorMessage(fetchError);
        }

        let data: DashboardDataQueryResponse | null = null;
        if (batchResponse.ok) {
          const rawQuery: unknown = await batchResponse.json();
          data = parseDashboardDataQueryResponse(rawQuery);
          if (!data) {
            if (!isCancelled()) {
              setErrorMessage("Dashboard query returned an unexpected response. Refresh to retry.");
            }
            return;
          }
        }
        if (isCancelled() || !data) {
          return;
        }
        const overviewData = data.overview;
        const requestsData = data.requests;
        if (overviewData) {
          setOverview(overviewData);
        }
        if (requestsData) {
          setRequests(requestsData);
        }

        if (includeExtended && data.overview_extended) {
          setOverviewExtended(data.overview_extended);
        } else if (routePath !== "/dashboard") {
          setOverviewExtended(null);
        }
        if (includeWidgets && data.widgets) {
          setDashboardWidgets(trimDashboardWidgetPayload(data.widgets));
        } else if (routePath !== "/dashboard") {
          setDashboardWidgets(null);
        }
        if (includeErrorGroups && data.error_groups) {
          setErrorGroups(data.error_groups);
        } else {
          setErrorGroups(null);
        }
        if (includeDiagnosis && data.diagnosis_timeline && data.diagnosis_failures) {
          setDiagnosisTimeline(data.diagnosis_timeline);
          setDiagnosisFailures(data.diagnosis_failures);
        } else {
          setDiagnosisTimeline(null);
          setDiagnosisFailures(null);
        }
        if (includeAlertDispatches && data.alert_dispatches) {
          setAlertDispatches(data.alert_dispatches);
        } else {
          setAlertDispatches(null);
        }
        setDiagnosisErrorGroupEvents(data.diagnosis_error_group_events ?? null);
        if (includeRecentJobFailures && data.recent_job_failures) {
          setRecentJobFailures(data.recent_job_failures);
        } else {
          setRecentJobFailures(null);
        }

        if (
          useSnapshot &&
          includeExtended &&
          overviewData &&
          requestsData &&
          data.overview_extended
        ) {
          writeDashboardSnapshot(scopeKey, {
            overview: overviewData,
            overviewExtended: data.overview_extended,
            requests: requestsData,
            errorGroups: data.error_groups ?? undefined,
            recentJobFailures: includeRecentJobFailures ? data.recent_job_failures ?? undefined : undefined,
          });
        }
        if (overviewData || requestsData) {
          hasLoadedDashboardData.current = true;
        }

        if (stretchAbsoluteEndAfterResumeRef.current) {
          const aw = absoluteWindow;
          if (!aw) {
            stretchAbsoluteEndAfterResumeRef.current = false;
          } else {
            const serverNowForStretch =
              overviewData?.server_now ??
              requestsData?.server_now ??
              data.error_groups?.server_now ??
              null;
            if (serverNowForStretch) {
              const fromMs = new Date(aw.from).getTime();
              const prevToMs = new Date(aw.to).getTime();
              const nowMs = new Date(serverNowForStretch).getTime();
              if (
                Number.isFinite(fromMs) &&
                Number.isFinite(prevToMs) &&
                Number.isFinite(nowMs) &&
                fromMs < prevToMs &&
                nowMs > prevToMs
              ) {
                // Extend window end only (do not reset request/error pages like setAbsoluteWindow does).
                setAbsoluteWindowState({ from: aw.from, to: new Date(nowMs).toISOString() });
              }
              stretchAbsoluteEndAfterResumeRef.current = false;
            } else if (overviewData || requestsData || data.error_groups) {
              stretchAbsoluteEndAfterResumeRef.current = false;
            }
          }
        }
      } catch (error) {
        if (error instanceof DOMException && error.name === "AbortError") {
          if (
            !isCancelled() &&
            error.message === "Dashboard request timed out"
          ) {
            liveWsBackoffUntilRef.current = Date.now() + LIVE_REFRESH_BACKOFF_DURATION_MS;
          }
          return;
        }
        if (!hasLoadedDashboardData.current) {
          setErrorMessage(buildDashboardNetworkError(error));
        }
      } finally {
        dashboardFetchInFlightRef.current = false;
        if (!isCancelled() && dashboardQueuedRefreshRef.current) {
          dashboardQueuedRefreshRef.current = false;
          if (!liveRefreshPausedRef.current) {
            setRefreshToken((token) => token + 1);
          }
        }
        if (isInitialLoad && !isCancelled()) {
          setLoading(false);
        }
      }
    };

    void run();
    return () => {
      controller.abort();
    };
  }, [
    hasDashboardSession,
    dashboardRoutePath,
    method,
    statusClass,
    absoluteWindow,
    toIsoWindow,
    windowMinutes,
    refreshToken,
    requestLimit,
    requestPage,
    errorGroupLimit,
    errorGroupPage,
    errorGroupSort,
    minLatencyMs,
    maxLatencyMs,
    pathQuery,
    serverEnvironmentQuery,
    serverServiceQuery,
    sqlFilterEnabled,
    sqlFilterApplied,
    reloadDashboardAuthSession,
    sessionProjectId,
  ]);

  useEffect(() => {
    return () => {
      if (runbookTimer.current) {
        clearTimeout(runbookTimer.current);
      }
      const reconnectTimer = liveReconnectTimer.current;
      if (reconnectTimer) {
        clearTimeout(reconnectTimer);
        liveReconnectTimer.current = null;
      }
      const pendingTimer = livePendingRefreshTimer.current;
      if (pendingTimer) {
        clearTimeout(pendingTimer);
        livePendingRefreshTimer.current = null;
      }
      if (liveSocketRef.current) {
        liveSocketRef.current.close();
        liveSocketRef.current = null;
      }
      const fallbackTimer = liveFallbackRefreshTimer.current;
      if (fallbackTimer) {
        clearInterval(fallbackTimer);
        liveFallbackRefreshTimer.current = null;
      }
    };
  }, []);

  useDashboardLiveWebSocket({
    hasSession: hasDashboardSession,
    authSessionResolved,
    sessionProjectId,
    reloadDashboardAuthSession,
    setLiveUpdatesConnected,
    liveWsBackoffUntilRef,
    liveRefreshPausedRef,
    dashboardFetchInFlightRef,
    dashboardQueuedRefreshRef,
    liveLastRefreshAtRef,
    livePendingRefreshTimerRef: livePendingRefreshTimer,
    liveReconnectTimerRef: liveReconnectTimer,
    liveSocketRef,
    liveWsHandshakeFailuresRef,
    bumpRefresh: bumpDashboardDataRefresh,
  });

  useDashboardWsDisconnectedFallbackPoll({
    hasSession: hasDashboardSession,
    liveUpdatesConnected,
    liveRefreshPausedRef,
    dashboardFetchInFlightRef,
    dashboardQueuedRefreshRef,
    bumpRefresh: bumpDashboardDataRefresh,
    liveFallbackRefreshTimerRef: liveFallbackRefreshTimer,
  });

  useDashboardVisibilityRefreshBump({
    hasSession: hasDashboardSession,
    liveRefreshPausedRef,
    dashboardFetchInFlightRef,
    dashboardQueuedRefreshRef,
    bumpRefresh: bumpDashboardDataRefresh,
  });

  const rawItems = useMemo(
    () =>
      (requests?.items ?? []).map((item) => ({
        ...item,
        log_message: item.log_message ?? null,
      })),
    [requests],
  );

  const onServerWindowChange = useCallback((minutes: number) => {
    const viewportY = typeof window !== "undefined" ? window.scrollY : 0;
    const anchorEl =
      typeof document !== "undefined" ? document.querySelector("[data-ap-dashboard-scope-anchor]") : null;
    const anchorTopBefore =
      anchorEl instanceof Element ? anchorEl.getBoundingClientRect().top : null;
    pinDashboardViewportScroll(viewportY);
    setAbsoluteWindowState(null);
    setWindowMinutes(minutes);
    setRequestPage(0);
    setErrorGroupPage(0);
    scheduleDashboardViewportScrollRestore(viewportY);
    if (anchorTopBefore != null) {
      scheduleDashboardScopeAnchorRepair(anchorTopBefore);
    }
  }, []);
  const setAbsoluteWindow = useCallback((fromIso: string, toIso: string, scrollYHint?: number) => {
    const viewportY =
      scrollYHint ?? (typeof window !== "undefined" ? window.scrollY : 0);
    const fromMs = new Date(fromIso).getTime();
    const toMs = new Date(toIso).getTime();
    if (!Number.isFinite(fromMs) || !Number.isFinite(toMs) || fromMs >= toMs) {
      return;
    }
    pinDashboardViewportScroll(viewportY);
    setAbsoluteWindowState({ from: new Date(fromMs).toISOString(), to: new Date(toMs).toISOString() });
    setRequestPage(0);
    setErrorGroupPage(0);
    scheduleDashboardViewportScrollRestore(viewportY);
  }, []);

  /** Pause live refresh and freeze the current scope; preserves scroll when the table remounts on page 0. */
  const pauseLiveAtCurrentScope = useCallback(
    (scrollYHint?: number) => {
      if (liveRefreshPausedRef.current) {
        return;
      }
      liveRefreshPausedRef.current = true;
      setLiveDataPaused(true);
      const fromTs = effectiveScopeFromTs;
      const toTs = effectiveScopeToTs;
      const fromMs = new Date(fromTs).getTime();
      const toMs = new Date(toTs).getTime();
      if (!Number.isFinite(fromMs) || !Number.isFinite(toMs) || fromMs >= toMs) {
        return;
      }
      setAbsoluteWindow(fromTs, toTs, scrollYHint);
    },
    [effectiveScopeFromTs, effectiveScopeToTs, setAbsoluteWindow],
  );

  const clearAbsoluteWindow = useCallback(() => {
    const viewportY = typeof window !== "undefined" ? window.scrollY : 0;
    pinDashboardViewportScroll(viewportY);
    setAbsoluteWindowState(null);
    setRequestPage(0);
    setErrorGroupPage(0);
    if (liveRefreshPausedRef.current) {
      liveRefreshPausedRef.current = false;
      setLiveDataPaused(false);
      stretchAbsoluteEndAfterResumeRef.current = true;
      setRefreshToken((t) => t + 1);
    }
    scheduleDashboardViewportScrollRestore(viewportY);
  }, []);

  const toggleLiveDataPaused = useCallback(() => {
    const nextPaused = !liveRefreshPausedRef.current;
    if (nextPaused) {
      const viewportY = typeof window !== "undefined" ? window.scrollY : 0;
      pauseLiveAtCurrentScope(viewportY);
    } else {
      liveRefreshPausedRef.current = false;
      setLiveDataPaused(false);
      stretchAbsoluteEndAfterResumeRef.current = true;
      setRefreshToken((t) => t + 1);
    }
  }, [pauseLiveAtCurrentScope]);

  const onServerMethodChange = useCallback((value: string) => {
    const viewportY = typeof window !== "undefined" ? window.scrollY : 0;
    pinDashboardViewportScroll(viewportY);
    setMethod(value);
    setRequestPage(0);
    setErrorGroupPage(0);
    scheduleDashboardViewportScrollRestore(viewportY);
  }, []);

  const onServerStatusClassChange = useCallback((value: string) => {
    const viewportY = typeof window !== "undefined" ? window.scrollY : 0;
    pinDashboardViewportScroll(viewportY);
    setStatusClass(value);
    setRequestPage(0);
    setErrorGroupPage(0);
    scheduleDashboardViewportScrollRestore(viewportY);
  }, []);

  useLayoutEffect(() => {
    if (hasHydratedPersistedScope.current) {
      return;
    }
    const parsed = readPersistedDashboardSession();
    if (!parsed) {
      hasHydratedPersistedScope.current = true;
      return;
    }
    const path = toDashboardRoutePath(window.location.pathname);
    const scoped: DashboardScopedQueryState | null =
      path === "/logs" || path === "/requests" || path === "/query-explorer"
        ? parsed.logsScoped
        : path === "/diagnosis"
          ? parsed.diagnosisScoped
          : null;
    if (scoped) {
      applyDashboardScopedQueryState(
        {
          setAbsoluteWindow,
          clearAbsoluteWindow,
          onServerWindowChange,
          onServerMethodChange,
          onServerStatusClassChange,
          setPathQuery,
          setMinLatencyMs,
          setMaxLatencyMs,
          setServerEnvironmentQuery,
          setServerServiceQuery,
          setRequestLimit,
          setRequestPage,
          setErrorGroupLimit,
          setErrorGroupPage,
          setErrorGroupSort,
          setSqlFilterApplied,
          setSqlFilterDraft,
          setSqlFilterEnabled,
        },
        scoped,
      );
    }
    const { logsClient } = parsed;
    queueMicrotask(() => {
      setGroupBy(logsClient.groupBy);
      setSortKey(logsClient.sortKey);
      setSortDir(logsClient.sortDir);
      setEnvTags(new Set(logsClient.envTags));
      setServiceTags(new Set(logsClient.serviceTags));
    });
    hasHydratedPersistedScope.current = true;
    // eslint-disable-next-line react-hooks/exhaustive-deps -- one-time hydration; setters stable
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
    const viewportY = typeof window !== "undefined" ? window.scrollY : 0;
    pinDashboardViewportScroll(viewportY);
    setServerEnvironmentQuery(normalizeCommaSeparated(tags.join(",")));
    setRequestPage(0);
    setErrorGroupPage(0);
    scheduleDashboardViewportScrollRestore(viewportY);
  }, []);

  const setServerServiceTags = useCallback((tags: string[]) => {
    const viewportY = typeof window !== "undefined" ? window.scrollY : 0;
    pinDashboardViewportScroll(viewportY);
    setServerServiceQuery(normalizeCommaSeparated(tags.join(",")));
    setRequestPage(0);
    setErrorGroupPage(0);
    scheduleDashboardViewportScrollRestore(viewportY);
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

  const hydrateLogsViewFromUrl = useCallback((next: PersistedLogsClientSlice) => {
    setGroupBy(next.groupBy);
    setSortKey(next.sortKey);
    setSortDir(next.sortDir);
    setEnvTags(new Set(next.envTags));
    setServiceTags(new Set(next.serviceTags));
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
      if (!hasDashboardSession) {
        return false;
      }
      setAlertSettingsSaving(true);
      setAlertSettingsMessage(null);
      try {
        const response = await dashboardSessionJsonPut("/dashboard/alert-settings", next);
        if (!response.ok) {
          throw new Error(`alert-settings update failed (${response.status})`);
        }
        const raw: unknown = await response.json();
        const updated = parseAlertSettings(raw);
        if (!updated) {
          throw new Error("alert-settings: invalid response shape");
        }
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
    [hasDashboardSession],
  );

  const updateAlertSettingsDraft = useCallback((next: AlertSettings) => {
    setAlertSettings(next);
  }, []);

  const saveThemePreference = useCallback(
    async (next: ThemePreference): Promise<boolean> => {
      if (!hasDashboardSession) {
        return false;
      }
      setThemeSettingsSaving(true);
      try {
        const response = await dashboardSessionJsonPut("/dashboard/theme-settings", {
          theme_preference: next,
          exclude_lumonox_traffic: excludeLumonoxTraffic,
        });
        if (!response.ok) {
          throw new Error(`theme-settings update failed (${response.status})`);
        }
        const raw: unknown = await response.json();
        const updated = parseThemeSettings(raw);
        if (!updated) {
          throw new Error("theme-settings: invalid response shape");
        }
        setThemePreference(updated.theme_preference);
        writeStoredDashboardThemePreference(updated.theme_preference);
        setExcludeLumonoxTraffic(updated.exclude_lumonox_traffic);
        return true;
      } catch {
        return false;
      } finally {
        setThemeSettingsSaving(false);
      }
    },
    [excludeLumonoxTraffic, hasDashboardSession],
  );

  const saveExcludeLumonoxTraffic = useCallback(
    async (next: boolean): Promise<boolean> => {
      if (!hasDashboardSession) {
        return false;
      }
      setThemeSettingsSaving(true);
      try {
        const response = await dashboardSessionJsonPut("/dashboard/theme-settings", {
          theme_preference: themePreference,
          exclude_lumonox_traffic: next,
        });
        if (!response.ok) {
          throw new Error(`theme-settings update failed (${response.status})`);
        }
        const raw: unknown = await response.json();
        const updated = parseThemeSettings(raw);
        if (!updated) {
          throw new Error("theme-settings: invalid response shape");
        }
        setThemePreference(updated.theme_preference);
        writeStoredDashboardThemePreference(updated.theme_preference);
        setExcludeLumonoxTraffic(updated.exclude_lumonox_traffic);
        setRefreshToken((n) => n + 1);
        return true;
      } catch {
        return false;
      } finally {
        setThemeSettingsSaving(false);
      }
    },
    [hasDashboardSession, themePreference],
  );

  const saveRetentionSettings = useCallback(
    async (next: RetentionSettings): Promise<boolean> => {
      if (!hasDashboardSession) {
        return false;
      }
      try {
        const response = await dashboardSessionJsonPut("/dashboard/retention-settings", {
          raw_events_days: next.raw_events_days,
          logs_query_max_window_minutes: next.logs_query_max_window_minutes,
          retention_max_db_size_mb: next.retention_max_db_size_mb,
          retention_max_log_rows: next.retention_max_log_rows,
          retention_plan: next.retention_plan,
          archival_enabled: next.archival_enabled,
          archival_mode: next.archival_mode,
        });
        if (!response.ok) {
          throw new Error(`retention-settings update failed (${response.status})`);
        }
        const raw: unknown = await response.json();
        const updated = parseRetentionSettings(raw);
        if (!updated) {
          throw new Error("retention-settings: invalid response shape");
        }
        setRetentionSettings(updated);
        return true;
      } catch {
        return false;
      }
    },
    [hasDashboardSession],
  );

  const refreshApiKeys = useCallback(async (): Promise<void> => {
    if (!hasDashboardSession) {
      setApiKeys([]);
      return;
    }
    const response = await dashboardSessionFetch("/dashboard/auth/api-keys");
    if (!response.ok) {
      return;
    }
    const raw: unknown = await response.json();
    const payload = parseDashboardApiKeyListResponse(raw);
    if (payload) {
      setApiKeys(payload.items ?? []);
    }
  }, [hasDashboardSession]);

  const setActiveDashboardProject = useCallback(
    async (projectId: string): Promise<boolean> => {
      if (!hasDashboardSession) {
        return false;
      }
      const response = await dashboardSessionJsonPost("/dashboard/auth/active-project", {
        project_id: projectId,
      });
      if (!response.ok) {
        return false;
      }
      reloadDashboardAuthSession();
      setWorkspaceBootstrapError(null);
      setBootstrapRetryToken((t) => t + 1);
      setRefreshToken((n) => n + 1);
      return true;
    },
    [hasDashboardSession, reloadDashboardAuthSession],
  );

  const issueApiKey = useCallback(async (): Promise<boolean> => {
    if (!hasDashboardSession) {
      return false;
    }
    const response = await dashboardSessionFetch("/dashboard/auth/api-keys/issue", { method: "POST" });
    if (!response.ok) {
      return false;
    }
    const raw: unknown = await response.json();
    const payload = parseDashboardApiKeyIssueResponse(raw);
    if (!payload) {
      return false;
    }
    setLastIssuedApiKey(payload.api_key);
    await refreshApiKeys();
    return true;
  }, [hasDashboardSession, refreshApiKeys]);

  const completeOnboarding = useCallback(async (): Promise<boolean> => {
    if (!hasDashboardSession) {
      return false;
    }
    const response = await dashboardSessionFetch("/dashboard/auth/onboarding-complete", { method: "POST" });
    if (!response.ok) {
      return false;
    }
    const raw: unknown = await response.json();
    const payload = parseDashboardOnboardingStatusResponse(raw);
    if (!payload) {
      return false;
    }
    setOnboardingStatus(payload);
    return true;
  }, [hasDashboardSession]);

  const rotateApiKey = useCallback(
    async (keyId: string): Promise<boolean> => {
      if (!hasDashboardSession) {
        return false;
      }
      const response = await dashboardSessionJsonPost("/dashboard/auth/api-keys/rotate", { key_id: keyId });
      if (!response.ok) {
        return false;
      }
      const raw: unknown = await response.json();
      const payload = parseDashboardApiKeyRotateResponse(raw);
      if (!payload) {
        return false;
      }
      setLastIssuedApiKey(payload.replacement_api_key);
      await refreshApiKeys();
      return true;
    },
    [hasDashboardSession, refreshApiKeys],
  );

  const revokeApiKey = useCallback(
    async (keyId: string): Promise<boolean> => {
      if (!hasDashboardSession) {
        return false;
      }
      const response = await dashboardSessionJsonPost("/dashboard/auth/api-keys/revoke", { key_id: keyId });
      if (!response.ok) {
        return false;
      }
      await refreshApiKeys();
      return true;
    },
    [hasDashboardSession, refreshApiKeys],
  );

  const signOutDashboard = useCallback(async (): Promise<void> => {
    try {
      await dashboardSessionFetch("/dashboard/auth/logout", { method: "POST" });
    } catch {
      /* ignore */
    } finally {
      await reloadDashboardAuthSession();
      if (typeof window !== "undefined") {
        window.location.assign(dashboardMagicLinkHref());
      }
    }
  }, [reloadDashboardAuthSession]);

  const sqlFilterStorageKey = useMemo(
    () => `lumonox.sql-filter-presets.${(sessionEmail ?? "anonymous").toLowerCase()}`,
    [sessionEmail],
  );
  const scopePresetStorageKey = useMemo(
    () =>
      `lumonox.scope-presets.${(sessionProjectId ?? "no-project").toLowerCase()}.${(sessionEmail ?? "anonymous").toLowerCase()}`,
    [sessionProjectId, sessionEmail],
  );

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    try {
      const raw = window.localStorage.getItem(sqlFilterStorageKey);
      if (!raw) {
        queueMicrotask(() => {
          setSavedSqlFilterPresets([]);
        });
        return;
      }
      const parsed = JSON.parse(raw) as unknown;
      if (!Array.isArray(parsed)) {
        queueMicrotask(() => {
          setSavedSqlFilterPresets([]);
        });
        return;
      }
      const normalized: SavedSqlFilterPreset[] = parsed
        .map((entry) => {
          if (!entry || typeof entry !== "object") {
            return null;
          }
          const obj = entry as Record<string, unknown>;
          if (
            typeof obj.id !== "string" ||
            typeof obj.name !== "string" ||
            typeof obj.where !== "string" ||
            typeof obj.createdAt !== "string" ||
            typeof obj.updatedAt !== "string"
          ) {
            return null;
          }
          return {
            id: obj.id,
            name: obj.name,
            where: obj.where,
            createdAt: obj.createdAt,
            updatedAt: obj.updatedAt,
          };
        })
        .filter((item): item is SavedSqlFilterPreset => item !== null);
      queueMicrotask(() => {
        setSavedSqlFilterPresets(normalized);
      });
    } catch {
      queueMicrotask(() => {
        setSavedSqlFilterPresets([]);
      });
    }
  }, [sqlFilterStorageKey]);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    try {
      window.localStorage.setItem(sqlFilterStorageKey, JSON.stringify(savedSqlFilterPresets));
    } catch {
      // ignore quota/private mode
    }
  }, [savedSqlFilterPresets, sqlFilterStorageKey]);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    try {
      const raw = window.localStorage.getItem(scopePresetStorageKey);
      if (!raw) {
        queueMicrotask(() => {
          setSavedScopePresets([]);
        });
        return;
      }
      const parsed = JSON.parse(raw) as unknown;
      if (!Array.isArray(parsed)) {
        queueMicrotask(() => {
          setSavedScopePresets([]);
        });
        return;
      }
      const normalized: SavedScopePreset[] = parsed
        .map((entry) => {
          if (!entry || typeof entry !== "object") {
            return null;
          }
          const obj = entry as Record<string, unknown>;
          if (
            typeof obj.id !== "string" ||
            typeof obj.name !== "string" ||
            typeof obj.createdAt !== "string" ||
            typeof obj.updatedAt !== "string" ||
            !obj.scope ||
            typeof obj.scope !== "object"
          ) {
            return null;
          }
          const scope = obj.scope as Record<string, unknown>;
          const windowMinutes = Math.max(1, coerceScopeNumber(scope.windowMinutes, 60));
          const requestLimitRaw = coerceScopeNumber(scope.requestLimit, 100);
          const requestLimit = REQUEST_LIMIT_OPTIONS.includes(
            requestLimitRaw as (typeof REQUEST_LIMIT_OPTIONS)[number],
          )
            ? requestLimitRaw
            : 100;
          const errorGroupLimitRaw = coerceScopeNumber(scope.errorGroupLimit, 25);
          const errorGroupLimit = ERROR_GROUP_LIMIT_OPTIONS.includes(
            errorGroupLimitRaw as (typeof ERROR_GROUP_LIMIT_OPTIONS)[number],
          )
            ? errorGroupLimitRaw
            : 25;
          const method =
            typeof scope.method === "string" && (METHOD_OPTIONS as readonly string[]).includes(scope.method)
              ? scope.method
              : "ALL";
          const statusClass =
            typeof scope.statusClass === "string" &&
            (STATUS_CLASS_OPTIONS as readonly string[]).includes(scope.statusClass)
              ? scope.statusClass
              : "ALL";
          const errorGroupSort = scope.errorGroupSort === "count" ? "count" : "last_seen";
          return {
            id: obj.id,
            name: obj.name,
            createdAt: obj.createdAt,
            updatedAt: obj.updatedAt,
            scope: {
              isAbsoluteWindow: Boolean(scope.isAbsoluteWindow),
              windowMinutes,
              windowFromTimestamp: typeof scope.windowFromTimestamp === "string" ? scope.windowFromTimestamp : "",
              windowToTimestamp: typeof scope.windowToTimestamp === "string" ? scope.windowToTimestamp : "",
              method,
              statusClass,
              minLatencyMs: typeof scope.minLatencyMs === "string" ? scope.minLatencyMs : "",
              maxLatencyMs: typeof scope.maxLatencyMs === "string" ? scope.maxLatencyMs : "",
              pathQuery: typeof scope.pathQuery === "string" ? scope.pathQuery : "",
              serverEnvironmentQuery:
                typeof scope.serverEnvironmentQuery === "string" ? scope.serverEnvironmentQuery : "",
              serverServiceQuery: typeof scope.serverServiceQuery === "string" ? scope.serverServiceQuery : "",
              requestLimit,
              errorGroupLimit,
              errorGroupSort,
              sqlFilterApplied: typeof scope.sqlFilterApplied === "string" ? scope.sqlFilterApplied : "",
              sqlFilterEnabled: Boolean(scope.sqlFilterEnabled),
            },
          };
        })
        .filter((item): item is SavedScopePreset => item !== null);
      queueMicrotask(() => {
        setSavedScopePresets(normalized);
      });
    } catch {
      queueMicrotask(() => {
        setSavedScopePresets([]);
      });
    }
  }, [scopePresetStorageKey]);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    try {
      window.localStorage.setItem(scopePresetStorageKey, JSON.stringify(savedScopePresets));
    } catch {
      // ignore quota/private mode
    }
  }, [savedScopePresets, scopePresetStorageKey]);

  const saveSqlFilterPreset = useCallback(
    (name: string, where: string): { ok: boolean; error?: string } => {
      const cleanName = name.trim();
      const cleanWhere = where.trim();
      if (!cleanName) {
        return { ok: false, error: "Preset name is required." };
      }
      if (!cleanWhere) {
        return { ok: false, error: "WHERE filter text is required." };
      }
      if (cleanName.length > 80) {
        return { ok: false, error: "Preset name must be 80 characters or less." };
      }
      setSavedSqlFilterPresets((prev) => {
        const existing = prev.find(
          (preset) => preset.name.toLowerCase() === cleanName.toLowerCase(),
        );
        const now = new Date().toISOString();
        if (existing) {
          return prev.map((preset) =>
            preset.id === existing.id
              ? { ...preset, where: cleanWhere, updatedAt: now, name: cleanName }
              : preset,
          );
        }
        const next: SavedSqlFilterPreset = {
          id:
            typeof crypto !== "undefined" && "randomUUID" in crypto
              ? crypto.randomUUID()
              : `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
          name: cleanName,
          where: cleanWhere,
          createdAt: now,
          updatedAt: now,
        };
        return [next, ...prev].slice(0, 100);
      });
      return { ok: true };
    },
    [],
  );

  const removeSqlFilterPreset = useCallback((id: string) => {
    setSavedSqlFilterPresets((prev) => prev.filter((preset) => preset.id !== id));
  }, []);

  const applySavedSqlFilterPreset = useCallback((id: string) => {
    const preset = savedSqlFilterPresets.find((candidate) => candidate.id === id);
    if (!preset) {
      return;
    }
    setSqlFilterDraft(preset.where);
    setSqlFilterApplied(preset.where);
    setSqlFilterEnabled(true);
    setRequestPage(0);
    setErrorGroupPage(0);
  }, [savedSqlFilterPresets]);

  const saveScopePreset = useCallback(
    (name: string, draft?: SavedScopePresetSaveDraft): { ok: boolean; error?: string } => {
      const cleanName = name.trim();
      if (!cleanName) {
        return { ok: false, error: "Saved view name is required." };
      }
      if (cleanName.length > 80) {
        return { ok: false, error: "Saved view name must be 80 characters or less." };
      }
      const now = new Date().toISOString();
      const draftFrom = draft?.windowFromTimestamp;
      const draftTo = draft?.windowToTimestamp;
      const draftAbs =
        Boolean(draft?.isAbsoluteWindow) &&
        typeof draftFrom === "string" &&
        typeof draftTo === "string" &&
        draftFrom.length > 0 &&
        draftTo.length > 0 &&
        new Date(draftFrom).getTime() < new Date(draftTo).getTime();
      const isAbs = draftAbs || Boolean(toIsoWindow);
      const fromTs = draftAbs ? draftFrom : toIsoWindow?.from ?? "";
      const toTs = draftAbs ? draftTo : toIsoWindow?.to ?? "";
      const scope: SavedScopePreset["scope"] = {
        isAbsoluteWindow: isAbs,
        windowMinutes: draft?.windowMinutes ?? windowMinutes,
        windowFromTimestamp: fromTs,
        windowToTimestamp: toTs,
        method: draft?.method ?? method,
        statusClass: draft?.statusClass ?? statusClass,
        minLatencyMs: draft?.minLatencyMs ?? minLatencyMs,
        maxLatencyMs: draft?.maxLatencyMs ?? maxLatencyMs,
        pathQuery: draft?.pathQuery ?? pathQuery,
        serverEnvironmentQuery: normalizeCommaSeparated(draft?.serverEnvironmentQuery ?? serverEnvironmentQuery),
        serverServiceQuery: normalizeCommaSeparated(draft?.serverServiceQuery ?? serverServiceQuery),
        requestLimit,
        errorGroupLimit,
        errorGroupSort: draft?.errorGroupSort ?? errorGroupSort,
        sqlFilterApplied,
        sqlFilterEnabled,
      };
      setSavedScopePresets((prev) => {
        const existing = prev.find((preset) => preset.name.toLowerCase() === cleanName.toLowerCase());
        if (existing) {
          return prev.map((preset) =>
            preset.id === existing.id
              ? { ...preset, name: cleanName, updatedAt: now, scope }
              : preset,
          );
        }
        const next: SavedScopePreset = {
          id:
            typeof crypto !== "undefined" && "randomUUID" in crypto
              ? crypto.randomUUID()
              : `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
          name: cleanName,
          scope,
          createdAt: now,
          updatedAt: now,
        };
        return [next, ...prev].slice(0, 100);
      });
      return { ok: true };
    },
    [
      toIsoWindow,
      windowMinutes,
      method,
      statusClass,
      minLatencyMs,
      maxLatencyMs,
      pathQuery,
      serverEnvironmentQuery,
      serverServiceQuery,
      requestLimit,
      errorGroupLimit,
      errorGroupSort,
      sqlFilterApplied,
      sqlFilterEnabled,
    ],
  );

  const removeScopePreset = useCallback((id: string) => {
    setSavedScopePresets((prev) => prev.filter((preset) => preset.id !== id));
  }, []);

  const applySavedScopePreset = useCallback(
    (id: string): { ok: boolean; error?: string } => {
      const preset = savedScopePresets.find((candidate) => candidate.id === id);
      if (!preset) {
        return { ok: false, error: "Saved view no longer exists." };
      }
      try {
        const parsed = savedPresetScopeToDashboardQuery(preset.scope);
        applyDashboardScopedQueryState(
          {
            setAbsoluteWindow,
            clearAbsoluteWindow,
            onServerWindowChange,
            onServerMethodChange,
            onServerStatusClassChange,
            setPathQuery,
            setMinLatencyMs,
            setMaxLatencyMs,
            setServerEnvironmentQuery,
            setServerServiceQuery,
            setRequestLimit,
            setRequestPage,
            setErrorGroupLimit,
            setErrorGroupPage,
            setErrorGroupSort,
            setSqlFilterApplied,
            setSqlFilterDraft,
            setSqlFilterEnabled,
          },
          parsed,
        );
        return { ok: true };
      } catch {
        return { ok: false, error: "Could not apply saved view." };
      }
    },
    [
      savedScopePresets,
      setAbsoluteWindow,
      clearAbsoluteWindow,
      onServerWindowChange,
      onServerMethodChange,
      onServerStatusClassChange,
      setPathQuery,
      setMinLatencyMs,
      setMaxLatencyMs,
      setServerEnvironmentQuery,
      setServerServiceQuery,
      setRequestLimit,
      setRequestPage,
      setErrorGroupLimit,
      setErrorGroupPage,
      setErrorGroupSort,
      setSqlFilterApplied,
      setSqlFilterDraft,
      setSqlFilterEnabled,
    ],
  );

  const validateSqlFilterDraft = useCallback(async (): Promise<LogQueryValidationResponse | null> => {
    if (!hasDashboardSession) {
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
      const response = await dashboardSessionJsonPost("/dashboard/log-query/validate", {
        query: wrapped,
        page_size: 100,
      });
      if (!response.ok) {
        const fallback: LogQueryValidationResponse = {
          valid: false,
          normalized_query: wrapped,
          error: `Validation failed (${response.status})`,
        };
        setSqlFilterValidation(fallback);
        return fallback;
      }
      const raw: unknown = await response.json();
      const parsed = parseLogQueryValidationResponse(raw);
      const payload: LogQueryValidationResponse =
        parsed ?? {
          valid: false,
          normalized_query: wrapped,
          error: "Invalid validation response",
        };
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
  }, [hasDashboardSession, sqlFilterDraft]);

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

  const toggleRequestRow = useCallback(
    (id: string) => {
      const wasExpanded = expandedRequestIdsRef.current.has(id);
      const scrollY = typeof window !== "undefined" ? window.scrollY : 0;
      setExpandedRequestIds((prev) => {
        const next = new Set(prev);
        if (next.has(id)) {
          next.delete(id);
        } else {
          next.add(id);
        }
        return next;
      });
      if (!wasExpanded) {
        queueMicrotask(() => pauseLiveAtCurrentScope(scrollY));
      }
    },
    [pauseLiveAtCurrentScope],
  );

  useEffect(() => {
    const visibleRequestIds = new Set(
      (requests?.items ?? [])
        .map((item) => item.request_id)
        .filter((id): id is string => typeof id === "string" && id.length > 0),
    );
    const prevVisibleRequestIds = prevVisibleRequestIdSetRef.current;
    setExpandedRequestIds((prev) => {
      if (prev.size === 0) {
        return prev;
      }
      let changed = false;
      const next = new Set(prev);
      for (const id of prev) {
        // Logs/Diagnosis use composite keys (never in this set). Only drop expansion when a
        // visible request row from the previous fetch is no longer present.
        if (prevVisibleRequestIds.has(id) && !visibleRequestIds.has(id)) {
          next.delete(id);
          changed = true;
        }
      }
      return changed ? next : prev;
    });
    prevVisibleRequestIdSetRef.current = visibleRequestIds;
  }, [requests]);

  const onSortHeader = useCallback(
    (key: SortKey) => {
      if (sortKey === key) {
        setSortDir((d) => (d === "asc" ? "desc" : "asc"));
      } else {
        setSortKey(key);
        setSortDir(
          key === "timestamp" || key === "status_code" || key === "latency_ms"
            ? "desc"
            : "asc",
        );
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
      if (sortKey === "log_message") {
        return compareValues(a.log_message ?? "", b.log_message ?? "", sortDir);
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
    if (!hasDashboardSession) {
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
    const minLatency = Number(minLatencyMs);
    const maxLatency = Number(maxLatencyMs);
    const controller = new AbortController();
    void (async () => {
      const diagnosisPayload = {
        scope: {
          from_timestamp: toIsoWindow?.from,
          to_timestamp: toIsoWindow?.to,
          window_minutes: windowMinutes,
          method: method !== "ALL" ? method : undefined,
          status_class: statusClass !== "ALL" ? Number(statusClass) : undefined,
          path_contains: pathQuery.trim() || undefined,
          environments: normalizeCommaSeparated(serverEnvironmentQuery) || undefined,
          services: normalizeCommaSeparated(serverServiceQuery) || undefined,
          min_latency_ms:
            minLatencyMs.trim() !== "" && Number.isFinite(minLatency) && minLatency >= 0
              ? minLatency
              : undefined,
          max_latency_ms:
            maxLatencyMs.trim() !== "" && Number.isFinite(maxLatency) && maxLatency >= 0
              ? maxLatency
              : undefined,
          event_sql_filter:
            sqlFilterEnabled && sqlFilterApplied.trim() ? sqlFilterApplied.trim() : undefined,
        },
        requests: { limit: 1, offset: 0 },
        error_groups: { limit: 1, offset: 0 },
        diagnosis_error_group_key: groupKey,
        diagnosis_error_group_events: { limit: 20, offset: 0 },
      } satisfies DashboardDataQueryRequest;
      const { body, headers } = await buildOptionalGzipJsonRequest(diagnosisPayload);
      void dashboardSessionFetch(
        "/dashboard/query",
        {
          method: "POST",
          headers,
          body,
        },
        controller.signal,
      )
        .then(async (response) => {
          if (!response.ok) {
            return null;
          }
          const raw: unknown = await response.json();
          return parseDashboardDataQueryResponse(raw);
        })
        .then((payload) => {
          if (payload?.diagnosis_error_group_events) {
            setDiagnosisErrorGroupEvents(payload.diagnosis_error_group_events);
          }
        })
        .catch(() => {
          setDiagnosisErrorGroupEvents(null);
        });
    })();
    return () => {
      controller.abort();
    };
  }, [
    hasDashboardSession,
    dashboardRoutePath,
    recentErrorsPreview,
    toIsoWindow,
    windowMinutes,
    method,
    statusClass,
    minLatencyMs,
    maxLatencyMs,
    pathQuery,
    serverEnvironmentQuery,
    serverServiceQuery,
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

  const homeSliceValue = useMemo(
    (): DashboardHomeSliceValue => ({
      overview,
      overviewExtended,
      dashboardWidgets,
      requests,
      errorGroups,
      sparklineSeries,
      operationalSignals,
      rawItems,
      recentJobFailures,
      windowMinutes,
      isAbsoluteWindow: absoluteWindow !== null,
      windowFromTimestamp: toIsoWindow?.from ?? overview?.from_timestamp ?? requests?.from_timestamp ?? "",
      windowToTimestamp: toIsoWindow?.to ?? overview?.to_timestamp ?? requests?.to_timestamp ?? "",
      method,
      statusClass,
      requestLimit,
      errorGroupLimit,
      errorGroupSort,
      minLatencyMs,
      maxLatencyMs,
      pathQuery,
      serverEnvironmentQuery,
      serverServiceQuery,
      sqlFilterApplied,
      sqlFilterEnabled,
      errorMessage,
    }),
    [
      overview,
      overviewExtended,
      dashboardWidgets,
      requests,
      errorGroups,
      sparklineSeries,
      operationalSignals,
      rawItems,
      recentJobFailures,
      windowMinutes,
      absoluteWindow,
      toIsoWindow,
      method,
      statusClass,
      requestLimit,
      errorGroupLimit,
      errorGroupSort,
      minLatencyMs,
      maxLatencyMs,
      pathQuery,
      serverEnvironmentQuery,
      serverServiceQuery,
      sqlFilterApplied,
      sqlFilterEnabled,
      errorMessage,
    ],
  );

  const diagnosisSliceValue = useMemo(
    (): DashboardDiagnosisSliceValue => ({
      diagnosisTimeline,
      diagnosisFailures,
      diagnosisErrorGroupEvents,
      errorGroups,
      recentJobFailures,
    }),
    [diagnosisTimeline, diagnosisFailures, diagnosisErrorGroupEvents, errorGroups, recentJobFailures],
  );

  const alertsSliceValue = useMemo(
    (): DashboardAlertsSliceValue => ({
      alertDispatches,
      alertSettings,
      alertCapabilities,
    }),
    [alertDispatches, alertSettings, alertCapabilities],
  );

  const logsSliceValue = useMemo(
    (): DashboardLogsSliceValue => ({
      requests,
      filteredSorted,
      grouped,
      availableServices,
      availableEnvironments,
    }),
    [requests, filteredSorted, grouped, availableServices, availableEnvironments],
  );

  const value = useMemo(
    (): DashboardDataContextValue => ({
      hasDashboardSession,
      sessionEmail,
      sessionMembershipRole,
      sessionProjectId,
      sessionOrganizationId,
      authSessionResolved,
      dashboardAuthSessionIssue,
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
      dashboardWidgets,
      requests,
      errorGroups,
      diagnosisTimeline,
      diagnosisFailures,
      diagnosisErrorGroupEvents,
      recentJobFailures,
      alertSettings,
      apiKeys,
      lastIssuedApiKey,
      alertDispatches,
      alertCapabilities,
      onboardingStatus,
      workspaceBootstrapError,
      retryWorkspaceBootstrap,
      retentionSettings,
      themePreference,
      excludeLumonoxTraffic,
      errorGroupSort,
      loading,
      errorMessage,
      refreshToken,
      liveDataPaused,
      toggleLiveDataPaused,
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
      hydrateLogsViewFromUrl,
      copyRunbookCommand,
      saveAlertSettings,
      saveThemePreference,
      saveExcludeLumonoxTraffic,
      saveRetentionSettings,
      refreshApiKeys,
      setActiveDashboardProject,
      signOutDashboard,
      completeOnboarding,
      issueApiKey,
      rotateApiKey,
      revokeApiKey,
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
      savedSqlFilterPresets,
      savedScopePresets,
      saveSqlFilterPreset,
      removeSqlFilterPreset,
      applySavedSqlFilterPreset,
      saveScopePreset,
      removeScopePreset,
      applySavedScopePreset,
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
      hasDashboardSession,
      sessionEmail,
      sessionMembershipRole,
      sessionProjectId,
      sessionOrganizationId,
      authSessionResolved,
      dashboardAuthSessionIssue,
      windowMinutes,
      toIsoWindow,
      absoluteWindow,
      overview,
      overviewExtended,
      dashboardWidgets,
      requests,
      errorGroups,
      diagnosisTimeline,
      diagnosisFailures,
      diagnosisErrorGroupEvents,
      recentJobFailures,
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
      apiKeys,
      lastIssuedApiKey,
      alertDispatches,
      alertCapabilities,
      onboardingStatus,
      workspaceBootstrapError,
      retryWorkspaceBootstrap,
      retentionSettings,
      themePreference,
      excludeLumonoxTraffic,
      errorGroupSort,
      loading,
      errorMessage,
      refreshToken,
      liveDataPaused,
      toggleLiveDataPaused,
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
      hydrateLogsViewFromUrl,
      copyRunbookCommand,
      saveAlertSettings,
      saveThemePreference,
      saveExcludeLumonoxTraffic,
      saveRetentionSettings,
      refreshApiKeys,
      setActiveDashboardProject,
      signOutDashboard,
      completeOnboarding,
      issueApiKey,
      rotateApiKey,
      revokeApiKey,
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
      savedSqlFilterPresets,
      savedScopePresets,
      saveSqlFilterPreset,
      removeSqlFilterPreset,
      applySavedSqlFilterPreset,
      saveScopePreset,
      removeScopePreset,
      applySavedScopePreset,
    ],
  );

  return (
    <DashboardDataContext.Provider value={value}>
      <DashboardHomeSliceContext.Provider value={homeSliceValue}>
        <DashboardDiagnosisSliceContext.Provider value={diagnosisSliceValue}>
          <DashboardAlertsSliceContext.Provider value={alertsSliceValue}>
            <DashboardLogsSliceContext.Provider value={logsSliceValue}>
              {children}
            </DashboardLogsSliceContext.Provider>
          </DashboardAlertsSliceContext.Provider>
        </DashboardDiagnosisSliceContext.Provider>
      </DashboardHomeSliceContext.Provider>
    </DashboardDataContext.Provider>
  );
}
