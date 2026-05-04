"use client";

import { Pause, Play } from "../../lib/icons";
import { DashboardScopeFacetShell } from "./DashboardScopeFacetShell";
import { useDashboardData } from "./DashboardDataContext";

function formatWindowSummary(d: ReturnType<typeof useDashboardData>): string {
  if (d.isAbsoluteWindow && d.windowFromTimestamp && d.windowToTimestamp) {
    const from = new Date(d.windowFromTimestamp);
    const to = new Date(d.windowToTimestamp);
    if (Number.isFinite(from.getTime()) && Number.isFinite(to.getTime())) {
      return `Custom window · ${from.toLocaleString()} → ${to.toLocaleString()}`;
    }
    return "Custom time window";
  }
  const label =
    d.windowMinutes >= 1440
      ? `${Math.round(d.windowMinutes / 1440)}d`
      : d.windowMinutes >= 60
        ? `${Math.round(d.windowMinutes / 60)}h`
        : `${d.windowMinutes}m`;
  return `Last ${label}`;
}

function formatFilterHint(d: ReturnType<typeof useDashboardData>): string {
  const parts: string[] = [];
  if (d.method !== "ALL") parts.push(d.method);
  if (d.statusClass !== "ALL") parts.push(`${d.statusClass}xx`);
  const path = d.pathQuery.trim();
  if (path) parts.push(`path ${path.length > 32 ? `${path.slice(0, 32)}...` : path}`);
  if (d.serverEnvironmentTags.length) parts.push(`env ${d.serverEnvironmentTags.join(",")}`);
  if (d.serverServiceTags.length) parts.push(`svc ${d.serverServiceTags.join(",")}`);
  if (d.sqlFilterEnabled && d.sqlFilterApplied.trim()) parts.push("SQL scope on");
  return parts.length ? parts.join(" · ") : "All methods · all status classes";
}

export function DiagnosisRequestsStickyScopeBar() {
  const d = useDashboardData();
  const paused = d.liveDataPaused;

  return (
    <DashboardScopeFacetShell className="sticky top-0 z-30 mb-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="min-w-0 flex-1">
          <p className="text-sm font-semibold text-slate-800 dark:text-neutral-100">{formatWindowSummary(d)}</p>
          <p className="mt-0.5 text-xs text-slate-600 dark:text-neutral-400">{formatFilterHint(d)}</p>
        </div>
        <button
          type="button"
          onClick={() => d.toggleLiveDataPaused()}
          title={paused ? "Resume live updates" : "Pause live updates"}
          aria-label={paused ? "Resume live updates" : "Pause live updates"}
          className="ap-btn shrink-0 p-2"
        >
          {paused ? <Play className="size-4" aria-hidden /> : <Pause className="size-4" aria-hidden />}
        </button>
      </div>
    </DashboardScopeFacetShell>
  );
}
