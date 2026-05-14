"use client";

import {
  buildScopedQuery,
  normalizeCommaSeparated,
  splitCommaSeparated,
  type DashboardScopedQueryState,
} from "./dashboardQueryState";
import { DEFAULT_LOGS_VIEW_CLIENT, type PersistedLogsClientSlice } from "./dashboardPersistentScope";
import { GROUP_OPTIONS, LOGS_TABLE_SORT_KEY_SET, type GroupBy, type SortDir, type SortKey } from "./dashboardTypes";

export function mergeLogsClientSearchParams(
  base: URLSearchParams,
  client: Pick<PersistedLogsClientSlice, "groupBy" | "sortKey" | "sortDir" | "envTags" | "serviceTags">,
): URLSearchParams {
  const out = new URLSearchParams(base.toString());
  if (client.groupBy !== "none") {
    out.set("logs_group", client.groupBy);
  } else {
    out.delete("logs_group");
  }
  if (
    client.sortKey !== DEFAULT_LOGS_VIEW_CLIENT.sortKey ||
    client.sortDir !== DEFAULT_LOGS_VIEW_CLIENT.sortDir
  ) {
    out.set("logs_sort", client.sortKey);
    out.set("logs_sort_dir", client.sortDir);
  } else {
    out.delete("logs_sort");
    out.delete("logs_sort_dir");
  }
  const envCsv = normalizeCommaSeparated([...client.envTags].sort().join(","));
  if (envCsv) {
    out.set("logs_client_env", envCsv);
  } else {
    out.delete("logs_client_env");
  }
  const svcCsv = normalizeCommaSeparated([...client.serviceTags].sort().join(","));
  if (svcCsv) {
    out.set("logs_client_svc", svcCsv);
  } else {
    out.delete("logs_client_svc");
  }
  return out;
}

export function parseLogsClientSearchParams(searchParams: URLSearchParams): PersistedLogsClientSlice {
  const groupRaw = searchParams.get("logs_group");
  const groupBy =
    groupRaw && GROUP_OPTIONS.some((o) => o.value === groupRaw) ? (groupRaw as GroupBy) : "none";

  const sortRaw = searchParams.get("logs_sort");
  const sortKey: SortKey =
    sortRaw && LOGS_TABLE_SORT_KEY_SET.has(sortRaw)
      ? (sortRaw as SortKey)
      : DEFAULT_LOGS_VIEW_CLIENT.sortKey;

  const dirRaw = searchParams.get("logs_sort_dir");
  let sortDir: SortDir = DEFAULT_LOGS_VIEW_CLIENT.sortDir;
  if (dirRaw === "asc" || dirRaw === "desc" || dirRaw === "none") {
    sortDir = dirRaw;
  }

  const envTags = splitCommaSeparated(searchParams.get("logs_client_env") ?? "");
  const serviceTags = splitCommaSeparated(searchParams.get("logs_client_svc") ?? "");

  return { groupBy, sortKey, sortDir, envTags, serviceTags };
}

export function buildLiveDashboardSearchString(
  pathname: string,
  scoped: DashboardScopedQueryState,
  logsClient: PersistedLogsClientSlice,
): string {
  const base = buildScopedQuery(scoped);
  if (pathname === "/logs") {
    return mergeLogsClientSearchParams(base, logsClient).toString();
  }
  return base.toString();
}
