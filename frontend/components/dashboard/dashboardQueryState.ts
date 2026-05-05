"use client";

import {
  ERROR_GROUP_LIMIT_OPTIONS,
  REQUEST_LIMIT_OPTIONS,
} from "./dashboardTypes";

export type DashboardScopedQueryState = {
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
  requestPage: number;
  errorGroupLimit: number;
  errorGroupPage: number;
  errorGroupSort: "last_seen" | "count";
  /** URL key `sql_filter`: applied WHERE fragment when SQL filter is enabled. */
  sqlFilterApplied?: string;
  sqlFilterEnabled?: boolean;
};

const DEFAULTS = {
  windowMinutes: 60,
  method: "ALL",
  statusClass: "ALL",
  requestLimit: 100,
  requestPage: 0,
  errorGroupLimit: 25,
  errorGroupPage: 0,
  errorGroupSort: "last_seen" as const,
};

type ScopedStateSource = Pick<
  DashboardScopedQueryState,
  | "isAbsoluteWindow"
  | "windowMinutes"
  | "windowFromTimestamp"
  | "windowToTimestamp"
  | "method"
  | "statusClass"
  | "minLatencyMs"
  | "maxLatencyMs"
  | "pathQuery"
  | "serverEnvironmentQuery"
  | "serverServiceQuery"
  | "requestLimit"
  | "requestPage"
  | "errorGroupLimit"
  | "errorGroupPage"
  | "errorGroupSort"
  | "sqlFilterApplied"
  | "sqlFilterEnabled"
>;

export function buildCurrentScopedState(source: ScopedStateSource): DashboardScopedQueryState {
  return {
    isAbsoluteWindow: source.isAbsoluteWindow,
    windowMinutes: source.windowMinutes,
    windowFromTimestamp: source.windowFromTimestamp,
    windowToTimestamp: source.windowToTimestamp,
    method: source.method,
    statusClass: source.statusClass,
    minLatencyMs: source.minLatencyMs,
    maxLatencyMs: source.maxLatencyMs,
    pathQuery: source.pathQuery,
    serverEnvironmentQuery: source.serverEnvironmentQuery,
    serverServiceQuery: source.serverServiceQuery,
    requestLimit: source.requestLimit,
    requestPage: source.requestPage,
    errorGroupLimit: source.errorGroupLimit,
    errorGroupPage: source.errorGroupPage,
    errorGroupSort: source.errorGroupSort,
    sqlFilterApplied: source.sqlFilterApplied,
    sqlFilterEnabled: source.sqlFilterEnabled,
  };
}

export function normalizeCommaSeparated(value: string): string {
  return value
    .split(",")
    .map((part) => part.trim())
    .filter(Boolean)
    .join(",");
}

export function splitCommaSeparated(value: string): string[] {
  const normalized = normalizeCommaSeparated(value);
  return normalized ? normalized.split(",") : [];
}

function parsePositiveInt(raw: string | null, fallback: number): number {
  if (raw === null) {
    return fallback;
  }
  const value = Number(raw);
  if (!Number.isInteger(value) || value < 0) {
    return fallback;
  }
  return value;
}

function parseWindowMinutes(raw: string | null): number {
  const value = parsePositiveInt(raw, DEFAULTS.windowMinutes);
  return value > 0 ? value : DEFAULTS.windowMinutes;
}

function parseLimit(
  raw: string | null,
  options: number[],
  fallback: number,
): number {
  const value = parsePositiveInt(raw, fallback);
  return options.includes(value) ? value : fallback;
}

export function buildScopedQuery(
  state: DashboardScopedQueryState,
): URLSearchParams {
  const params = new URLSearchParams();

  if (
    state.isAbsoluteWindow &&
    state.windowFromTimestamp &&
    state.windowToTimestamp
  ) {
    params.set("from_timestamp", state.windowFromTimestamp);
    params.set("to_timestamp", state.windowToTimestamp);
  } else {
    params.set("window_minutes", String(state.windowMinutes));
  }

  if (state.method !== "ALL") {
    params.set("method", state.method);
  }
  if (state.statusClass !== "ALL") {
    params.set("status_class", state.statusClass);
  }
  if (state.pathQuery.trim()) {
    params.set("path_contains", state.pathQuery.trim());
  }
  if (state.minLatencyMs.trim()) {
    params.set("min_latency_ms", state.minLatencyMs.trim());
  }
  if (state.maxLatencyMs.trim()) {
    params.set("max_latency_ms", state.maxLatencyMs.trim());
  }

  const envCsv = normalizeCommaSeparated(state.serverEnvironmentQuery);
  if (envCsv) {
    params.set("environments", envCsv);
  }
  const serviceCsv = normalizeCommaSeparated(state.serverServiceQuery);
  if (serviceCsv) {
    params.set("services", serviceCsv);
  }

  if (state.requestLimit !== DEFAULTS.requestLimit) {
    params.set("request_limit", String(state.requestLimit));
  }
  if (state.requestPage > 0) {
    params.set("request_page", String(state.requestPage));
  }
  if (state.errorGroupLimit !== DEFAULTS.errorGroupLimit) {
    params.set("error_group_limit", String(state.errorGroupLimit));
  }
  if (state.errorGroupPage > 0) {
    params.set("error_group_page", String(state.errorGroupPage));
  }
  if (state.errorGroupSort === "count") {
    params.set("error_group_sort", "count");
  }
  const applied = (state.sqlFilterApplied ?? "").trim();
  if (state.sqlFilterEnabled && applied) {
    params.set("sql_filter", applied);
  }

  return params;
}

