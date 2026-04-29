"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import type { AlertSettings } from "../dashboardTypes";
import { useDashboardData } from "../DashboardDataContext";
import { buildScopedQuery } from "../dashboardQueryState";

export function AlertsContent() {
  const d = useDashboardData();
  const router = useRouter();
  const [formError, setFormError] = useState<string | null>(null);
  const [showFailedOnly, setShowFailedOnly] = useState(false);
  const form = d.alertSettings;

  const overview = d.overview;
  const requestCount = d.sparklineSeries.reduce(
    (sum, bucket) => sum + Number(bucket.request_count || 0),
    0,
  );
  const errorCount = d.sparklineSeries.reduce(
    (sum, bucket) => sum + Number(bucket.error_count || 0),
    0,
  );
  const displayRequestCount = requestCount || overview?.request_count || 0;
  const displayErrorCount = requestCount ? errorCount : overview?.error_count || 0;
  const displayErrorRate = displayRequestCount ? displayErrorCount / displayRequestCount : 0;
  const successfulRequests = d.operationalSignals.successfulRequests;
  const errorSpikeCandidate = d.operationalSignals.errorSpikeCandidate;
  const outageCandidate = d.operationalSignals.outageCandidate;
  const recentDispatches = d.recentAlertDispatches;
  const visibleDispatches = showFailedOnly
    ? recentDispatches.filter((dispatch) => dispatch.status === "failed")
    : recentDispatches;
  const diagnosisParams = buildScopedQuery({
    isAbsoluteWindow: d.isAbsoluteWindow,
    windowMinutes: d.windowMinutes,
    windowFromTimestamp: d.windowFromTimestamp,
    windowToTimestamp: d.windowToTimestamp,
    method: d.method,
    statusClass: d.statusClass,
    minLatencyMs: d.minLatencyMs,
    maxLatencyMs: d.maxLatencyMs,
    pathQuery: d.pathQuery,
    serverEnvironmentQuery: d.serverEnvironmentQuery,
    serverServiceQuery: d.serverServiceQuery,
    requestLimit: d.requestLimit,
    requestPage: 0,
    errorGroupLimit: d.errorGroupLimit,
    errorGroupPage: 0,
    errorGroupSort: d.errorGroupSort,
    sqlFilterApplied: d.sqlFilterApplied,
    sqlFilterEnabled: d.sqlFilterEnabled,
  }).toString();
  const diagnosisBaseHref = `/diagnosis?${diagnosisParams}`;

  const goToDiagnosisGrouped = () => {
    d.setErrorGroupSort("count");
    const groupedParams = new URLSearchParams(diagnosisParams);
    groupedParams.set("error_group_sort", "count");
    router.push(`/diagnosis?${groupedParams.toString()}#grouped-errors`);
  };

  const onSave = async () => {
    if (!form) {
      return;
    }
    if (form.error_spike_ratio_threshold < 0 || form.error_spike_ratio_threshold > 1) {
      setFormError("Error spike threshold must be between 0 and 1.");
      return;
    }
    const integerFields: Array<keyof AlertSettings> = [
      "error_spike_min_requests",
      "error_spike_window_minutes",
      "outage_min_requests",
      "outage_window_minutes",
      "cooldown_minutes",
    ];
    for (const field of integerFields) {
      if (Number(form[field]) < 1) {
        setFormError("Minute/request threshold fields must be at least 1.");
        return;
      }
    }
    setFormError(null);
    await d.saveAlertSettings(form);
  };

  return (
    <section className="rounded-2xl border border-slate-200/80 bg-white/95 p-5 shadow-sm dark:border-neutral-800 dark:bg-neutral-900">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-base font-semibold text-slate-800 dark:text-neutral-100">Operations (M5)</h2>
          <p className="mt-1 text-sm text-slate-500 dark:text-neutral-400">
            Preview backend heuristics and retention defaults. Live traffic details stay on{" "}
            <Link
              href="/dashboard"
              className="font-medium text-sky-700 underline-offset-2 hover:underline dark:text-neutral-300"
            >
              Dashboard
            </Link>{" "}
            and{" "}
            <Link
              href={diagnosisBaseHref}
              className="font-medium text-sky-700 underline-offset-2 hover:underline dark:text-neutral-300"
            >
              Errors &amp; Diagnosis
            </Link>
            .
          </p>
        </div>
        <span className="rounded-full bg-slate-100 px-2.5 py-1 text-sm font-medium text-slate-700 dark:bg-neutral-800 dark:text-neutral-200">
          Live alert settings mode
        </span>
      </div>
      <div className="mt-4 grid gap-4 lg:grid-cols-3">
        <div className="rounded-xl border border-slate-200/90 bg-slate-50/50 p-4 dark:border-neutral-700 dark:bg-neutral-800/60">
          <h3 className="text-sm font-semibold text-slate-700 dark:text-neutral-200">
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
          <p className="mt-3 text-sm text-slate-500 dark:text-neutral-400">
            Based on current window: {displayRequestCount} requests,{" "}
            {successfulRequests} successful,{" "}
            {(displayErrorRate * 100).toFixed(1)}% error rate.
          </p>
        </div>
        <div className="rounded-xl border border-slate-200/90 bg-slate-50/50 p-4 dark:border-neutral-700 dark:bg-neutral-800/60 lg:col-span-2">
          <h3 className="text-sm font-semibold text-slate-700 dark:text-neutral-200">
            Alert settings
          </h3>
          {form ? (
            <>
              <div className="mt-3 grid gap-3 sm:grid-cols-2">
                <label className="flex items-center gap-2 text-sm text-slate-700 dark:text-neutral-200">
                  <input
                    type="checkbox"
                    checked={form.enabled}
                    onChange={(event) =>
                      d.updateAlertSettingsDraft({ ...form, enabled: event.target.checked })
                    }
                  />
                  Alerts enabled
                </label>
                <label className="text-sm text-slate-700 dark:text-neutral-200">
                  Destination email
                  <input
                    type="email"
                    value={form.destination_email ?? ""}
                    onChange={(event) =>
                      d.updateAlertSettingsDraft({
                        ...form,
                        destination_email: event.target.value.trim() || null,
                      })
                    }
                    className="ap-input mt-1"
                    placeholder="ops@example.com"
                  />
                </label>
                <label className="text-sm text-slate-700 dark:text-neutral-200">
                  Error spike threshold (0-1)
                  <input
                    type="number"
                    min={0}
                    max={1}
                    step={0.01}
                    value={form.error_spike_ratio_threshold}
                    onChange={(event) =>
                      d.updateAlertSettingsDraft({
                        ...form,
                        error_spike_ratio_threshold: Number(event.target.value),
                      })
                    }
                    className="ap-input mt-1"
                  />
                </label>
                <label className="text-sm text-slate-700 dark:text-neutral-200">
                  Error spike min requests
                  <input
                    type="number"
                    min={1}
                    value={form.error_spike_min_requests}
                    onChange={(event) =>
                      d.updateAlertSettingsDraft({
                        ...form,
                        error_spike_min_requests: Number(event.target.value),
                      })
                    }
                    className="ap-input mt-1"
                  />
                </label>
                <label className="text-sm text-slate-700 dark:text-neutral-200">
                  Error spike window (minutes)
                  <input
                    type="number"
                    min={1}
                    value={form.error_spike_window_minutes}
                    onChange={(event) =>
                      d.updateAlertSettingsDraft({
                        ...form,
                        error_spike_window_minutes: Number(event.target.value),
                      })
                    }
                    className="ap-input mt-1"
                  />
                </label>
                <label className="text-sm text-slate-700 dark:text-neutral-200">
                  Outage min requests
                  <input
                    type="number"
                    min={1}
                    value={form.outage_min_requests}
                    onChange={(event) =>
                      d.updateAlertSettingsDraft({
                        ...form,
                        outage_min_requests: Number(event.target.value),
                      })
                    }
                    className="ap-input mt-1"
                  />
                </label>
                <label className="text-sm text-slate-700 dark:text-neutral-200">
                  Outage window (minutes)
                  <input
                    type="number"
                    min={1}
                    value={form.outage_window_minutes}
                    onChange={(event) =>
                      d.updateAlertSettingsDraft({
                        ...form,
                        outage_window_minutes: Number(event.target.value),
                      })
                    }
                    className="ap-input mt-1"
                  />
                </label>
                <label className="text-xs text-slate-700 dark:text-neutral-200">
                  Cooldown (minutes)
                  <input
                    type="number"
                    min={1}
                    value={form.cooldown_minutes}
                    onChange={(event) =>
                      d.updateAlertSettingsDraft({
                        ...form,
                        cooldown_minutes: Number(event.target.value),
                      })
                    }
                    className="ap-input mt-1 px-2 py-1 text-xs"
                  />
                </label>
              </div>
              <div className="mt-3 flex items-center gap-3">
                <button
                  type="button"
                  onClick={onSave}
                  disabled={d.alertSettingsSaving}
                  className="rounded-lg border border-sky-300 bg-sky-50 px-3 py-1.5 text-sm font-medium text-sky-900 shadow-sm transition-colors hover:bg-sky-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500/40 active:scale-[0.99] disabled:opacity-60 dark:border-sky-800 dark:bg-sky-950/50 dark:text-sky-100 dark:hover:bg-sky-900/40 dark:focus-visible:ring-neutral-500/50"
                >
                  {d.alertSettingsSaving ? "Saving..." : "Save alert settings"}
                </button>
                {formError ? (
                  <p className="text-xs text-rose-700 dark:text-rose-400">{formError}</p>
                ) : null}
                {d.alertSettingsMessage ? (
                  <p className="text-xs text-emerald-700 dark:text-emerald-400">
                    {d.alertSettingsMessage}
                  </p>
                ) : null}
              </div>
            </>
          ) : (
            <p className="mt-2 text-sm text-slate-500 dark:text-neutral-400">
              Loading alert settings...
            </p>
          )}
        </div>
        <div className="rounded-xl border border-slate-200/90 bg-slate-50/50 p-4 dark:border-neutral-700 dark:bg-neutral-800/60 lg:col-span-3">
          <div className="flex items-center justify-between gap-2">
            <h3 className="text-sm font-semibold text-slate-700 dark:text-neutral-200">
              Recent dispatched alerts
            </h3>
            <div className="flex items-center gap-2">
              <label className="flex items-center gap-1 text-xs text-slate-600 dark:text-neutral-300">
                <input
                  type="checkbox"
                  checked={showFailedOnly}
                  onChange={(event) => setShowFailedOnly(event.target.checked)}
                />
                Failed only
              </label>
              <span className="rounded-full bg-slate-200 px-2 py-0.5 text-xs font-medium text-slate-700 dark:bg-neutral-700 dark:text-neutral-200">
                {visibleDispatches.length} shown
              </span>
            </div>
          </div>
          {visibleDispatches.length === 0 ? (
            <p className="mt-2 text-sm text-slate-500 dark:text-neutral-400">
              No matching alerts in the selected time window.
            </p>
          ) : (
            <div className="mt-3 overflow-x-auto rounded-lg border border-slate-200 dark:border-neutral-700">
              <table className="min-w-full text-left text-xs">
                <thead className="bg-slate-100/80 text-slate-600 dark:bg-neutral-800 dark:text-neutral-300">
                  <tr>
                    <th className="px-3 py-2 font-semibold">Triggered</th>
                    <th className="px-3 py-2 font-semibold">Type</th>
                    <th className="px-3 py-2 font-semibold">Delivery</th>
                    <th className="px-3 py-2 font-semibold">Status</th>
                    <th className="px-3 py-2 font-semibold">Reason</th>
                    <th className="px-3 py-2 font-semibold">Destination</th>
                    <th className="px-3 py-2 font-semibold">Detail</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200 bg-white dark:divide-neutral-800 dark:bg-neutral-900">
                  {visibleDispatches.map((dispatch) => (
                    <tr key={dispatch.id}>
                      <td className="whitespace-nowrap px-3 py-2 text-slate-700 dark:text-neutral-200">
                        {new Date(dispatch.triggered_at).toLocaleString()}
                      </td>
                      <td className="px-3 py-2">
                        <span className="rounded-full bg-sky-500/10 px-2 py-0.5 font-medium text-sky-800 dark:text-sky-300">
                          {dispatch.alert_type}
                        </span>
                      </td>
                      <td className="px-3 py-2 text-slate-700 dark:text-neutral-200">
                        <div className="flex flex-col">
                          <span>{dispatch.delivered_via}</span>
                          {dispatch.provider_message_id ? (
                            <span className="text-[10px] text-slate-500 dark:text-neutral-400">
                              {dispatch.provider_message_id}
                            </span>
                          ) : null}
                        </div>
                      </td>
                      <td className="px-3 py-2">
                        <span
                          className={`rounded-full px-2 py-0.5 font-medium ${
                            dispatch.status === "sent"
                              ? "bg-emerald-500/15 text-emerald-800 dark:text-emerald-300"
                              : dispatch.status === "failed"
                                ? "bg-rose-500/15 text-rose-800 dark:text-rose-300"
                                : "bg-slate-300/30 text-slate-700 dark:text-neutral-300"
                          }`}
                        >
                          {dispatch.status}
                        </span>
                        {dispatch.delivered_at ? (
                          <div className="mt-1 text-[10px] text-slate-500 dark:text-neutral-400">
                            {new Date(dispatch.delivered_at).toLocaleString()}
                          </div>
                        ) : null}
                      </td>
                      <td className="px-3 py-2 text-slate-700 dark:text-neutral-200">
                        {dispatch.reason_message ?? dispatch.reason_code ?? "none"}
                      </td>
                      <td className="px-3 py-2 text-slate-700 dark:text-neutral-200">
                        {dispatch.destination_email ?? "not set"}
                      </td>
                      <td className="max-w-[380px] px-3 py-2 font-mono text-xs text-slate-700 dark:text-neutral-300">
                        {JSON.stringify(dispatch.detail)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
        <div className="rounded-xl border border-slate-200/90 bg-slate-50/50 p-4 dark:border-neutral-700 dark:bg-neutral-800/60 lg:col-span-3">
          <h3 className="text-sm font-semibold text-slate-700 dark:text-neutral-200">
            Runbook shortcuts
          </h3>
          <p className="mt-2 text-sm leading-snug text-slate-600 dark:text-neutral-300">
            Run from the backend package root. Copy commands or jump to grouped errors on Errors &amp; Diagnosis.
          </p>
          <div className="mt-3 flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => d.copyRunbookCommand(d.RUNBOOK_ALERTS_CMD, "Alerts job command")}
              className="ap-btn"
            >
              Copy alerts-once
            </button>
            <button
              type="button"
              onClick={() => d.copyRunbookCommand(d.RUNBOOK_RETENTION_CMD, "Retention job command")}
              className="ap-btn"
            >
              Copy retention-once
            </button>
            <button
              type="button"
              onClick={goToDiagnosisGrouped}
              className="rounded-lg border border-sky-300 bg-sky-50 px-3 py-1.5 text-sm font-medium text-sky-900 shadow-sm transition-colors hover:bg-sky-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500/40 active:scale-[0.99] dark:border-sky-800 dark:bg-sky-950/50 dark:text-sky-100 dark:hover:bg-sky-900/40 dark:focus-visible:ring-neutral-500/50"
            >
              Sort errors by count, open Errors &amp; Diagnosis
            </button>
          </div>
          <pre className="mt-3 max-h-24 overflow-auto rounded-md bg-slate-900/90 p-2.5 font-mono text-xs leading-relaxed text-slate-100">
            {d.RUNBOOK_ALERTS_CMD}
          </pre>
          <p className="mt-2 text-sm leading-snug text-slate-600 dark:text-neutral-300">
            If the command prints <span className="font-semibold text-slate-800">0</span>, the job still
            ran successfully: it means no error-spike or outage rule dispatched an alert for any project in
            this pass (often no qualifying traffic yet, cooldown, or{" "}
            <code className="rounded bg-slate-200 px-1">ALERTS_ENABLED=false</code>).
          </p>
          <pre className="mt-2 max-h-24 overflow-auto rounded-md bg-slate-900/90 p-2.5 font-mono text-xs leading-relaxed text-slate-100">
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
