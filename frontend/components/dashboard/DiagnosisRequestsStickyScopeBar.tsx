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

/** Rolling window + live: pause. Custom/abs scope: lx only (never with pause/play). Rolling + paused: unpause only. */
export function DiagnosisRequestsStickyScopeBar() {
  const d = useDashboardData();
  const paused = d.liveDataPaused;
  const windowLabel =
    d.windowMinutes >= 1440
      ? `${Math.round(d.windowMinutes / 1440)}d`
      : d.windowMinutes >= 60
        ? `${Math.round(d.windowMinutes / 60)}h`
        : `${d.windowMinutes}m`;
  const lxLabel = `Last ${windowLabel}`;
  const lxTitle = `Return to last ${windowLabel} rolling window and resume live updates`;

  const showLx = d.isAbsoluteWindow;
  const showPausePlay = !d.isAbsoluteWindow;
  const showPause = showPausePlay && !paused;
  const showUnpause = showPausePlay && paused;

  return (
    <DashboardScopeFacetShell className="sticky top-0 z-30 mb-4">
      <p className="text-base font-semibold text-slate-800 dark:text-neutral-100">{formatWindowSummary(d)}</p>
      <div className="mt-2 flex flex-wrap items-start justify-between gap-4">
        <p className="min-w-0 flex-1 text-sm leading-relaxed text-slate-600 dark:text-neutral-400">{formatFilterHint(d)}</p>
        <div className="flex shrink-0 items-center justify-end gap-2">
          {showLx ? (
            <button
              type="button"
              onClick={() => d.clearAbsoluteWindow()}
              title={lxTitle}
              aria-label={lxTitle}
              className="ap-btn shrink-0 px-3 py-1.5 text-xs font-medium"
            >
              {lxLabel}
            </button>
          ) : null}
          {showPause ? (
            <button
              type="button"
              onClick={() => d.toggleLiveDataPaused()}
              title="Pause live updates"
              aria-label="Pause live updates"
              className="ap-btn shrink-0 p-2"
            >
              <Pause className="size-4" aria-hidden />
            </button>
          ) : null}
          {showUnpause ? (
            <button
              type="button"
              onClick={() => d.toggleLiveDataPaused()}
              title="Resume live updates"
              aria-label="Resume live updates"
              className="ap-btn shrink-0 p-2"
            >
              <Play className="size-4" aria-hidden />
            </button>
          ) : null}
        </div>
      </div>
    </DashboardScopeFacetShell>
  );
}
