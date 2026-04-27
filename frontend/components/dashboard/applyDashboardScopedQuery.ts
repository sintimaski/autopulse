"use client";

import type { DashboardScopedQueryState } from "./dashboardQueryState";

/** Minimal surface needed to apply persisted / URL-derived scoped server filters. */
export type DashboardScopedApplyTarget = {
  setAbsoluteWindow: (fromIso: string, toIso: string) => void;
  clearAbsoluteWindow: () => void;
  onServerWindowChange: (minutes: number) => void;
  onServerMethodChange: (value: string) => void;
  onServerStatusClassChange: (value: string) => void;
  setPathQuery: (value: string) => void;
  setMinLatencyMs: (value: string) => void;
  setMaxLatencyMs: (value: string) => void;
  setServerEnvironmentQuery: (value: string) => void;
  setServerServiceQuery: (value: string) => void;
  setRequestLimit: (value: number) => void;
  setRequestPage: (value: number) => void;
  setErrorGroupLimit: (value: number) => void;
  setErrorGroupPage: (value: number) => void;
  setErrorGroupSort: (value: "last_seen" | "count") => void;
  setSqlFilterApplied: (value: string) => void;
  setSqlFilterDraft: (value: string) => void;
  setSqlFilterEnabled: (value: boolean) => void;
};

export function applyDashboardScopedQueryState(
  d: DashboardScopedApplyTarget,
  parsed: DashboardScopedQueryState,
): void {
  if (parsed.isAbsoluteWindow && parsed.windowFromTimestamp && parsed.windowToTimestamp) {
    d.setAbsoluteWindow(parsed.windowFromTimestamp, parsed.windowToTimestamp);
  } else {
    d.clearAbsoluteWindow();
    d.onServerWindowChange(parsed.windowMinutes);
  }
  d.onServerMethodChange(parsed.method);
  d.onServerStatusClassChange(parsed.statusClass);
  d.setPathQuery(parsed.pathQuery);
  d.setMinLatencyMs(parsed.minLatencyMs);
  d.setMaxLatencyMs(parsed.maxLatencyMs);
  d.setServerEnvironmentQuery(parsed.serverEnvironmentQuery);
  d.setServerServiceQuery(parsed.serverServiceQuery);
  d.setRequestLimit(parsed.requestLimit);
  d.setRequestPage(parsed.requestPage);
  d.setErrorGroupLimit(parsed.errorGroupLimit);
  d.setErrorGroupPage(parsed.errorGroupPage);
  d.setErrorGroupSort(parsed.errorGroupSort);
  const f = (parsed.sqlFilterApplied ?? "").trim();
  if (parsed.sqlFilterEnabled && f) {
    d.setSqlFilterApplied(f);
    d.setSqlFilterDraft(f);
    d.setSqlFilterEnabled(true);
  } else {
    d.setSqlFilterApplied("");
    d.setSqlFilterDraft("");
    d.setSqlFilterEnabled(false);
  }
}
