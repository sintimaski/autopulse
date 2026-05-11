import { ERROR_GROUP_LIMIT_OPTIONS, REQUEST_LIMIT_OPTIONS } from "./dashboardTypes";
import type { DashboardScopedQueryState } from "./dashboardQueryState";
import { normalizeCommaSeparated } from "./dashboardQueryState";
import type { SavedScopePreset } from "./dashboardDataContextTypes";

export function coerceScopeNumber(value: unknown, fallback: number): number {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value;
  }
  const n = Number(value);
  return Number.isFinite(n) ? n : fallback;
}

export function savedPresetScopeToDashboardQuery(
  scope: SavedScopePreset["scope"],
): DashboardScopedQueryState {
  const wmRaw = coerceScopeNumber(scope.windowMinutes, 60);
  const windowMinutes = wmRaw > 0 ? wmRaw : 60;
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

  return {
    isAbsoluteWindow: Boolean(scope.isAbsoluteWindow),
    windowMinutes,
    windowFromTimestamp: typeof scope.windowFromTimestamp === "string" ? scope.windowFromTimestamp : "",
    windowToTimestamp: typeof scope.windowToTimestamp === "string" ? scope.windowToTimestamp : "",
    method: typeof scope.method === "string" ? scope.method : "ALL",
    statusClass: typeof scope.statusClass === "string" ? scope.statusClass : "ALL",
    minLatencyMs: typeof scope.minLatencyMs === "string" ? scope.minLatencyMs : "",
    maxLatencyMs: typeof scope.maxLatencyMs === "string" ? scope.maxLatencyMs : "",
    pathQuery: typeof scope.pathQuery === "string" ? scope.pathQuery : "",
    serverEnvironmentQuery:
      typeof scope.serverEnvironmentQuery === "string"
        ? normalizeCommaSeparated(scope.serverEnvironmentQuery)
        : "",
    serverServiceQuery:
      typeof scope.serverServiceQuery === "string" ? normalizeCommaSeparated(scope.serverServiceQuery) : "",
    requestLimit,
    requestPage: 0,
    errorGroupLimit,
    errorGroupPage: 0,
    errorGroupSort: scope.errorGroupSort === "count" ? "count" : "last_seen",
    correlationRequestId: "",
    sqlFilterApplied: typeof scope.sqlFilterApplied === "string" ? scope.sqlFilterApplied : "",
    sqlFilterEnabled: Boolean(scope.sqlFilterEnabled),
  };
}
