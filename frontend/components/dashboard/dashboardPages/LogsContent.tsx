"use client";

import Link from "next/link";
import { useMemo, useState } from "react";

import { buildCurrentScopedState, buildDiagnosisPageHref, type DashboardScopedQueryState } from "../dashboardQueryState";
import { formatTimestamp, GROUP_OPTIONS, statusTone, type GroupBy } from "../dashboardTypes";
import { useDashboardData } from "../DashboardDataContext";
import { useDashboardLogsSlice } from "../data/useDashboardSlices";
import { ExpandableTableRow } from "../ExpandableTableRow";
import { TagSelector } from "../TagSelector";

export function LogsContent() {
  const d = useDashboardData();
  const logsSlice = useDashboardLogsSlice();
  const [rowsPerGroup, setRowsPerGroup] = useState(100);
  const scopedState = useMemo(
    (): DashboardScopedQueryState =>
      buildCurrentScopedState({
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
        requestPage: d.requestPage,
        errorGroupLimit: d.errorGroupLimit,
        errorGroupPage: d.errorGroupPage,
        errorGroupSort: d.errorGroupSort,
        sqlFilterApplied: d.sqlFilterApplied,
        sqlFilterEnabled: d.sqlFilterEnabled,
      }),
    [
    d.isAbsoluteWindow,
    d.windowMinutes,
    d.windowFromTimestamp,
    d.windowToTimestamp,
    d.method,
    d.statusClass,
    d.minLatencyMs,
    d.maxLatencyMs,
    d.pathQuery,
    d.serverEnvironmentQuery,
    d.serverServiceQuery,
    d.requestLimit,
    d.requestPage,
    d.errorGroupLimit,
    d.errorGroupPage,
    d.errorGroupSort,
    d.sqlFilterApplied,
    d.sqlFilterEnabled,
    ],
  );
  const { filteredCount, errorRows, slowRows, p95LatencyMs } = useMemo(() => {
    const filteredCountInner = logsSlice.filteredSorted.length;
    const errorRowsInner = logsSlice.filteredSorted.filter((item) => item.status_code >= 500).length;
    const slowRowsInner = logsSlice.filteredSorted.filter((item) => item.latency_ms >= 300).length;
    if (filteredCountInner === 0) {
      return { filteredCount: 0, errorRows: 0, slowRows: 0, p95LatencyMs: 0 };
    }
    const sorted = [...logsSlice.filteredSorted].sort((a, b) => a.latency_ms - b.latency_ms);
    const idx = Math.min(sorted.length - 1, Math.max(0, Math.ceil(sorted.length * 0.95) - 1));
    return {
      filteredCount: filteredCountInner,
      errorRows: errorRowsInner,
      slowRows: slowRowsInner,
      p95LatencyMs: sorted[idx]?.latency_ms ?? 0,
    };
  }, [logsSlice.filteredSorted]);
  const requests = logsSlice.requests;
  if (!requests) {
    return (
      <section
        className="rounded-2xl border border-slate-200 bg-white/95 p-6 text-slate-700 shadow-sm dark:border-neutral-800 dark:bg-neutral-900 dark:text-neutral-200"
        role="status"
        aria-live="polite"
      >
        <h2 className="text-base font-semibold text-slate-800 dark:text-neutral-100">
          Requests are loading or missing
        </h2>
        <p className="mt-2 text-sm text-slate-600 dark:text-neutral-300">
          No request-log slice is available right now. Adjust the scope filters, refresh, or send
          a first event from the onboarding checklist.
        </p>
      </section>
    );
  }
  const serverWindowTotal = requests.total;
  const activeClientControls = d.envTags.size + d.serviceTags.size + (d.groupBy !== "none" ? 1 : 0);

  return (
    <>
      {d.errorMessage ? (
        <section
          className="rounded-xl border border-amber-200 bg-amber-50/80 px-4 py-3 text-sm text-amber-900 dark:border-amber-900/60 dark:bg-amber-950/30 dark:text-amber-100"
          role="status"
        >
          Some logs data may be stale: {d.errorMessage}
        </section>
      ) : null}
      <section className="rounded-2xl bg-white/95 p-6 shadow-sm ring-1 ring-slate-900/[0.06] dark:bg-neutral-900 dark:ring-white/[0.08]">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <h2 className="text-base font-semibold text-slate-900 dark:text-neutral-100">Request evidence flow</h2>
            <p className="mt-1 text-sm text-slate-500 dark:text-neutral-400">
              1) Scope in the header, 2) refine here, 3) open rows for request evidence.
            </p>
          </div>
          <button
            type="button"
            onClick={d.clearClientFilters}
            className="self-start rounded-lg border border-slate-200 bg-slate-50 px-3 py-1.5 text-sm font-medium text-slate-700 transition-colors hover:bg-slate-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-orange-500/40 dark:border-neutral-700 dark:bg-neutral-800 dark:text-neutral-200 dark:hover:bg-neutral-700 dark:focus-visible:ring-neutral-500/50"
          >
            Reset all filters
          </button>
        </div>

        <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <div className="rounded-xl border border-slate-200 bg-slate-50/80 p-3 dark:border-neutral-700 dark:bg-neutral-800/70">
            <p className="text-xs font-medium uppercase tracking-wide text-slate-500 dark:text-neutral-400">
              Loaded rows
            </p>
            <p className="mt-1 text-2xl font-semibold tracking-tight text-slate-900 dark:text-neutral-100">
              {filteredCount}
            </p>
            <p className="mt-1 text-xs text-slate-500 dark:text-neutral-400">From {serverWindowTotal} in window</p>
          </div>
          <div className="rounded-xl border border-red-200/70 bg-red-50/70 p-3 dark:border-red-900/40 dark:bg-red-950/20">
            <p className="text-xs font-medium uppercase tracking-wide text-red-600 dark:text-red-300">
              Errors (5xx)
            </p>
            <p className="mt-1 text-2xl font-semibold tracking-tight text-red-700 dark:text-red-200">{errorRows}</p>
            <p className="mt-1 text-xs text-red-600/80 dark:text-red-300/80">Prioritize these first</p>
          </div>
          <div className="rounded-xl bg-orange-50/70 p-3 ring-1 ring-orange-500/12 dark:bg-orange-950/25 dark:ring-orange-400/20">
            <p className="text-xs font-medium uppercase tracking-wide text-orange-800 dark:text-orange-200">
              Slow (300ms+)
            </p>
            <p className="mt-1 text-2xl font-semibold tracking-tight text-orange-900 dark:text-orange-100">
              {slowRows}
            </p>
            <p className="mt-1 text-xs text-orange-800/85 dark:text-orange-200/85">Worth a quick look</p>
          </div>
          <div className="rounded-xl border border-slate-200 bg-slate-50/80 p-3 dark:border-neutral-700 dark:bg-neutral-800/70">
            <p className="text-xs font-medium uppercase tracking-wide text-slate-500 dark:text-neutral-400">
              p95 latency
            </p>
            <p className="mt-1 text-2xl font-semibold tracking-tight text-slate-900 dark:text-neutral-100">
              {p95LatencyMs.toFixed(1)} ms
            </p>
            <p className="mt-1 text-xs text-slate-500 dark:text-neutral-400">On the currently visible set</p>
          </div>
        </div>

        <div className="mt-4 rounded-xl border border-slate-200/90 bg-slate-50/70 p-4 dark:border-neutral-700 dark:bg-neutral-800/70">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="text-sm font-semibold text-slate-700 dark:text-neutral-200">
              Local view controls
            </p>
            <span className="rounded-full bg-slate-200 px-2 py-0.5 text-xs font-medium text-slate-700 dark:bg-neutral-700 dark:text-neutral-200">
              {activeClientControls} active
            </span>
          </div>
          <div className="mt-3 grid gap-4 lg:grid-cols-[220px_1fr_1fr]">
            <label className="flex flex-col gap-1 text-xs font-medium text-slate-600 dark:text-neutral-300">
              Group rows by
              <select
                value={d.groupBy}
                onChange={(e) => d.setGroupBy(e.target.value as GroupBy)}
                className="ap-select"
              >
                {GROUP_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </label>

            <TagSelector
              id="logs-environment-tags"
              label="Environment tags"
              options={d.availableEnvironments}
              selected={d.envTags}
              onToggle={d.toggleEnv}
              emptyText="No environment tags in this slice."
              accent="sky"
            />
            <TagSelector
              id="logs-service-tags"
              label="Service tags"
              options={d.availableServices}
              selected={d.serviceTags}
              onToggle={d.toggleService}
              emptyText="No service tags in this slice."
              accent="violet"
            />
          </div>
        </div>
      </section>

      <section className="rounded-2xl bg-white/95 p-6 shadow-sm ring-1 ring-slate-900/[0.06] dark:bg-neutral-900 dark:ring-white/[0.08]">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <h2 className="text-base font-semibold text-slate-800 dark:text-neutral-100">Request rows</h2>
          <p className="text-sm text-slate-500 dark:text-neutral-400">
            Showing <span className="font-semibold text-slate-800 dark:text-neutral-100">{d.filteredSorted.length}</span> of{" "}
            {d.rawItems.length} loaded (total in window: {requests.total})
          </p>
        </div>

        {d.rawItems.length === 0 ? (
          <p className="mt-6 text-sm text-slate-600 dark:text-neutral-300">
            No requests in this time window yet. Send traffic to{" "}
            <code className="rounded bg-slate-100 px-1 dark:bg-neutral-800 dark:text-neutral-200">
              POST /ingest
            </code> or run the manual test script,
            then refresh.
          </p>
        ) : d.filteredSorted.length === 0 ? (
          <p className="mt-6 text-sm text-slate-600 dark:text-neutral-300">
            No rows match your client filters. Clear filters or widen the time window.
          </p>
        ) : (
          <div className="mt-4 space-y-6">
            {d.grouped.map((group) => (
              <div key={group.key}>
                {d.groupBy !== "none" && (
                  <h3 className="mb-2 flex items-center gap-2 text-sm font-semibold text-slate-700 dark:text-neutral-200">
                    <span className="rounded-md bg-slate-100 px-2 py-0.5 text-xs text-slate-600 dark:bg-neutral-800 dark:text-neutral-300">
                      {GROUP_OPTIONS.find((g) => g.value === d.groupBy)?.label}
                    </span>
                    <span className="text-slate-900 dark:text-neutral-100">{group.label}</span>
                    <span className="font-normal text-slate-500 dark:text-neutral-400">
                      ({group.items.length})
                    </span>
                  </h3>
                )}
                <div className="overflow-x-auto rounded-xl border border-slate-200 dark:border-neutral-700">
                  <table className="min-w-full text-left text-sm">
                    <thead className="sticky top-0 bg-slate-50 text-xs font-semibold uppercase tracking-wide text-slate-500 dark:bg-neutral-800 dark:text-neutral-400">
                      <tr>
                        <th className="w-10 px-2 py-2" aria-label="Expand row" />
                        {(
                          [
                            ["timestamp", "Time"],
                            ["method", "Method"],
                            ["path", "Path"],
                            ["log_message", "Message"],
                            ["status_code", "Status"],
                            ["latency_ms", "Latency"],
                            ["service_name", "Service"],
                            ["environment", "Env"],
                          ] as const
                        ).map(([key, label]) => (
                          <th
                            key={key}
                            className="px-3 py-2"
                            aria-sort={
                              d.sortKey === key ? (d.sortDir === "asc" ? "ascending" : "descending") : "none"
                            }
                          >
                            <button
                              type="button"
                              onClick={() => d.onSortHeader(key)}
                              className="inline-flex min-h-8 items-center gap-1 rounded-md px-2 py-1 transition-colors hover:bg-slate-200/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-orange-500/40 dark:hover:bg-neutral-700/80 dark:focus-visible:ring-neutral-500/50"
                            >
                              {label}
                              {d.sortKey === key && (
                                <span className="text-orange-600 dark:text-orange-400" aria-hidden>
                                  {d.sortDir === "asc" ? "↑" : "↓"}
                                </span>
                              )}
                            </button>
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 bg-white dark:divide-neutral-800 dark:bg-neutral-950">
                      {group.items.slice(0, rowsPerGroup).map((item, rowIndex) => {
                        const rowId = [
                          group.key,
                          String(rowIndex),
                          item.timestamp,
                          item.method,
                          item.path,
                          String(item.status_code),
                          String(item.latency_ms),
                          item.service_name,
                          item.environment,
                          item.log_message ?? "",
                        ].join("|");
                        const open = d.expandedRequestIds.has(rowId);
                        return (
                          <ExpandableTableRow
                            key={rowId}
                            rowId={rowId}
                            open={open}
                            onToggle={d.toggleRequestRow}
                            colSpan={9}
                            summaryClassName="cursor-pointer border-l-2 border-transparent hover:border-orange-500/70 hover:bg-slate-50/90 dark:hover:border-neutral-500 dark:hover:bg-neutral-800/90"
                            detailsRowClassName="bg-slate-50/95 dark:bg-neutral-900/95"
                            detailsCellClassName="px-4 py-3 text-xs text-slate-700 dark:text-neutral-300"
                            renderSummary={() => (
                              <>
                              <td className="whitespace-nowrap px-3 py-2 text-slate-600 dark:text-neutral-300">
                                {formatTimestamp(item.timestamp)}
                              </td>
                              <td className="px-3 py-2">
                                <span className="rounded-md bg-slate-100 px-2 py-0.5 text-xs font-semibold text-slate-800 dark:bg-neutral-800 dark:text-neutral-100">
                                  {item.method}
                                </span>
                              </td>
                              <td className="max-w-[220px] truncate px-3 py-2 font-mono text-xs text-slate-800 dark:text-neutral-200 sm:max-w-md">
                                {item.path}
                              </td>
                              <td className="max-w-[180px] truncate px-3 py-2 text-xs text-slate-600 dark:text-neutral-300 sm:max-w-sm">
                                {item.log_message?.trim()
                                  ? item.log_message.length > 120
                                    ? `${item.log_message.slice(0, 120)}…`
                                    : item.log_message
                                  : "—"}
                              </td>
                              <td className="px-3 py-2">
                                <span
                                  className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-semibold ring-1 ring-inset ${statusTone(item.status_code)}`}
                                >
                                  {item.status_code}
                                </span>
                              </td>
                              <td className="whitespace-nowrap px-3 py-2 tabular-nums text-slate-700 dark:text-neutral-300">
                                {item.latency_ms.toFixed(1)} ms
                              </td>
                              <td className="px-3 py-2 text-slate-700 dark:text-neutral-300">{item.service_name}</td>
                              <td className="px-3 py-2">
                                <span className="rounded-full bg-neutral-200/80 px-2 py-0.5 text-xs font-medium text-neutral-900 ring-1 ring-neutral-400/35 dark:bg-neutral-800 dark:text-neutral-100 dark:ring-neutral-600/50">
                                  {item.environment}
                                </span>
                              </td>
                              </>
                            )}
                            renderDetails={() => {
                              const statusClassForDiagnosis =
                                item.status_code >= 500 ? "5" : item.status_code >= 400 ? "4" : "ALL";
                              const diagnosisHref = buildDiagnosisPageHref(
                                scopedState,
                                {
                                  pathQuery: item.path,
                                  statusClass: statusClassForDiagnosis,
                                },
                                "#grouped-errors",
                              );
                              return (
                              <>
                                <dl className="grid gap-3 sm:grid-cols-2">
                                  <div>
                                    <dt className="font-semibold text-slate-500 dark:text-neutral-400">
                                      Request id
                                    </dt>
                                    <dd className="mt-0.5 break-all font-mono text-slate-900 dark:text-neutral-100">
                                      {item.request_id ?? "— (not reported by SDK)"}
                                    </dd>
                                  </div>
                                  <div>
                                    <dt className="font-semibold text-slate-500 dark:text-neutral-400">
                                      Timestamp (ISO)
                                    </dt>
                                    <dd className="mt-0.5 break-all font-mono text-slate-900 dark:text-neutral-100">
                                      {item.timestamp}
                                    </dd>
                                  </div>
                                  <div className="sm:col-span-2">
                                    <dt className="font-semibold text-slate-500 dark:text-neutral-400">Path</dt>
                                    <dd className="mt-0.5 break-all font-mono text-[13px] text-slate-900 dark:text-neutral-100">
                                      {item.path}
                                    </dd>
                                  </div>
                                  <div className="sm:col-span-2">
                                    <dt className="font-semibold text-slate-500 dark:text-neutral-400">
                                      Log / error message
                                    </dt>
                                    <dd className="mt-0.5 break-words text-slate-900 dark:text-neutral-100">
                                      {item.log_message?.trim() ? item.log_message : "—"}
                                    </dd>
                                  </div>
                                  <div>
                                    <dt className="font-semibold text-slate-500 dark:text-neutral-400">Status</dt>
                                    <dd className="mt-0.5 tabular-nums text-slate-900 dark:text-neutral-100">
                                      {item.status_code}
                                    </dd>
                                  </div>
                                  <div>
                                    <dt className="font-semibold text-slate-500 dark:text-neutral-400">Latency</dt>
                                    <dd className="mt-0.5 tabular-nums text-slate-900 dark:text-neutral-100">
                                      {item.latency_ms.toFixed(3)} ms
                                    </dd>
                                  </div>
                                  <div>
                                    <dt className="font-semibold text-slate-500 dark:text-neutral-400">Service</dt>
                                    <dd className="mt-0.5 text-slate-900 dark:text-neutral-100">{item.service_name}</dd>
                                  </div>
                                  <div>
                                    <dt className="font-semibold text-slate-500 dark:text-neutral-400">
                                      Environment
                                    </dt>
                                    <dd className="mt-0.5 text-slate-900 dark:text-neutral-100">{item.environment}</dd>
                                  </div>
                                </dl>
                                <div className="mt-4 border-t border-slate-200 pt-3 dark:border-neutral-700">
                                  <Link
                                    href={diagnosisHref}
                                    className="text-sm font-medium text-orange-600 underline-offset-2 hover:underline dark:text-orange-400"
                                  >
                                    {item.status_code >= 500
                                      ? "Open errors and diagnosis (5xx on this route)"
                                      : item.status_code >= 400
                                        ? "Open errors and diagnosis (4xx on this route)"
                                        : "Open errors and diagnosis for this route"}
                                  </Link>
                                </div>
                              </>
                              );
                            }}
                          />
                        );
                      })}
                    </tbody>
                  </table>
                </div>
                {group.items.length > rowsPerGroup ? (
                  <div className="mt-2">
                    <button
                      type="button"
                      onClick={() => setRowsPerGroup((prev) => prev + 100)}
                      className="rounded-md border border-slate-200 bg-slate-50 px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-100 dark:border-neutral-700 dark:bg-neutral-800 dark:text-neutral-200 dark:hover:bg-neutral-700"
                    >
                      Load 100 more rows in this group
                    </button>
                  </div>
                ) : null}
              </div>
            ))}
          </div>
        )}
        <div className="mt-4 flex items-center justify-between gap-3 border-t border-slate-100 pt-3 text-sm text-slate-600 dark:border-neutral-800 dark:text-neutral-300">
          <p>
            Page {d.requestPage + 1} · Offset {d.requestPage * d.requestLimit}
          </p>
          <div className="flex items-center gap-2">
            <button
              type="button"
              disabled={d.requestPage === 0}
              onClick={() => d.setRequestPage((p) => Math.max(0, p - 1))}
              className="ap-btn"
            >
              Prev
            </button>
            <button
              type="button"
              disabled={(d.requestPage + 1) * d.requestLimit >= requests.total}
              onClick={() => d.setRequestPage((p) => p + 1)}
              className="ap-btn"
            >
              Next
            </button>
          </div>
        </div>
      </section>
    </>
  );
}
