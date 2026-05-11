"use client";

import { InlineDataSpinner } from "../../ui/InlineDataSpinner";
import type { InternalMetricsSnapshot } from "./settingsContentTypes";

type SettingsInternalMetricsSectionProps = {
  canViewInternalMetrics: boolean;
  internalMetricsLoadState: "idle" | "loading" | "ready" | "error";
  internalMetricsEnabled: boolean;
  internalMetricsReason: string | null;
  internalMetricsSnapshot: InternalMetricsSnapshot | null;
  metricStatusClass: (ok: boolean | null) => string;
  aggregateQueueHealthy: boolean | null;
  aggregateWorkerHealthy: boolean | null;
  queueUsageRatio: number | null;
};

export function SettingsInternalMetricsSection({
  canViewInternalMetrics,
  internalMetricsLoadState,
  internalMetricsEnabled,
  internalMetricsReason,
  internalMetricsSnapshot,
  metricStatusClass,
  aggregateQueueHealthy,
  aggregateWorkerHealthy,
  queueUsageRatio,
}: SettingsInternalMetricsSectionProps) {
  return (
    <section
      id="lx-settings-internal-metrics"
      className="rounded-2xl border border-slate-200/80 bg-white/95 p-5 shadow-sm dark:border-neutral-800 dark:bg-neutral-900"
    >
      <h2 className="text-base font-semibold text-slate-800 dark:text-neutral-100">Internal metrics</h2>
      <p className="mt-1 text-sm text-slate-500 dark:text-neutral-400">
        Operator-only health snapshot mirrored from the server&apos;s internal metrics endpoint.
      </p>
      {!canViewInternalMetrics ? (
        <p className="mt-2 text-sm text-slate-600 dark:text-neutral-300">
          Only organization owners and admins can view internal metrics.
        </p>
      ) : internalMetricsLoadState === "loading" ? (
        <div className="mt-4">
          <InlineDataSpinner label="Loading internal metrics…" />
        </div>
      ) : internalMetricsLoadState === "error" ? (
        <p className="mt-2 text-sm text-rose-700 dark:text-rose-300">
          {internalMetricsReason ?? "Could not load internal metrics."}
        </p>
      ) : !internalMetricsEnabled ? (
        <p className="mt-2 text-sm text-slate-600 dark:text-neutral-300">
          {internalMetricsReason ??
            "Internal metrics are disabled on this server. Set INTERNAL_METRICS_BEARER_TOKEN to enable."}
        </p>
      ) : internalMetricsSnapshot ? (
        <>
          <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <div className={`rounded-lg border px-3 py-2 ${metricStatusClass(Boolean(internalMetricsSnapshot.scheduler_running))}`}>
              <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-500 dark:text-neutral-400">
                Scheduler
              </p>
              <p className="mt-1 text-sm font-semibold text-slate-900 dark:text-neutral-100">
                {internalMetricsSnapshot.scheduler_running ? "running" : "stopped"}
              </p>
            </div>
            <div className={`rounded-lg border px-3 py-2 ${metricStatusClass(Boolean(internalMetricsSnapshot.retention_pressure_poll_running))}`}>
              <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-500 dark:text-neutral-400">
                Retention poll
              </p>
              <p className="mt-1 text-sm font-semibold text-slate-900 dark:text-neutral-100">
                {internalMetricsSnapshot.retention_pressure_poll_running ? "running" : "stopped"}
              </p>
            </div>
            <div className={`rounded-lg border px-3 py-2 ${metricStatusClass(Boolean(internalMetricsSnapshot.dashboard_ws_tick_running))}`}>
              <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-500 dark:text-neutral-400">
                WS tick loop
              </p>
              <p className="mt-1 text-sm font-semibold text-slate-900 dark:text-neutral-100">
                {internalMetricsSnapshot.dashboard_ws_tick_running ? "running" : "stopped"}
              </p>
            </div>
            <div className={`rounded-lg border px-3 py-2 ${metricStatusClass(Boolean(internalMetricsSnapshot.dashboard_realtime_bus_subscriber_running))}`}>
              <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-500 dark:text-neutral-400">
                Realtime subscriber
              </p>
              <p className="mt-1 text-sm font-semibold text-slate-900 dark:text-neutral-100">
                {internalMetricsSnapshot.dashboard_realtime_bus_subscriber_running ? "running" : "stopped"}
              </p>
            </div>
          </div>
          <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            <div className={`rounded-lg border px-3 py-2 ${metricStatusClass(aggregateQueueHealthy)}`}>
              <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-500 dark:text-neutral-400">
                Aggregate queue depth
              </p>
              <p className="mt-1 text-sm font-semibold text-slate-900 dark:text-neutral-100">
                {internalMetricsSnapshot.ingest_aggregate_queue?.depth ?? "n/a"}
              </p>
            </div>
            <div className={`rounded-lg border px-3 py-2 ${metricStatusClass(aggregateQueueHealthy)}`}>
              <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-500 dark:text-neutral-400">
                Aggregate queue max
              </p>
              <p className="mt-1 text-sm font-semibold text-slate-900 dark:text-neutral-100">
                {internalMetricsSnapshot.ingest_aggregate_queue?.max_size ?? "n/a"}
              </p>
            </div>
            <div className={`rounded-lg border px-3 py-2 ${metricStatusClass(aggregateWorkerHealthy)}`}>
              <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-500 dark:text-neutral-400">
                Aggregate worker
              </p>
              <p className="mt-1 text-sm font-semibold text-slate-900 dark:text-neutral-100">
                {internalMetricsSnapshot.ingest_aggregate_queue?.enabled ? "enabled" : "disabled"}
                {queueUsageRatio !== null ? ` · ${(queueUsageRatio * 100).toFixed(1)}% full` : ""}
              </p>
            </div>
          </div>
          {internalMetricsSnapshot.ingest_pressure ? (
            <details className="mt-4 overflow-hidden rounded-lg border border-slate-200 dark:border-neutral-700">
              <summary className="cursor-pointer bg-slate-50 px-3 py-2 text-sm font-semibold text-slate-700 dark:bg-neutral-800 dark:text-neutral-200">
                Ingest pressure signals ({Object.keys(internalMetricsSnapshot.ingest_pressure).length})
              </summary>
              <div className="overflow-x-auto">
                <table className="min-w-full text-left text-xs">
                  <thead className="bg-slate-50 text-slate-600 dark:bg-neutral-800 dark:text-neutral-300">
                    <tr>
                      <th className="px-3 py-2 font-semibold">Ingest pressure signal</th>
                      <th className="px-3 py-2 font-semibold">Value</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-200 bg-white dark:divide-neutral-800 dark:bg-neutral-900">
                    {Object.entries(internalMetricsSnapshot.ingest_pressure)
                      .sort((a, b) => a[0].localeCompare(b[0]))
                      .map(([key, value]) => (
                        <tr key={key}>
                          <td className="px-3 py-2 font-mono text-slate-700 dark:text-neutral-200">{key}</td>
                          <td className="px-3 py-2 text-slate-700 dark:text-neutral-200">{value}</td>
                        </tr>
                      ))}
                  </tbody>
                </table>
              </div>
            </details>
          ) : null}
        </>
      ) : (
        <p className="mt-2 text-sm text-slate-600 dark:text-neutral-300">
          Internal metrics are enabled, but no snapshot is currently available.
        </p>
      )}
    </section>
  );
}
