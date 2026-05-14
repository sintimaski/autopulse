"use client";

import type { DashboardSystemDiagnosticsResponse } from "../dashboardTypes";
import { copyTextToClipboard } from "../clipboard";
import { InlineDataSpinner } from "../../ui/InlineDataSpinner";
import type { SchedulerJobSummary, SystemDiagnosticsSummary } from "../../../utils/systemDiagnostics";
import { formatDurationSeconds } from "../../../utils/systemDiagnostics";

type SettingsSystemDiagnosticsSectionProps = {
  canViewSystemDiagnostics: boolean;
  systemDiagnosticsLoadState: "idle" | "loading" | "ready" | "error";
  systemDiagnosticsSnapshot: DashboardSystemDiagnosticsResponse | null;
  systemDiagnosticsSummary: SystemDiagnosticsSummary;
  schedulerJobs: SchedulerJobSummary[];
  metricStatusClass: (ok: boolean | null) => string;
  systemDiagnosticsMessage: string | null;
  setSystemDiagnosticsMessage: (message: string | null) => void;
};

export function SettingsSystemDiagnosticsSection({
  canViewSystemDiagnostics,
  systemDiagnosticsLoadState,
  systemDiagnosticsSnapshot,
  systemDiagnosticsSummary,
  schedulerJobs,
  metricStatusClass,
  systemDiagnosticsMessage,
  setSystemDiagnosticsMessage,
}: SettingsSystemDiagnosticsSectionProps) {
  return (
    <section
      id="lx-settings-system-diagnostics"
      className="rounded-2xl border border-slate-200/80 bg-white/95 p-5 shadow-sm dark:border-neutral-800 dark:bg-neutral-900"
    >
      <h2 className="text-base font-semibold text-slate-800 dark:text-neutral-100">System diagnostics</h2>
      <p className="mt-1 text-sm text-slate-500 dark:text-neutral-400">
        Support snapshot for topology guardrails, scheduler health, replay backlog, and project freshness.
      </p>
      {!canViewSystemDiagnostics ? (
        <p className="mt-2 text-sm text-slate-600 dark:text-neutral-300">
          Only organization owners and admins can view diagnostics.
        </p>
      ) : systemDiagnosticsLoadState === "loading" ? (
        <div className="mt-4">
          <InlineDataSpinner label="Loading diagnostics snapshot…" />
        </div>
      ) : systemDiagnosticsLoadState === "error" ? (
        <p className="mt-2 text-sm text-rose-700 dark:text-rose-300">
          Could not load diagnostics. Verify dashboard auth and backend availability.
        </p>
      ) : systemDiagnosticsSnapshot ? (
        <>
          <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <div className={`rounded-lg border px-3 py-2 ${metricStatusClass(systemDiagnosticsSummary.guardrailStatus === "healthy" ? true : systemDiagnosticsSummary.guardrailStatus === "degraded" ? false : null)}`}>
              <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-500 dark:text-neutral-400">
                Topology guardrails
              </p>
              <p className="mt-1 text-sm font-semibold text-slate-900 dark:text-neutral-100">
                {systemDiagnosticsSummary.guardrailStatus}
              </p>
            </div>
            <div className={`rounded-lg border px-3 py-2 ${metricStatusClass(systemDiagnosticsSummary.schedulerStatus === "running" ? true : systemDiagnosticsSummary.schedulerStatus === "stopped" ? false : null)}`}>
              <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-500 dark:text-neutral-400">
                Scheduler state
              </p>
              <p className="mt-1 text-sm font-semibold text-slate-900 dark:text-neutral-100">
                {systemDiagnosticsSummary.schedulerStatus}
              </p>
            </div>
            <div className={`rounded-lg border px-3 py-2 ${metricStatusClass((systemDiagnosticsSummary.pendingSqlTailRepairs ?? 0) < 1)}`}>
              <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-500 dark:text-neutral-400">
                Pending SQL-tail repairs
              </p>
              <p className="mt-1 text-sm font-semibold text-slate-900 dark:text-neutral-100">
                {systemDiagnosticsSummary.pendingSqlTailRepairs ?? "n/a"}
              </p>
            </div>
            <div className={`rounded-lg border px-3 py-2 ${metricStatusClass(systemDiagnosticsSummary.ingestionLagSeconds !== null ? systemDiagnosticsSummary.ingestionLagSeconds < 600 : null)}`}>
              <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-500 dark:text-neutral-400">
                Ingestion lag
              </p>
              <p className="mt-1 text-sm font-semibold text-slate-900 dark:text-neutral-100">
                {formatDurationSeconds(systemDiagnosticsSummary.ingestionLagSeconds)}
              </p>
            </div>
          </div>
          <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            <div className="rounded-lg border border-slate-200 bg-slate-50/70 px-3 py-2 dark:border-neutral-700 dark:bg-neutral-800/60">
              <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-500 dark:text-neutral-400">
                Dead-lettered SQL-tail repairs
              </p>
              <p className="mt-1 text-sm font-semibold text-slate-900 dark:text-neutral-100">
                {systemDiagnosticsSummary.deadLetteredSqlTailRepairs ?? "n/a"}
              </p>
            </div>
            <div className="rounded-lg border border-slate-200 bg-slate-50/70 px-3 py-2 dark:border-neutral-700 dark:bg-neutral-800/60">
              <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-500 dark:text-neutral-400">
                Aggregate dead-letter backlog
              </p>
              <p className="mt-1 text-sm font-semibold text-slate-900 dark:text-neutral-100">
                {systemDiagnosticsSummary.aggregateDeadLetterBacklog ?? "n/a"}
              </p>
            </div>
            <div className="rounded-lg border border-slate-200 bg-slate-50/70 px-3 py-2 dark:border-neutral-700 dark:bg-neutral-800/60">
              <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-500 dark:text-neutral-400">
                Generated at
              </p>
              <p className="mt-1 text-sm font-semibold text-slate-900 dark:text-neutral-100">
                {systemDiagnosticsSummary.generatedAt
                  ? new Date(systemDiagnosticsSummary.generatedAt).toLocaleString()
                  : "n/a"}
              </p>
            </div>
          </div>
          {schedulerJobs.length > 0 ? (
            <div className="mt-4 overflow-x-auto rounded-lg border border-slate-200 dark:border-neutral-700">
              <table className="min-w-full text-left text-xs">
                <thead className="bg-slate-50 text-slate-600 dark:bg-neutral-800 dark:text-neutral-300">
                  <tr>
                    <th className="px-3 py-2 font-semibold">Job</th>
                    <th className="px-3 py-2 font-semibold">Status</th>
                    <th className="px-3 py-2 font-semibold">Last run</th>
                    <th className="px-3 py-2 font-semibold">Next run</th>
                    <th className="px-3 py-2 font-semibold">Failure</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200 bg-white dark:divide-neutral-800 dark:bg-neutral-900">
                  {schedulerJobs.map((job) => (
                    <tr key={job.jobName}>
                      <td className="px-3 py-2 font-mono text-slate-700 dark:text-neutral-200">{job.jobName}</td>
                      <td className="px-3 py-2 text-slate-700 dark:text-neutral-200">{job.status}</td>
                      <td className="px-3 py-2 text-slate-700 dark:text-neutral-200">
                        {job.lastFinishedAt ? new Date(job.lastFinishedAt).toLocaleString() : "n/a"}
                      </td>
                      <td className="px-3 py-2 text-slate-700 dark:text-neutral-200">
                        {job.nextScheduledAt ? new Date(job.nextScheduledAt).toLocaleString() : "n/a"}
                      </td>
                      <td className="px-3 py-2 text-slate-700 dark:text-neutral-200">{job.failureReason ?? "none"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}
          <div className="mt-4 flex items-center gap-3">
            <button
              type="button"
              className="ap-btn"
              onClick={async () => {
                const ok = await copyTextToClipboard(JSON.stringify(systemDiagnosticsSnapshot, null, 2));
                setSystemDiagnosticsMessage(ok ? "Diagnostics JSON copied." : "Could not copy diagnostics JSON.");
              }}
            >
              Copy diagnostics JSON
            </button>
            {systemDiagnosticsMessage ? (
              <p
                className="text-sm text-slate-600 dark:text-neutral-300"
                role="status"
                aria-live="polite"
              >
                {systemDiagnosticsMessage}
              </p>
            ) : null}
          </div>
          <details className="mt-3 overflow-hidden rounded-lg border border-slate-200 dark:border-neutral-700">
            <summary className="cursor-pointer bg-slate-50 px-3 py-2 text-sm font-semibold text-slate-700 dark:bg-neutral-800 dark:text-neutral-200">
              Raw diagnostics payload
            </summary>
            <pre className="max-h-72 overflow-auto bg-white px-3 py-2 text-xs text-slate-700 dark:bg-neutral-900 dark:text-neutral-200">
              {JSON.stringify(systemDiagnosticsSnapshot, null, 2)}
            </pre>
          </details>
        </>
      ) : (
        <p className="mt-2 text-sm text-slate-600 dark:text-neutral-300">
          Diagnostics are enabled but no payload is currently available.
        </p>
      )}
    </section>
  );
}
