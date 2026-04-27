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
  sqlQueryText?: string;
  sqlQueryCursor?: string;
  liveQueryEnabled?: boolean;
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
  if (state.sqlQueryText && state.sqlQueryText.trim()) {
    params.set("sql_query", state.sqlQueryText.trim());
  }
  if (state.sqlQueryCursor && state.sqlQueryCursor.trim()) {
    params.set("sql_cursor", state.sqlQueryCursor.trim());
  }
  if (state.liveQueryEnabled === false) {
    params.set("sql_live", "0");
  }

  return params;
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

  return {
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
    sqlQueryText: searchParams.get("sql_query") ?? "",
    sqlQueryCursor: searchParams.get("sql_cursor") ?? "",
    liveQueryEnabled: searchParams.get("sql_live") !== "0",
  };
}
