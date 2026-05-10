import type { Dispatch, MutableRefObject, SetStateAction } from "react";

import {
  buildDashboardFetchError,
  buildDashboardNetworkError,
  type DashboardFetchResult,
} from "../../../utils/dashboardFetchErrors";
import { parseDashboardDataQueryResponse } from "../../../utils/dashboardQueryResponseGuards";
import {
  buildDashboardDataQueryRequest,
  planDashboardBatchQueryForRoute,
} from "../dashboardQueryBundle";
import { normalizeCommaSeparated } from "../dashboardQueryState";
import {
  buildDashboardDataCacheScopeKey,
  readDashboardSnapshot,
  writeDashboardSnapshot,
} from "../dashboardSnapshotCache";
import {
  buildOptionalGzipJsonRequest,
  LIVE_FETCH_SLOW_MS,
  LIVE_REFRESH_BACKOFF_DURATION_MS,
  trimDashboardWidgetPayload,
} from "../dashboardDataFetchUtils";
import { dashboardSessionFetch } from "../dashboardSessionFetch";
import type {
  AlertDispatchesResponse,
  DashboardDataQueryRequest,
  DashboardDataQueryResponse,
  DashboardWidgetsResponse,
  DiagnosisErrorGroupEventsResponse,
  DiagnosisFailureRoutesResponse,
  DiagnosisTimelineResponse,
  ErrorGroupsResponse,
  OverviewExtendedResponse,
  OverviewResponse,
  RecentJobFailuresResponse,
  RequestsResponse,
} from "../dashboardTypes";

/** Dependencies for the main `POST /dashboard/query` refresh cycle (extracted from `DashboardDataProvider`). */
export type DashboardBatchQueryExecutionArgs = {
  fetchSignal: AbortSignal;
  isCancelled: () => boolean;
  dashboardRoutePath: string;
  toIsoWindow: { from: string; to: string } | null;
  windowMinutes: number;
  method: string;
  statusClass: string;
  minLatencyMs: string;
  maxLatencyMs: string;
  pathQuery: string;
  serverEnvironmentQuery: string;
  serverServiceQuery: string;
  requestLimit: number;
  requestPage: number;
  errorGroupLimit: number;
  errorGroupPage: number;
  errorGroupSort: "last_seen" | "count";
  sqlFilterEnabled: boolean;
  sqlFilterApplied: string;
  absoluteWindow: { from: string; to: string } | null;
  reloadDashboardAuthSession: () => void;
  liveWsBackoffUntilRef: MutableRefObject<number>;
  dashboardFetchInFlightRef: MutableRefObject<boolean>;
  dashboardQueuedRefreshRef: MutableRefObject<boolean>;
  liveRefreshPausedRef: MutableRefObject<boolean>;
  hasLoadedDashboardData: MutableRefObject<boolean>;
  stretchAbsoluteEndAfterResumeRef: MutableRefObject<boolean>;
  setLoading: Dispatch<SetStateAction<boolean>>;
  setErrorMessage: Dispatch<SetStateAction<string | null>>;
  setOverview: Dispatch<SetStateAction<OverviewResponse | null>>;
  setOverviewExtended: Dispatch<SetStateAction<OverviewExtendedResponse | null>>;
  setDashboardWidgets: Dispatch<SetStateAction<DashboardWidgetsResponse | null>>;
  setRequests: Dispatch<SetStateAction<RequestsResponse | null>>;
  setErrorGroups: Dispatch<SetStateAction<ErrorGroupsResponse | null>>;
  setDiagnosisTimeline: Dispatch<SetStateAction<DiagnosisTimelineResponse | null>>;
  setDiagnosisFailures: Dispatch<SetStateAction<DiagnosisFailureRoutesResponse | null>>;
  setDiagnosisErrorGroupEvents: Dispatch<SetStateAction<DiagnosisErrorGroupEventsResponse | null>>;
  setAlertDispatches: Dispatch<SetStateAction<AlertDispatchesResponse | null>>;
  setRecentJobFailures: Dispatch<SetStateAction<RecentJobFailuresResponse | null>>;
  setAbsoluteWindowState: Dispatch<SetStateAction<{ from: string; to: string } | null>>;
  setRefreshToken: Dispatch<SetStateAction<number>>;
};

/**
 * Runs one dashboard batch query: plan → optional snapshot → POST `/dashboard/query` → apply slices.
 * Live/backoff refs and cancellation semantics stay caller-owned.
 */
export async function executeDashboardBatchQuery(args: DashboardBatchQueryExecutionArgs): Promise<void> {
  const {
    fetchSignal,
    isCancelled,
    dashboardRoutePath: routePath,
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
    requestPage,
    errorGroupLimit,
    errorGroupPage,
    errorGroupSort,
    sqlFilterEnabled,
    sqlFilterApplied,
    absoluteWindow,
    reloadDashboardAuthSession,
    liveWsBackoffUntilRef,
    dashboardFetchInFlightRef,
    dashboardQueuedRefreshRef,
    liveRefreshPausedRef,
    hasLoadedDashboardData,
    stretchAbsoluteEndAfterResumeRef,
    setLoading,
    setErrorMessage,
    setOverview,
    setOverviewExtended,
    setDashboardWidgets,
    setRequests,
    setErrorGroups,
    setDiagnosisTimeline,
    setDiagnosisFailures,
    setDiagnosisErrorGroupEvents,
    setAlertDispatches,
    setRecentJobFailures,
    setAbsoluteWindowState,
    setRefreshToken,
  } = args;

  const fetchStartedAt = Date.now();
  if (routePath === "/settings") {
    return;
  }

  const isDocumentVisible = typeof document === "undefined" || document.visibilityState === "visible";
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
      fetchSignal,
    );
    if (batchResponse.status === 401) {
      reloadDashboardAuthSession();
    }
    const elapsedMs = Date.now() - fetchStartedAt;
    if (!isCancelled()) {
      const status = batchResponse.status;
      if (elapsedMs >= LIVE_FETCH_SLOW_MS || status === 429 || status === 503 || status >= 500) {
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

    if (useSnapshot && includeExtended && overviewData && requestsData && data.overview_extended) {
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
          overviewData?.server_now ?? requestsData?.server_now ?? data.error_groups?.server_now ?? null;
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
      if (!isCancelled() && error.message === "Dashboard request timed out") {
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
}