/** Compare query strings semantically (key order in toString() may differ). */
export function scopedQueryStringsEqual(a: string, b: string): boolean {
  if (a === b) {
    return true;
  }
  const pa = new URLSearchParams(a);
  const pb = new URLSearchParams(b);
  const keys = new Set<string>([...pa.keys(), ...pb.keys()]);
  for (const key of keys) {
    if (pa.get(key) !== pb.get(key)) {
      return false;
    }
  }
  return true;
}

export function buildRequestsPageHref(
  state: DashboardScopedQueryState,
  patch?: Partial<DashboardScopedQueryState>,
): string {
  const next: DashboardScopedQueryState = {
    ...state,
    ...patch,
    requestPage: patch?.requestPage ?? 0,
    errorGroupPage: patch?.errorGroupPage ?? state.errorGroupPage,
  };
  return `/requests?${buildScopedQuery(next).toString()}`;
}

/** Build `/diagnosis` href preserving the current scope (optionally narrowed); `hash` defaults to empty. */
export function buildDiagnosisPageHref(
  state: DashboardScopedQueryState,
  patch?: Partial<DashboardScopedQueryState>,
  hash = "",
): string {
  const next: DashboardScopedQueryState = {
    ...state,
    ...patch,
    requestPage: patch?.requestPage ?? 0,
    errorGroupPage: patch?.errorGroupPage ?? 0,
  };
  const q = buildScopedQuery(next).toString();
  return `/diagnosis?${q}${hash}`;
}

export function parseScopedQuery(
  searchParams: URLSearchParams,
): DashboardScopedQueryState {
  const from = searchParams.get("from_timestamp") ?? searchParams.get("bucket_start");
  const to = searchParams.get("to_timestamp") ?? searchParams.get("bucket_end");
  const method = searchParams.get("method") ?? DEFAULTS.method;
  const statusClass = searchParams.get("status_class") ?? DEFAULTS.statusClass;
  const errorGroupSort =
    searchParams.get("error_group_sort") === "count" ? "count" : "last_seen";

  const base: DashboardScopedQueryState = {
    isAbsoluteWindow: Boolean(from && to),
    windowMinutes: parseWindowMinutes(searchParams.get("window_minutes")),
    windowFromTimestamp: from ?? "",
    windowToTimestamp: to ?? "",
    method,
    statusClass,
    minLatencyMs: searchParams.get("min_latency_ms") ?? "",
    maxLatencyMs: searchParams.get("max_latency_ms") ?? "",
    pathQuery: searchParams.get("path_contains") ?? "",
    serverEnvironmentQuery: searchParams.get("environments") ?? "",
    serverServiceQuery: searchParams.get("services") ?? "",
    requestLimit: parseLimit(
      searchParams.get("request_limit"),
      REQUEST_LIMIT_OPTIONS,
      DEFAULTS.requestLimit,
    ),
    requestPage: parsePositiveInt(
      searchParams.get("request_page"),
      DEFAULTS.requestPage,
    ),
    errorGroupLimit: parseLimit(
      searchParams.get("error_group_limit"),
      ERROR_GROUP_LIMIT_OPTIONS,
      DEFAULTS.errorGroupLimit,
    ),
    errorGroupPage: parsePositiveInt(
      searchParams.get("error_group_page"),
      DEFAULTS.errorGroupPage,
    ),
    errorGroupSort,
  };
  if (searchParams.has("sql_filter")) {
    const f = (searchParams.get("sql_filter") ?? "").trim();
    base.sqlFilterApplied = f;
    base.sqlFilterEnabled = f.length > 0;
  }
  return base;
}

/** URL keys omitted when persisting or sharing bookmarks — the time window follows the user's current session. */
export const DASHBOARD_BOOKMARK_STRIP_KEYS = [
  "window_minutes",
  "from_timestamp",
  "to_timestamp",
  "request_page",
  "error_group_page",
] as const;

/** Strip window and pagination from a raw query string (no leading `?`). */
export function stripDashboardBookmarkQueryString(raw: string): string {
  const params = new URLSearchParams(raw);
  for (const k of DASHBOARD_BOOKMARK_STRIP_KEYS) {
    params.delete(k);
  }
  return params.toString();
}

/** Same as {@link stripDashboardBookmarkQueryString} for `location.search` (with optional leading `?`). */
export function stripDashboardBookmarkLocationSearch(search: string): string {
  const raw = search.startsWith("?") ? search.slice(1) : search;
  const stripped = stripDashboardBookmarkQueryString(raw);
  return stripped ? `?${stripped}` : "";
}
