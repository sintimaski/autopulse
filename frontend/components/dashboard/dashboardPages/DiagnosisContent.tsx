"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useLayoutEffect } from "react";

import { formatTimestamp } from "../dashboardTypes";
import { useDashboardData } from "../DashboardDataContext";
import { ExpandableTableRow } from "../ExpandableTableRow";

export function DiagnosisContent() {
  const d = useDashboardData();
  const pathname = usePathname();
  const requests = d.requests;
  const errorGroups = d.errorGroups;
  const timeline = d.diagnosisTimeline;
  const failures = d.diagnosisFailures;
  const groupEvents = d.diagnosisErrorGroupEvents;

  useLayoutEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    if (pathname === "/diagnosis" && window.location.hash === "#grouped-errors") {
      document.getElementById("grouped-errors")?.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }, [pathname]);

  if (!requests || !errorGroups || !timeline || !failures) {
    return null;
  }

  return (
    <>
      <section className="grid gap-4 lg:grid-cols-3">
        <article className="rounded-2xl border border-slate-200/80 bg-white/95 p-4 shadow-sm dark:border-neutral-800 dark:bg-neutral-900">
          <h2 className="text-sm font-semibold text-slate-800 dark:text-neutral-100">Incident summary</h2>
          <p className="mt-2 text-2xl font-semibold tabular-nums text-slate-900 dark:text-neutral-100">
            {failures.items.reduce((sum, item) => sum + item.failure_count, 0)}
          </p>
          <p className="text-xs text-slate-500 dark:text-neutral-400">Total failures in selected window</p>
        </article>
        <article className="rounded-2xl border border-slate-200/80 bg-white/95 p-4 shadow-sm dark:border-neutral-800 dark:bg-neutral-900">
          <h2 className="text-sm font-semibold text-slate-800 dark:text-neutral-100">Timeline buckets</h2>
          <p className="mt-2 text-2xl font-semibold tabular-nums text-slate-900 dark:text-neutral-100">
            {timeline.buckets.length}
          </p>
          <p className="text-xs text-slate-500 dark:text-neutral-400">Minute buckets with traffic</p>
        </article>
        <article className="rounded-2xl border border-slate-200/80 bg-white/95 p-4 shadow-sm dark:border-neutral-800 dark:bg-neutral-900">
          <h2 className="text-sm font-semibold text-slate-800 dark:text-neutral-100">Error groups</h2>
          <p className="mt-2 text-2xl font-semibold tabular-nums text-slate-900 dark:text-neutral-100">
            {errorGroups.total}
          </p>
          <p className="text-xs text-slate-500 dark:text-neutral-400">Grouped diagnosis anchors</p>
        </article>
      </section>

      <section className="rounded-2xl border border-slate-200/80 bg-white/95 p-5 shadow-sm dark:border-neutral-800 dark:bg-neutral-900">
        <h2 className="text-base font-semibold text-slate-800 dark:text-neutral-100">Quick diagnosis</h2>
        <p className="mt-1 text-sm text-slate-500 dark:text-neutral-400">
          Recent grouped errors and top failing routes from the loaded request sample ({requests.limit} rows).
          Full request rows live on{" "}
          <Link href="/logs" className="font-medium text-sky-700 underline-offset-2 hover:underline dark:text-neutral-300">
            Logs
          </Link>
          .
        </p>
        <div className="mt-4 grid gap-4 lg:grid-cols-2">
          <div className="rounded-xl border border-slate-200/90 bg-slate-50/50 p-4 dark:border-neutral-700 dark:bg-neutral-800/60">
            <h3 className="text-sm font-semibold text-slate-700 dark:text-neutral-200">
              Recent errors
            </h3>
            {d.recentErrorsPreview.length === 0 ? (
              <p className="mt-2 text-sm text-slate-600 dark:text-neutral-300">None in this window.</p>
            ) : (
              <ul className="mt-2 space-y-2">
                {d.recentErrorsPreview.map((item) => (
                  <li key={item.group_key}>
                    <a
                      href="#grouped-errors"
                      className="block rounded-lg border border-transparent px-1 py-1 text-sm transition-colors hover:border-slate-200 hover:bg-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500/40 dark:hover:border-neutral-700 dark:hover:bg-neutral-900 dark:focus-visible:ring-neutral-500/50"
                    >
                      <span className="font-medium text-slate-900 dark:text-neutral-100">
                        {item.exception_type ?? "Error"}
                      </span>
                      <span className="text-slate-500 dark:text-neutral-400"> · </span>
                      <span className="font-mono text-xs text-slate-700 dark:text-neutral-300">
                        {item.path}
                      </span>
                      <span className="mt-0.5 block text-xs text-slate-500 dark:text-neutral-400">
                        {item.message
                          ? `${item.message.slice(0, 80)}${item.message.length > 80 ? "…" : ""}`
                          : "—"}{" "}
                        <span className="tabular-nums text-rose-700">×{item.count}</span>
                      </span>
                    </a>
                  </li>
                ))}
              </ul>
            )}
          </div>
          <div className="rounded-xl border border-slate-200/90 bg-slate-50/50 p-4 dark:border-neutral-700 dark:bg-neutral-800/60">
            <h3 className="text-sm font-semibold text-slate-700 dark:text-neutral-200">
              Top failing routes
            </h3>
            {d.topFailingRoutes.length === 0 ? (
              <p className="mt-2 text-sm text-slate-600 dark:text-neutral-300">No 5xx in loaded requests.</p>
            ) : (
              <ul className="mt-2 space-y-2">
                {d.topFailingRoutes.map(([path, count]) => (
                  <li
                    key={path}
                    className="flex items-start justify-between gap-2 text-sm text-slate-800 dark:text-neutral-200"
                  >
                    <span className="min-w-0 truncate font-mono text-xs">{path}</span>
                    <span className="shrink-0 tabular-nums font-semibold text-rose-700">{count}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      </section>

      <section className="grid gap-4 lg:grid-cols-2">
        <article className="rounded-2xl border border-slate-200/80 bg-white/95 p-5 shadow-sm dark:border-neutral-800 dark:bg-neutral-900">
          <h2 className="text-base font-semibold text-slate-800 dark:text-neutral-100">Causal timeline</h2>
          <div className="mt-3 space-y-2">
            {timeline.buckets.slice(-20).map((bucket) => (
              <div key={bucket.minute} className="flex items-center justify-between text-xs">
                <span className="text-slate-600 dark:text-neutral-300">{formatTimestamp(bucket.minute)}</span>
                <span className="tabular-nums text-slate-700 dark:text-neutral-200">
                  req {bucket.request_count} · err {bucket.error_count}
                </span>
              </div>
            ))}
          </div>
        </article>
        <article className="rounded-2xl border border-slate-200/80 bg-white/95 p-5 shadow-sm dark:border-neutral-800 dark:bg-neutral-900">
          <h2 className="text-base font-semibold text-slate-800 dark:text-neutral-100">Evidence panel</h2>
          <p className="mt-1 text-sm text-slate-500 dark:text-neutral-400">Top routes by failure count for fast pivots.</p>
          <ul className="mt-3 space-y-2">
            {failures.items.slice(0, 10).map((item) => (
              <li key={item.path} className="flex items-center justify-between gap-3 text-sm">
                <Link href={`/logs?path_contains=${encodeURIComponent(item.path)}`} className="truncate font-mono text-xs text-sky-700 hover:underline dark:text-neutral-300">
                  {item.path}
                </Link>
                <span className="tabular-nums text-rose-700 dark:text-rose-300">{item.failure_count}</span>
              </li>
            ))}
          </ul>
        </article>
      </section>

      <section
        id="grouped-errors"
        className="scroll-mt-28 rounded-2xl border border-slate-200/80 bg-white/95 p-5 shadow-sm dark:border-neutral-800 dark:bg-neutral-900"
      >
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <h2 className="text-base font-semibold text-slate-800 dark:text-neutral-100">Grouped errors</h2>
            <p className="mt-1 text-sm text-slate-500 dark:text-neutral-400">
              Same time window as overview. Full stack traces may contain sensitive data; scrub at the SDK.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <label className="flex flex-col gap-1 text-sm font-medium text-slate-600 dark:text-neutral-300">
              Sort by
              <select
                value={d.errorGroupSort}
                onChange={(e) => d.setErrorGroupSort(e.target.value as "last_seen" | "count")}
                className="min-w-[140px] rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm shadow-sm outline-none ring-sky-500/30 focus:ring-2 dark:border-neutral-700 dark:bg-neutral-800 dark:text-neutral-100 dark:ring-neutral-600/40 dark:focus:ring-neutral-500/50"
              >
                <option value="last_seen">Last seen</option>
                <option value="count">Count</option>
              </select>
            </label>
            <p className="text-sm text-slate-500 dark:text-neutral-400 sm:pb-2">
              Showing {d.displayedErrorGroups.length} of {errorGroups.total} groups
            </p>
          </div>
        </div>
        {errorGroups.items.length === 0 ? (
          <p className="mt-4 text-sm text-slate-600 dark:text-neutral-300">
            No grouped errors in this time window.
          </p>
        ) : (
          <div className="mt-4 overflow-x-auto rounded-xl border border-slate-200 dark:border-neutral-700">
            <table className="min-w-full text-left text-sm">
              <thead className="bg-slate-50 text-xs font-semibold uppercase tracking-wide text-slate-500 dark:bg-neutral-800 dark:text-neutral-300">
                <tr>
                  <th className="w-10 px-2 py-2" aria-label="Expand row" />
                  <th className="px-3 py-2">Exception</th>
                  <th className="px-3 py-2">Message</th>
                  <th className="px-3 py-2">Route</th>
                  <th className="px-3 py-2">Count</th>
                  <th className="px-3 py-2">First seen</th>
                  <th className="px-3 py-2">Last seen</th>
                  <th className="px-3 py-2">Sample stack</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 bg-white dark:divide-neutral-800 dark:bg-neutral-900">
                {d.displayedErrorGroups.map((item) => {
                  const rowId = `error-group|${item.group_key}`;
                  const open = d.expandedRequestIds.has(rowId);
                  return (
                    <ExpandableTableRow
                      key={item.group_key}
                      rowId={rowId}
                      open={open}
                      onToggle={d.toggleRequestRow}
                      colSpan={8}
                      summaryClassName="cursor-pointer border-l-2 border-transparent align-top hover:border-sky-500/80 hover:bg-slate-50/90 dark:hover:border-neutral-500 dark:hover:bg-neutral-800/90"
                      detailsRowClassName="bg-slate-50/95 dark:bg-neutral-900/95"
                      detailsCellClassName="px-4 py-3 text-xs text-slate-700 dark:text-neutral-300"
                      renderSummary={() => (
                        <>
                          <td className="px-3 py-2 font-medium text-slate-900 dark:text-neutral-100">
                            {item.exception_type ?? "(unknown)"}
                          </td>
                          <td className="max-w-[220px] truncate px-3 py-2 text-slate-700 dark:text-neutral-300 sm:max-w-md">
                            {item.message ?? "(no message)"}
                          </td>
                          <td className="max-w-[220px] truncate px-3 py-2 font-mono text-xs text-slate-800 dark:text-neutral-100 sm:max-w-md">
                            {item.path}
                          </td>
                          <td className="px-3 py-2 tabular-nums text-slate-700 dark:text-neutral-300">
                            {item.count}
                          </td>
                          <td className="whitespace-nowrap px-3 py-2 text-slate-600 dark:text-neutral-300">
                            {formatTimestamp(item.first_seen)}
                          </td>
                          <td className="whitespace-nowrap px-3 py-2 text-slate-600 dark:text-neutral-300">
                            {formatTimestamp(item.last_seen)}
                          </td>
                          <td className="px-3 py-2 text-xs text-slate-500 dark:text-neutral-400">
                            {item.sample_stack_trace ? "Stack trace available" : "No stack trace available"}
                          </td>
                        </>
                      )}
                      renderDetails={() => (
                        <dl className="grid gap-3 sm:grid-cols-2">
                          <div>
                            <dt className="font-semibold text-slate-500 dark:text-neutral-400">Group key</dt>
                            <dd className="mt-0.5 break-all font-mono text-xs text-slate-800 dark:text-neutral-200">
                              {item.group_key}
                            </dd>
                          </div>
                          <div>
                            <dt className="font-semibold text-slate-500 dark:text-neutral-400">Count</dt>
                            <dd className="mt-0.5 tabular-nums text-slate-900 dark:text-neutral-100">
                              {item.count}
                            </dd>
                          </div>
                          <div className="sm:col-span-2">
                            <dt className="font-semibold text-slate-500 dark:text-neutral-400">
                              Exception message
                            </dt>
                            <dd className="mt-0.5 break-words text-slate-900 dark:text-neutral-100">
                              {item.message ?? "(no message)"}
                            </dd>
                          </div>
                          <div className="sm:col-span-2">
                            <dt className="font-semibold text-slate-500 dark:text-neutral-400">
                              Sample stack trace
                            </dt>
                            {item.sample_stack_trace ? (
                              <pre className="mt-1 max-h-56 overflow-auto rounded-md bg-slate-950 p-2 text-xs leading-5 text-slate-100">
                                {item.sample_stack_trace}
                              </pre>
                            ) : (
                              <dd className="mt-0.5 text-slate-600 dark:text-neutral-300">
                                No stack trace (event had no exception payload).
                              </dd>
                            )}
                          </div>
                        </dl>
                      )}
                    />
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
        <div className="mt-4 flex items-center justify-between gap-3 border-t border-slate-100 pt-3 text-sm text-slate-600 dark:border-neutral-800 dark:text-neutral-300">
          <p>
            Page {d.errorGroupPage + 1} · Offset {d.errorGroupPage * d.errorGroupLimit}
          </p>
          <div className="flex items-center gap-2">
            <button
              type="button"
              disabled={d.errorGroupPage === 0}
              onClick={() => d.setErrorGroupPage((p) => Math.max(0, p - 1))}
              className="rounded-lg border border-slate-200 bg-white px-3 py-1.5 font-medium text-slate-700 transition-colors hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500/40 disabled:cursor-not-allowed disabled:opacity-50 dark:border-neutral-700 dark:bg-neutral-900 dark:text-neutral-200 dark:focus-visible:ring-neutral-500/50"
            >
              Prev
            </button>
            <button
              type="button"
              disabled={(d.errorGroupPage + 1) * d.errorGroupLimit >= errorGroups.total}
              onClick={() => d.setErrorGroupPage((p) => p + 1)}
              className="rounded-lg border border-slate-200 bg-white px-3 py-1.5 font-medium text-slate-700 transition-colors hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500/40 disabled:cursor-not-allowed disabled:opacity-50 dark:border-neutral-700 dark:bg-neutral-900 dark:text-neutral-200 dark:focus-visible:ring-neutral-500/50"
            >
              Next
            </button>
          </div>
        </div>
      </section>

      <section className="rounded-2xl border border-slate-200/80 bg-white/95 p-5 shadow-sm dark:border-neutral-800 dark:bg-neutral-900">
        <h2 className="text-base font-semibold text-slate-800 dark:text-neutral-100">Error-group event evidence</h2>
        {groupEvents && groupEvents.items.length > 0 ? (
          <ul className="mt-3 space-y-2">
            {groupEvents.items.slice(0, 8).map((event) => (
              <li key={event.id} className="rounded-lg border border-slate-100 bg-slate-50/80 px-3 py-2 text-xs dark:border-neutral-700 dark:bg-neutral-800/70">
                <p className="font-mono">{event.path}</p>
                <p className="mt-1 text-slate-600 dark:text-neutral-300">
                  {formatTimestamp(event.timestamp)} · {event.status_code} · {event.latency_ms.toFixed(1)} ms
                </p>
              </li>
            ))}
          </ul>
        ) : (
          <p className="mt-3 text-sm text-slate-600 dark:text-neutral-300">Select a busier window to load event evidence.</p>
        )}
      </section>
    </>
  );
}
