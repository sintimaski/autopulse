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
  buildOptionalGzipJsonRequest,
  DASHBOARD_HEAVY_SLICES_REFRESH_INTERVAL_MS,
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
  sqlFilterEnabled: boolean;
  sqlFilterApplied: string;
  absoluteWindow: { from: string; to: string } | null;
  reloadDashboardAuthSession: () => void;
  dashboardFetchInFlightRef: MutableRefObject<boolean>;
  dashboardQueuedRefreshRef: MutableRefObject<boolean>;
  liveRefreshPausedRef: MutableRefObject<boolean>;
  hasLoadedDashboardData: MutableRefObject<boolean>;
  dashboardHeavyRefreshAtRef: MutableRefObject<number>;
  dashboardHeavyScopeKeyRef: MutableRefObject<string>;
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
  setChartsScopePending: Dispatch<SetStateAction<boolean>>;
  /** Wall-clock ms when an `overview` slice was last applied on the client (successful batch). */
  setOverviewDataReceivedAtMs: Dispatch<SetStateAction<number | null>>;
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
    sqlFilterEnabled,
    sqlFilterApplied,
    absoluteWindow,
    reloadDashboardAuthSession,
    dashboardFetchInFlightRef,
    dashboardQueuedRefreshRef,
    liveRefreshPausedRef,
    hasLoadedDashboardData,
    dashboardHeavyRefreshAtRef,
    dashboardHeavyScopeKeyRef,
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
    setChartsScopePending,
    setOverviewDataReceivedAtMs,
  } = args;

  if (routePath === "/settings") {
    if (!isCancelled()) {
      setChartsScopePending(false);
    }
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
  let effectivePlan = plan;
  /** Home overview alternates light vs heavy `POST /dashboard/query`; freshness clock resets only on heavy (full bundle). */
  let bumpOverviewDataReceivedClock = false;

  const isInitialLoad = !hasLoadedDashboardData.current;
  if (routePath === "/dashboard") {
    const heavyScopeKey = JSON.stringify({
      routePath,
      from: toIsoWindow?.from ?? "",
      to: toIsoWindow?.to ?? "",
      windowMinutes,
      method,
      statusClass,
      minLatencyMs,
      maxLatencyMs,
      pathQuery: pathQuery.trim(),
      serverEnvironmentQuery: normalizeCommaSeparated(serverEnvironmentQuery),
      serverServiceQuery: normalizeCommaSeparated(serverServiceQuery),
      sqlFilterEnabled,
      sqlFilterApplied: sqlFilterApplied.trim(),
      includeWidgets: plan.includeWidgets,
    });
    const now = Date.now();
    const scopeChanged = dashboardHeavyScopeKeyRef.current !== heavyScopeKey;
    const shouldRefreshHeavySlices =
      isInitialLoad || scopeChanged || now >= dashboardHeavyRefreshAtRef.current;
    bumpOverviewDataReceivedClock = shouldRefreshHeavySlices;
    if (!shouldRefreshHeavySlices) {
      effectivePlan = {
        ...plan,
        includeExtended: false,
        includeWidgets: false,
        includeErrorGroups: false,
        includeRecentJobFailures: false,
      };
    } else {
      dashboardHeavyScopeKeyRef.current = heavyScopeKey;
      dashboardHeavyRefreshAtRef.current = now + DASHBOARD_HEAVY_SLICES_REFRESH_INTERVAL_MS;
    }
  }
  const {
    includeExtended,
    includeWidgets,
    includeErrorGroups,
    includeDiagnosis,
    includeRecentJobFailures,
    includeAlertDispatches,
    requestsLimitForRoute,
    requestsOffsetForRoute,
    errorGroupsLimitForRoute,
    errorGroupsOffsetForRoute,
  } = effectivePlan;

  if (isInitialLoad) {
    setLoading(true);
  }
  dashboardFetchInFlightRef.current = true;
  setErrorMessage(null);
  try {
    const scopeRequest: DashboardDataQueryRequest = buildDashboardDataQueryRequest({
      plan: effectivePlan,
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
      if (bumpOverviewDataReceivedClock) {
        setOverviewDataReceivedAtMs(Date.now());
      }
    }
    if (requestsData) {
      setRequests(requestsData);
    }

    if (includeExtended && data.overview_extended) {
      setOverviewExtended(data.overview_extended);
    } else if (routePath !== "/dashboard") {
      setOverviewExtended(null);
    }
    if (includeWidgets && data.widgets != null) {
      setDashboardWidgets(trimDashboardWidgetPayload(data.widgets));
    } else if (!includeWidgets && routePath !== "/dashboard") {
      setDashboardWidgets(null);
    }
    if (includeErrorGroups && data.error_groups) {
      setErrorGroups(data.error_groups);
    } else if (routePath !== "/dashboard") {
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
    } else if (routePath !== "/dashboard") {
      setRecentJobFailures(null);
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
    if (!isCancelled()) {
      setChartsScopePending(false);
    }
  }
}
