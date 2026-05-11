import { normalizeCommaSeparated } from "./dashboardQueryState";
import type { DashboardDataQueryRequest } from "./dashboardTypes";

export type DashboardBatchRoutePlan = {
  includeExtended: boolean;
  includeWidgets: boolean;
  includeErrorGroups: boolean;
  includeDiagnosis: boolean;
  includeRecentJobFailures: boolean;
  includeAlertDispatches: boolean;
  requestsLimitForRoute: number;
  requestsOffsetForRoute: number;
  errorGroupsLimitForRoute: number;
  errorGroupsOffsetForRoute: number;
};

/**
 * Pure routing rules for `POST /dashboard/query`: which optional slices to request and
 * pagination clamps that depend on the active dashboard route.
 */
export function planDashboardBatchQueryForRoute(args: {
  routePath: string;
  isDocumentVisible: boolean;
  hasAdvancedScopeFilters: boolean;
  requestLimit: number;
  requestPage: number;
  errorGroupLimit: number;
  errorGroupPage: number;
}): DashboardBatchRoutePlan {
  const {
    routePath,
    isDocumentVisible,
    hasAdvancedScopeFilters,
    requestLimit,
    requestPage,
    errorGroupLimit,
    errorGroupPage,
  } = args;

  const isStudioWidgetRoute = routePath.startsWith("/w/");
  let includeExtended =
    routePath === "/dashboard" || routePath === "/diagnosis" || routePath === "/widgets" || isStudioWidgetRoute;
  // Widgets power `/widgets`, studio `/w/...`, and the home dashboard "Advanced infrastructure insights" block.
  let includeWidgets = routePath === "/dashboard" || routePath === "/widgets" || isStudioWidgetRoute;
  if (!isDocumentVisible) {
    includeExtended = routePath === "/diagnosis";
    includeWidgets = false;
  }
  const includeErrorGroups = routePath === "/diagnosis" || routePath === "/dashboard";
  const includeDiagnosis = routePath === "/diagnosis";
  const includeRecentJobFailures = routePath === "/dashboard" || routePath === "/diagnosis";
  const includeAlertDispatches = routePath === "/alerts" || routePath === "/diagnosis";
  const requestsLimitForRoute =
    routePath === "/dashboard"
      ? Math.min(requestLimit, 25)
      : routePath === "/widgets" || isStudioWidgetRoute
        ? Math.min(requestLimit, 100)
        : requestLimit;
  const requestsOffsetForRoute =
    routePath === "/dashboard" || routePath === "/widgets" || isStudioWidgetRoute ? 0 : requestPage * requestLimit;
  const errorGroupsLimitForRoute = routePath === "/dashboard" ? Math.min(errorGroupLimit, 10) : errorGroupLimit;
  const errorGroupsOffsetForRoute = routePath === "/dashboard" ? 0 : errorGroupPage * errorGroupLimit;

  return {
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
  };
}

type BuildDashboardQueryRequestArgs = {
  plan: DashboardBatchRoutePlan;
  toIsoWindow: { from: string; to: string } | null;
  windowMinutes: number;
  method: string;
  statusClass: string;
  minLatencyMs: string;
  maxLatencyMs: string;
  pathQuery: string;
  correlationRequestId: string;
  serverEnvironmentQuery: string;
  serverServiceQuery: string;
  sqlFilterEnabled: boolean;
  sqlFilterApplied: string;
};

/** Builds the JSON body for `POST /dashboard/query` from scope + route plan. */
export function buildDashboardDataQueryRequest(args: BuildDashboardQueryRequestArgs): DashboardDataQueryRequest {
  const {
    plan,
    toIsoWindow,
    windowMinutes,
    method,
    statusClass,
    minLatencyMs,
    maxLatencyMs,
    pathQuery,
    correlationRequestId,
    serverEnvironmentQuery,
    serverServiceQuery,
    sqlFilterEnabled,
    sqlFilterApplied,
  } = args;

  const minLatency = Number(minLatencyMs);
  const maxLatency = Number(maxLatencyMs);
  const serverPath = pathQuery.trim();
  const corr = correlationRequestId.trim().slice(0, 128);
  const envCsv = normalizeCommaSeparated(serverEnvironmentQuery);
  const serviceCsv = normalizeCommaSeparated(serverServiceQuery);

  return {
    scope: {
      from_timestamp: toIsoWindow?.from,
      to_timestamp: toIsoWindow?.to,
      window_minutes: windowMinutes,
      method: method !== "ALL" ? method : undefined,
      status_class: statusClass !== "ALL" ? Number(statusClass) : undefined,
      path_contains: serverPath || undefined,
      environments: envCsv || undefined,
      services: serviceCsv || undefined,
      min_latency_ms:
        minLatencyMs.trim() !== "" && Number.isFinite(minLatency) && minLatency >= 0 ? minLatency : undefined,
      max_latency_ms:
        maxLatencyMs.trim() !== "" && Number.isFinite(maxLatency) && maxLatency >= 0 ? maxLatency : undefined,
      event_sql_filter: sqlFilterEnabled && sqlFilterApplied.trim() ? sqlFilterApplied.trim() : undefined,
      correlation_request_id: corr || undefined,
    },
    include_extended: plan.includeExtended,
    include_widgets: plan.includeWidgets,
    include_error_groups: plan.includeErrorGroups,
    include_diagnosis: plan.includeDiagnosis,
    include_recent_job_failures: plan.includeRecentJobFailures,
    include_alert_dispatches: plan.includeAlertDispatches,
    requests: { limit: plan.requestsLimitForRoute, offset: plan.requestsOffsetForRoute },
    error_groups: { limit: plan.errorGroupsLimitForRoute, offset: plan.errorGroupsOffsetForRoute },
    alert_dispatches: { limit: 25, offset: 0 },
  };
}
