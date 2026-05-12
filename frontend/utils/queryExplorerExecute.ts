import { normalizeCommaSeparated } from "../components/dashboard/dashboardQueryState";

export type QueryExplorerExecuteInput = {
  query: string;
  rowLimit: number;
  applyTimeWindow: boolean;
  windowMinutes: number;
  isAbsoluteWindow: boolean;
  windowFromTimestamp: string;
  windowToTimestamp: string;
  method: string;
  statusClass: string;
  pathQuery: string;
  serverEnvironmentQuery: string;
  serverServiceQuery: string;
  minLatencyMs: string;
  maxLatencyMs: string;
  sqlFilterEnabled: boolean;
  sqlFilterApplied: string;
};

function parseStatusClassForApi(raw: string): number | undefined {
  if (!raw || raw === "ALL") {
    return undefined;
  }
  const n = Number(raw);
  return Number.isFinite(n) ? n : undefined;
}

function parseLatencyMs(raw: string): number | undefined {
  const t = raw.trim();
  if (!t) {
    return undefined;
  }
  const n = Number(t);
  return Number.isFinite(n) ? n : undefined;
}

/** JSON body for `POST /dashboard/query-explorer/execute` (matches `QueryExplorerContent` semantics). */
export function buildQueryExplorerExecutePayload(p: QueryExplorerExecuteInput): Record<string, unknown> {
  const rowLimit = Math.max(1, Math.min(500, Math.floor(Number(p.rowLimit)) || 200));
  const base: Record<string, unknown> = {
    query: p.query,
    row_limit: rowLimit,
  };

  if (p.applyTimeWindow) {
    base.scope_mode = "time_window";
    base.window_minutes = p.windowMinutes;
    if (p.isAbsoluteWindow && p.windowFromTimestamp.trim() && p.windowToTimestamp.trim()) {
      base.from_timestamp = p.windowFromTimestamp.trim();
      base.to_timestamp = p.windowToTimestamp.trim();
    }
  } else {
    base.scope_mode = "project_wide";
  }

  if (p.method && p.method !== "ALL") {
    base.method = p.method;
  }
  const statusClass = parseStatusClassForApi(p.statusClass);
  if (statusClass !== undefined) {
    base.status_class = statusClass;
  }
  const path = p.pathQuery.trim();
  if (path) {
    base.path_contains = path;
  }
  const env = normalizeCommaSeparated(p.serverEnvironmentQuery);
  if (env) {
    base.environments = env;
  }
  const svc = normalizeCommaSeparated(p.serverServiceQuery);
  if (svc) {
    base.services = svc;
  }
  const minL = parseLatencyMs(p.minLatencyMs);
  if (minL !== undefined) {
    base.min_latency_ms = minL;
  }
  const maxL = parseLatencyMs(p.maxLatencyMs);
  if (maxL !== undefined) {
    base.max_latency_ms = maxL;
  }
  if (p.sqlFilterEnabled && p.sqlFilterApplied.trim()) {
    base.event_sql_filter = p.sqlFilterApplied.trim();
  }

  return base;
}
