"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";

import { useDashboardData } from "../DashboardDataContext";

export function AlertsContent() {
  const d = useDashboardData();
  const overview = d.overview;
  const router = useRouter();

  if (!overview) {
    return null;
  }
  const requestCount = d.sparklineSeries.reduce(
    (sum, bucket) => sum + Number(bucket.request_count || 0),
    0,
  );
  const errorCount = d.sparklineSeries.reduce(
    (sum, bucket) => sum + Number(bucket.error_count || 0),
    0,
  );
  const displayRequestCount = requestCount || overview.request_count;
  const displayErrorCount = requestCount ? errorCount : overview.error_count;
  const displayErrorRate = displayRequestCount ? displayErrorCount / displayRequestCount : 0;
  const successfulRequests = Math.max(displayRequestCount - displayErrorCount, 0);
  const errorSpikeCandidate =
    displayRequestCount >= d.M5_ALERT_DEFAULTS.errorSpikeMinRequests &&
    displayErrorRate >= d.M5_ALERT_DEFAULTS.errorSpikeRatioThreshold;
  const outageCandidate =
    displayRequestCount >= d.M5_ALERT_DEFAULTS.outageMinRequests && successfulRequests === 0;

  const goToDiagnosisGrouped = () => {
    d.setErrorGroupSort("count");
    router.push("/diagnosis#grouped-errors");
  };

  return (
    <section className="rounded-2xl border border-slate-200/80 bg-white/95 p-5 shadow-sm dark:border-neutral-800 dark:bg-neutral-900">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-sm font-semibold text-slate-800 dark:text-neutral-100">Operations (M5)</h2>
          <p className="mt-1 text-xs text-slate-500 dark:text-neutral-400">
            Frontend preview of backend alert heuristics and retention defaults. Live traffic and errors
            stay on{" "}
            <Link
              href="/dashboard"
              className="font-medium text-sky-700 underline-offset-2 hover:underline dark:text-neutral-300"
            >
              Dashboard
            </Link>{" "}
            and{" "}
            <Link
              href="/diagnosis"
              className="font-medium text-sky-700 underline-offset-2 hover:underline dark:text-neutral-300"
            >
              Diagnosis
            </Link>
            .
          </p>
        </div>
        <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-700 dark:bg-neutral-800 dark:text-neutral-200">
          Heuristic-only mode
        </span>
      </div>
      <p className="mt-3 text-xs text-slate-500 dark:text-neutral-400">
        In-app alert settings (enabled, destination email, thresholds) require dedicated backend
        project-settings endpoints. This page intentionally surfaces live heuristics and runbook actions
        only for MVP.
      </p>
      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <div className="rounded-xl border border-slate-200/90 bg-slate-50/50 p-4 dark:border-neutral-700 dark:bg-neutral-800/60">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-600 dark:text-neutral-300">
            Alert heuristic preview
          </h3>
          <ul className="mt-3 space-y-2 text-sm text-slate-700 dark:text-neutral-200">
            <li className="flex items-start justify-between gap-3">
              <span>Error spike candidate</span>
              <span
                className={`rounded-full px-2 py-0.5 text-xs font-semibold ${
                  errorSpikeCandidate
                    ? "bg-rose-500/15 text-rose-800"
                    : "bg-emerald-500/15 text-emerald-800"
                }`}
              >
                {errorSpikeCandidate ? "Likely trigger" : "Within threshold"}
              </span>
            </li>
            <li className="flex items-start justify-between gap-3">
              <span>Possible outage candidate</span>
              <span
                className={`rounded-full px-2 py-0.5 text-xs font-semibold ${
                  outageCandidate
                    ? "bg-rose-500/15 text-rose-800"
                    : "bg-emerald-500/15 text-emerald-800"
                }`}
              >
                {outageCandidate ? "Likely trigger" : "No outage signal"}
              </span>
            </li>
          </ul>
          <p className="mt-3 text-xs text-slate-500 dark:text-neutral-400">
            Based on current window: {displayRequestCount} requests,{" "}
            {successfulRequests} successful,{" "}
            {(displayErrorRate * 100).toFixed(1)}% error rate.
          </p>
        </div>
        <div className="rounded-xl border border-slate-200/90 bg-slate-50/50 p-4 dark:border-neutral-700 dark:bg-neutral-800/60">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-600 dark:text-neutral-300">
            Runbook shortcuts
          </h3>
          <p className="mt-2 text-[11px] leading-snug text-slate-600 dark:text-neutral-300">
            Run from the backend package root with your virtualenv. Use the buttons to copy commands, or
            jump to grouped errors on Diagnosis sorted by count.
          </p>
          <div className="mt-3 flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => d.copyRunbookCommand(d.RUNBOOK_ALERTS_CMD, "Alerts job command")}
              className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-800 shadow-sm transition hover:bg-slate-50 dark:border-neutral-600 dark:bg-neutral-900 dark:text-neutral-100 dark:hover:bg-neutral-800"
            >
              Copy alerts-once
            </button>
            <button
              type="button"
              onClick={() => d.copyRunbookCommand(d.RUNBOOK_RETENTION_CMD, "Retention job command")}
              className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-800 shadow-sm transition hover:bg-slate-50 dark:border-neutral-600 dark:bg-neutral-900 dark:text-neutral-100 dark:hover:bg-neutral-800"
            >
              Copy retention-once
            </button>
            <button
              type="button"
              onClick={goToDiagnosisGrouped}
              className="rounded-lg border border-sky-300 bg-sky-50 px-3 py-1.5 text-xs font-medium text-sky-900 shadow-sm transition hover:bg-sky-100 dark:border-neutral-600 dark:bg-neutral-800 dark:text-neutral-100 dark:hover:bg-neutral-700"
            >
              Sort errors by count, open Diagnosis
            </button>
          </div>
          <pre className="mt-3 max-h-24 overflow-auto rounded-md bg-slate-900/90 p-2.5 font-mono text-[11px] leading-relaxed text-slate-100">
            {d.RUNBOOK_ALERTS_CMD}
          </pre>
          <p className="mt-2 text-[11px] leading-snug text-slate-600 dark:text-neutral-300">
            If the command prints <span className="font-semibold text-slate-800">0</span>, the job still
            ran successfully: it means no error-spike or outage rule dispatched an alert for any project in
            this pass (often no qualifying traffic yet, cooldown, or{" "}
            <code className="rounded bg-slate-200 px-1">ALERTS_ENABLED=false</code>).
          </p>
          <pre className="mt-2 max-h-24 overflow-auto rounded-md bg-slate-900/90 p-2.5 font-mono text-[11px] leading-relaxed text-slate-100">
            {d.RUNBOOK_RETENTION_CMD}
          </pre>
          <p className="mt-3 text-xs text-slate-600 dark:text-neutral-300">
            Raw events retention target: {d.M5_ALERT_DEFAULTS.retentionRawDays} days.
          </p>
          {d.runbookMessage ? (
            <p
              className="mt-2 text-xs font-medium text-emerald-800 dark:text-emerald-400"
              role="status"
              aria-live="polite"
            >
              {d.runbookMessage}
            </p>
          ) : null}
        </div>
      </div>
    </section>
  );
}
