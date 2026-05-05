"use client";

import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import { useEffect, useLayoutEffect, useMemo, useState } from "react";

import {
  buildCurrentScopedState,
  buildRequestsPageHref,
  type DashboardScopedQueryState,
} from "../dashboardQueryState";
import { DashboardDetailModal } from "../DashboardDetailModal";
import { ErrorGroupEvidenceBody } from "../ErrorGroupEvidenceBody";
import { SaveBookmarkModal } from "../SaveBookmarkModal";
import { toDashboardRoutePath } from "../dashboardRoutePath";
import { formatTimestamp, type ErrorGroupItem } from "../dashboardTypes";
import { useDashboardData } from "../DashboardDataContext";
import { useDashboardDiagnosisSlice } from "../data/useDashboardSlices";
import { ExpandableTableRow } from "../ExpandableTableRow";
import { RowActionsMenu } from "../RowActionsMenu";
import { InlineDataSpinner } from "../../ui/InlineDataSpinner";
import { GuidedTroubleshootingPanel } from "../GuidedTroubleshootingPanel";
import { RecentJobFailuresStrip } from "../RecentJobFailuresStrip";
import { DiagnosisRequestsStickyScopeBar } from "../DiagnosisRequestsStickyScopeBar";
import { MetricCard } from "../MetricCard";
import { buildErrorGroupEvidenceMenuItems } from "../errorGroupEvidenceMenu";

export function DiagnosisContent() {
  const d = useDashboardData();
  const diagnosisSlice = useDashboardDiagnosisSlice();
  const pathname = usePathname();
  const routePath = useMemo(() => toDashboardRoutePath(pathname), [pathname]);
  const searchParams = useSearchParams();
  const queryStringForBookmarks = searchParams.toString();
  const [errorModalItem, setErrorModalItem] = useState<ErrorGroupItem | null>(null);
  const [bookmarkDraft, setBookmarkDraft] = useState<{ title: string; hashFragment: string } | null>(null);
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
  const requests = d.requests;
  const errorGroups = diagnosisSlice.errorGroups;
  const timeline = diagnosisSlice.diagnosisTimeline;
  const failures = diagnosisSlice.diagnosisFailures;
  const groupEvents = diagnosisSlice.diagnosisErrorGroupEvents;

  useLayoutEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    if (pathname === "/diagnosis" && window.location.hash === "#grouped-errors") {
      document.getElementById("grouped-errors")?.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }, [pathname]);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    const hash = window.location.hash;
    if (!hash.startsWith("#error-group:")) {
      return;
    }
    const encoded = hash.slice("#error-group:".length);
    if (!encoded) {
      return;
    }
    let decodedGroupKey = "";
    try {
      decodedGroupKey = decodeURIComponent(encoded);
    } catch {
      return;
    }
    const rowId = `error-group|${decodedGroupKey}`;
    const exists = d.displayedErrorGroups.some((group) => group.group_key === decodedGroupKey);
    if (!exists) {
      return;
    }
    if (!d.expandedRequestIds.has(rowId)) {
      d.toggleRequestRow(rowId);
    }
  }, [d]);

  if (!requests || !errorGroups || !timeline || !failures) {
    if (d.loading && !d.errorMessage) {
      return (
        <>
          <DiagnosisRequestsStickyScopeBar />
          <InlineDataSpinner label="Loading diagnosis…" className="rounded-2xl" />
        </>
      );
    }
    const missing = [
      !requests ? "requests" : null,
      !errorGroups ? "errorGroups" : null,
      !timeline ? "timeline" : null,
      !failures ? "failures" : null,
    ].filter((entry): entry is string => entry !== null);
    return (
      <>
        <DiagnosisRequestsStickyScopeBar />
        <section
        className="rounded-2xl border border-slate-200 bg-white/95 p-6 text-slate-700 shadow-sm dark:border-neutral-800 dark:bg-neutral-900 dark:text-neutral-200"
        role="status"
        aria-live="polite"
      >
        <h2 className="text-base font-semibold text-slate-800 dark:text-neutral-100">
          Diagnosis needs data for this scope
        </h2>
        <p className="mt-2 text-sm text-slate-600 dark:text-neutral-300">
          {d.errorMessage ?? (
            <>
              The diagnosis view needs recent traffic to rank incidents. Missing slices:{" "}
              <code className="rounded bg-slate-100 px-1 py-0.5 text-xs dark:bg-neutral-800">
                {missing.join(", ")}
              </code>
              .
            </>
          )}
        </p>
        <p className="mt-2 text-sm text-slate-600 dark:text-neutral-300">
          Once your app sends events, this view will populate automatically. You can also{" "}
          <Link
            href="/onboarding"
            className="font-medium text-sky-700 underline-offset-2 hover:underline dark:text-sky-300"
          >
            resume onboarding
          </Link>{" "}
          or{" "}
          <Link
            href={buildRequestsPageHref(scopedState)}
            className="font-medium text-sky-700 underline-offset-2 hover:underline dark:text-sky-300"
          >
            open Requests
          </Link>{" "}
          if evidence arrived outside this scope.
        </p>
      </section>
      </>
    );
  }

  return (
    <>
      <DiagnosisRequestsStickyScopeBar />
      {d.errorMessage ? (
        <section
          className="rounded-xl border border-amber-200 bg-amber-50/80 px-4 py-3 text-sm text-amber-900 dark:border-amber-900/60 dark:bg-amber-950/30 dark:text-amber-100"
          role="status"
        >
          Some diagnosis widgets may be stale: {d.errorMessage}
        </section>
      ) : null}
      <RecentJobFailuresStrip data={diagnosisSlice.recentJobFailures} />
      <section className="grid gap-4 lg:grid-cols-3">
        <MetricCard
          label="Incident summary"
          value={String(failures.items.reduce((sum, item) => sum + item.failure_count, 0))}
          helper="Failures in this window"
        />
        <MetricCard label="Timeline buckets" value={String(timeline.buckets.length)} helper="Minutes with traffic" />
        <MetricCard label="Error groups" value={String(errorGroups.total)} helper="Grouped anchors" />
      </section>

      <GuidedTroubleshootingPanel />

      <section className="rounded-2xl bg-white/95 p-6 shadow-sm ring-1 ring-slate-900/[0.06] dark:bg-neutral-900 dark:ring-white/[0.08]">
        <h2 className="text-base font-semibold tracking-tight text-slate-900 dark:text-neutral-50">Quick diagnosis</h2>
        <p className="mt-1.5 text-sm text-slate-600 dark:text-neutral-400">
          Recent grouped errors and top failing routes from the loaded request sample ({requests.limit} rows).
          Full request rows live on{" "}
          <Link
            href={buildRequestsPageHref(scopedState)}
            className="font-medium text-orange-600 underline-offset-2 hover:underline dark:text-orange-400"
          >
            Requests
          </Link>{" "}
          (same time window and filters).
        </p>
        <div className="mt-4 grid gap-4 lg:grid-cols-2">
          <div className="rounded-xl bg-slate-50/60 p-4 ring-1 ring-slate-900/[0.04] dark:bg-neutral-800/40 dark:ring-white/[0.05]">
            <h3 className="text-sm font-semibold text-slate-800 dark:text-neutral-100">Recent errors</h3>
            {d.recentErrorsPreview.length === 0 ? (
              <p className="mt-2 text-sm text-slate-600 dark:text-neutral-300">None in this window.</p>
            ) : (
              <ul className="mt-2 space-y-2">
                {d.recentErrorsPreview.map((item) => (
                  <li key={item.group_key}>
                    <div className="rounded-lg border border-transparent px-1 py-1 text-sm transition-colors hover:border-slate-200 hover:bg-white dark:hover:border-neutral-700 dark:hover:bg-neutral-900">
                      <a
                        href="#grouped-errors"
                        className="block focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-orange-500/45 dark:focus-visible:ring-orange-400/35"
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
                      <Link
                        href={buildRequestsPageHref(scopedState, {
                          pathQuery: item.path,
                          statusClass: "ALL",
                        })}
                        className="mt-1 inline-block text-xs font-medium text-orange-600 underline-offset-2 hover:underline dark:text-orange-400"
                      >
                        Request logs for this route
                      </Link>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>
          <div className="rounded-xl bg-slate-50/60 p-4 ring-1 ring-slate-900/[0.04] dark:bg-neutral-800/40 dark:ring-white/[0.05]">
            <h3 className="text-sm font-semibold text-slate-800 dark:text-neutral-100">Top failing routes</h3>
            {d.topFailingRoutes.length === 0 ? (
              <p className="mt-2 text-sm text-slate-600 dark:text-neutral-300">No 5xx in loaded requests.</p>
            ) : (
              <ul className="mt-2 space-y-2">
                {d.topFailingRoutes.map(([path, count]) => (
                  <li
                    key={path}
                    className="flex items-start justify-between gap-2 text-sm text-slate-800 dark:text-neutral-200"
                  >
                    <Link
                      href={buildRequestsPageHref(scopedState, { pathQuery: path, statusClass: "5" })}
                      className="min-w-0 truncate font-mono text-xs text-orange-600 underline-offset-2 hover:underline dark:text-orange-400"
                    >
                      {path}
                    </Link>
                    <span className="shrink-0 tabular-nums font-semibold text-rose-700">{count}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      </section>

      <section
        id="grouped-errors"
        className="scroll-mt-28 rounded-2xl bg-white/95 p-6 shadow-sm ring-1 ring-slate-900/[0.06] dark:bg-neutral-900 dark:ring-white/[0.08]"
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
                className="ap-select min-w-[140px]"
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
        {d.pathQuery.trim() ? (
          <div className="mt-4 flex flex-col gap-2 rounded-xl bg-orange-50/90 px-3 py-3 text-sm text-orange-950 ring-1 ring-orange-500/15 dark:bg-orange-950/30 dark:text-orange-50 dark:ring-orange-400/25">
            <p>
              <span className="font-semibold">Route filter on.</span> Groups match{" "}
              <code className="rounded bg-white/90 px-1.5 py-0.5 font-mono text-xs dark:bg-neutral-900/80">
                {d.pathQuery.trim()}
              </code>
              . Clear to list every group in this window.
            </p>
            <button
              type="button"
              onClick={() => {
                d.setPathQuery("");
                d.setErrorGroupPage(0);
              }}
              className="self-start rounded-lg bg-orange-600 px-3 py-1.5 text-xs font-medium text-white shadow-sm hover:bg-orange-500 dark:bg-orange-500 dark:hover:bg-orange-400"
            >
              Clear route filter
            </button>
          </div>
        ) : null}
        {errorGroups.items.length === 0 ? (
          <p className="mt-4 text-sm text-slate-600 dark:text-neutral-300">
            No grouped errors in this time window.
          </p>
        ) : (
          <div className="mt-4 max-w-full min-w-0 overflow-x-auto rounded-xl border border-slate-200 dark:border-neutral-700">
            <table className="w-full min-w-[640px] table-fixed border-collapse text-left text-sm">
              <thead className="bg-slate-50 text-xs font-semibold uppercase tracking-wide text-slate-500 dark:bg-neutral-800 dark:text-neutral-300">
                <tr>
                  <th className="w-10 px-2 py-2" aria-label="Expand row" />
                  <th className="w-14 px-2 py-2">Count</th>
                  <th className="w-[22%] min-w-0 px-2 py-2">Exception</th>
                  <th className="w-[26%] min-w-0 px-2 py-2">Route</th>
                  <th className="w-[28%] min-w-0 px-2 py-2">Message</th>
                  <th className="w-36 px-2 py-2">Last seen</th>
                  <th className="min-w-0 px-2 py-2">Stack</th>
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
                      colSpan={7}
                      summaryClassName="cursor-pointer border-l-2 border-transparent align-middle hover:border-orange-500/70 hover:bg-slate-50/90 dark:hover:border-orange-400/50 dark:hover:bg-neutral-800/90"
                      detailsRowClassName="bg-slate-50/95 dark:bg-neutral-900/95"
                      detailsCellClassName="px-4 py-3 text-sm text-slate-700 dark:text-neutral-300"
                      renderSummary={() => (
                        <>
                          <td className="px-2 py-2 align-middle">
                            <span className="inline-flex min-w-[2rem] justify-center rounded-full bg-rose-100 px-2 py-0.5 text-xs font-bold text-rose-800 dark:bg-rose-950/60 dark:text-rose-200">
                              {item.count}
                            </span>
                          </td>
                          <td className="min-w-0 px-2 py-2 align-middle">
                            <p className="truncate font-medium text-slate-900 dark:text-neutral-100" title={item.exception_type ?? ""}>
                              {item.exception_type ?? "(unknown)"}
                            </p>
                          </td>
                          <td className="min-w-0 px-2 py-2 align-middle">
                            <p className="truncate font-mono text-sm text-slate-800 dark:text-neutral-100" title={item.path}>
                              {item.path}
                            </p>
                          </td>
                          <td className="min-w-0 px-2 py-2 align-middle">
                            <p className="line-clamp-2 text-sm text-slate-600 dark:text-neutral-300" title={item.message ?? ""}>
                              {item.message ?? "(no message)"}
                            </p>
                          </td>
                          <td className="whitespace-nowrap px-2 py-2 align-middle text-sm text-slate-600 dark:text-neutral-300">
                            {formatTimestamp(item.last_seen)}
                          </td>
                          <td className="px-2 py-2 align-middle text-sm text-slate-500 dark:text-neutral-400">
                            {item.sample_stack_trace ? "Yes" : "—"}
                          </td>
                        </>
                      )}
                      renderDetails={() => {
                        const bookmarkFragment = `error-group:${encodeURIComponent(item.group_key)}`;
                        const defaultTitle = `${item.exception_type ?? "Error"} · ${item.path}`.slice(0, 200);
                        const menuItems = buildErrorGroupEvidenceMenuItems({
                          item,
                          onOpenInModal: () => setErrorModalItem(item),
                          onSaveBookmark: () =>
                            setBookmarkDraft({
                              title: defaultTitle,
                              hashFragment: bookmarkFragment,
                            }),
                        });
                        return (
                          <ErrorGroupEvidenceBody
                            item={item}
                            scopedState={scopedState}
                            headerActions={<RowActionsMenu items={menuItems} />}
                          />
                        );
                      }}
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
              className="ap-btn"
            >
              Prev
            </button>
            <button
              type="button"
              disabled={(d.errorGroupPage + 1) * d.errorGroupLimit >= errorGroups.total}
              onClick={() => d.setErrorGroupPage((p) => p + 1)}
              className="ap-btn"
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
                <Link
                  href={buildRequestsPageHref(scopedState, {
                    pathQuery: event.path,
                    statusClass: event.status_code >= 500 ? "5" : event.status_code >= 400 ? "4" : "ALL",
                  })}
                  className="mt-2 inline-block font-medium text-orange-600 underline-offset-2 hover:underline dark:text-orange-400"
                >
                  View in requests explorer
                </Link>
              </li>
            ))}
          </ul>
        ) : (
          <p className="mt-3 text-sm text-slate-600 dark:text-neutral-300">Select a busier window to load event evidence.</p>
        )}
      </section>
      <DashboardDetailModal
        open={errorModalItem !== null}
        title={errorModalItem ? `${errorModalItem.exception_type ?? "Error"} · ${errorModalItem.path}` : ""}
        onClose={() => setErrorModalItem(null)}
      >
        {errorModalItem ? (
          <ErrorGroupEvidenceBody
            item={errorModalItem}
            scopedState={scopedState}
            headerActions={
              <RowActionsMenu
                items={buildErrorGroupEvidenceMenuItems({
                  item: errorModalItem,
                  onOpenInModal: () => undefined,
                  onSaveBookmark: () =>
                    setBookmarkDraft({
                      title: `${errorModalItem.exception_type ?? "Error"} · ${errorModalItem.path}`.slice(0, 200),
                      hashFragment: `error-group:${encodeURIComponent(errorModalItem.group_key)}`,
                    }),
                }).filter((i) => i.id !== "open-modal")}
              />
            }
          />
        ) : null}
      </DashboardDetailModal>
      <SaveBookmarkModal
        open={bookmarkDraft !== null}
        onClose={() => setBookmarkDraft(null)}
        defaultTitle={bookmarkDraft?.title ?? ""}
        pathname={routePath}
        queryString={queryStringForBookmarks}
        hashFragment={bookmarkDraft?.hashFragment ?? ""}
      />
    </>
  );
}
