"use client";

import Link from "next/link";
import { useCallback, useMemo } from "react";

import { ClipboardList, ExternalLink, Share2 } from "../../../lib/icons";
import { IncidentNotebook } from "../incident/IncidentNotebook";
import { useDashboardData } from "../DashboardDataContext";
import {
  buildCurrentScopedState,
  buildDiagnosisPageHref,
  buildIncidentShareQuery,
  buildScopedQuery,
} from "../dashboardQueryState";
import { logicalDashboardLocationHref } from "../dashboardRoutePath";

function shortScopeHash(scopedQs: string): string {
  let h = 5381;
  for (let i = 0; i < scopedQs.length; i++) {
    h = Math.imul(33, h) ^ scopedQs.charCodeAt(i);
  }
  return (h >>> 0).toString(36);
}

const LEGACY_NOTES_STORAGE_PREFIX = "lumonox.incidentWorksheetNotes.v1";
const NOTEBOOK_STORAGE_PREFIX = "lumonox.incidentNotebook.v2";

function legacyNotesStorageKey(projectId: string | null, scopedQs: string): string {
  const pid = projectId?.trim() || "unknown";
  return `${LEGACY_NOTES_STORAGE_PREFIX}:${pid}:${shortScopeHash(scopedQs)}`;
}

function notebookStorageKey(projectId: string | null, scopedQs: string): string {
  const pid = projectId?.trim() || "unknown";
  return `${NOTEBOOK_STORAGE_PREFIX}:${pid}:${shortScopeHash(scopedQs)}`;
}

function formatWindowSummary(d: ReturnType<typeof useDashboardData>): string {
  if (d.isAbsoluteWindow && d.windowFromTimestamp && d.windowToTimestamp) {
    return `Fixed window · ${d.windowFromTimestamp.slice(0, 19)}Z → ${d.windowToTimestamp.slice(0, 19)}Z`;
  }
  return `Rolling · last ${d.windowMinutes} minutes`;
}

export function IncidentWorkspaceContent() {
  const d = useDashboardData();
  const scopedState = useMemo(
    () =>
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
        correlationRequestId: d.correlationRequestId,
        sqlFilterApplied: d.sqlFilterApplied,
        sqlFilterEnabled: d.sqlFilterEnabled,
      }),
    [
      d.correlationRequestId,
      d.errorGroupLimit,
      d.errorGroupPage,
      d.errorGroupSort,
      d.isAbsoluteWindow,
      d.maxLatencyMs,
      d.method,
      d.minLatencyMs,
      d.pathQuery,
      d.requestLimit,
      d.requestPage,
      d.serverEnvironmentQuery,
      d.serverServiceQuery,
      d.sqlFilterApplied,
      d.sqlFilterEnabled,
      d.statusClass,
      d.windowFromTimestamp,
      d.windowMinutes,
      d.windowToTimestamp,
    ],
  );

  const scopedQs = useMemo(() => buildScopedQuery(scopedState).toString(), [scopedState]);
  const diagnosisHref = useMemo(() => buildDiagnosisPageHref(scopedState, {}, "#grouped-errors"), [scopedState]);
  const requestsHref = useMemo(() => `/requests?${scopedQs}`, [scopedQs]);
  const logsHref = useMemo(() => `/logs?${scopedQs}`, [scopedQs]);
  const queryExplorerHref = useMemo(() => `/query-explorer?${scopedQs}`, [scopedQs]);
  const overviewHref = useMemo(() => `/dashboard?${scopedQs}`, [scopedQs]);
  const tracesHref = "/traces";
  const bookmarksHref = "/bookmarks";
  const alertsHref = "/alerts";

  const handoffQuery = useMemo(() => buildIncidentShareQuery(scopedState), [scopedState]);
  const handoffPath = useMemo(
    () => logicalDashboardLocationHref(handoffQuery ? `/incident?${handoffQuery}` : "/incident"),
    [handoffQuery],
  );

  const notebookKey = useMemo(() => notebookStorageKey(d.sessionProjectId, scopedQs), [d.sessionProjectId, scopedQs]);
  const legacyNotesKey = useMemo(
    () => legacyNotesStorageKey(d.sessionProjectId, scopedQs),
    [d.sessionProjectId, scopedQs],
  );
  const copyEvidencePack = useCallback(async () => {
    const origin = typeof window !== "undefined" ? window.location.origin : "";
    const abs = (path: string) => new URL(logicalDashboardLocationHref(path), origin || "http://localhost").href;
    const lines = [
      "# Lumonox incident worksheet",
      "",
      `- **Project:** ${d.sessionProjectId ?? "(session project)"}`,
      `- **Scope:** ${formatWindowSummary(d)}`,
      d.pathQuery.trim() ? `- **Path contains:** ${d.pathQuery.trim()}` : null,
      d.correlationRequestId.trim() ? `- **Correlation request_id:** \`${d.correlationRequestId.trim()}\`` : null,
      "",
      "## Quick links",
      "",
      `- [Overview](${abs(overviewHref)})`,
      `- [Errors & Diagnosis (grouped)](${abs(diagnosisHref)})`,
      `- [Requests](${abs(requestsHref)})`,
      `- [Request log (legacy)](${abs(logsHref)})`,
      `- [Traces](${abs(tracesHref)}) — set the trace time window to match this incident if needed.`,
      `- [Query Explorer](${abs(queryExplorerHref)})`,
      `- [Bookmarks](${abs(bookmarksHref)})`,
      `- [Alerts](${abs(alertsHref)})`,
      "",
      "## Shareable incident URL (time window only)",
      "",
      `\`${new URL(handoffPath, origin || "http://localhost").href}\``,
      "",
      "## Notebook",
      "",
      "Structured cells (markdown, notes, SQL) are stored in **this browser’s localStorage** for this project + scope. SQL run outputs are not persisted across reloads.",
      "",
    ].filter((l): l is string => l !== null);
    const text = lines.join("\n");
    try {
      await navigator.clipboard.writeText(text);
    } catch {
      window.prompt("Copy evidence pack (Ctrl+C / ⌘C):", text);
    }
  }, [
    alertsHref,
    bookmarksHref,
    diagnosisHref,
    d,
    handoffPath,
    logsHref,
    overviewHref,
    queryExplorerHref,
    requestsHref,
    tracesHref,
  ]);

  const evidenceCards = useMemo(
    () =>
      [
        {
          title: "Errors & grouped failures",
          body: "Stack traces, fingerprints, and correlated timeline for the scoped window.",
          href: diagnosisHref,
        },
        {
          title: "Requests",
          body: "HTTP evidence rows, latency, status — export-friendly table.",
          href: requestsHref,
        },
        {
          title: "Request log",
          body: "Legacy grouped log view (same scope as Requests).",
          href: logsHref,
        },
        {
          title: "Traces (OTLP)",
          body: "Span search uses its own time controls — align with this incident window when investigating.",
          href: tracesHref,
        },
        {
          title: "Query Explorer",
          body: "DuckDB SQL over retained events; time scope follows the header toolbar.",
          href: queryExplorerHref,
        },
        {
          title: "Overview",
          body: "Health snapshot and traffic charts for the same filters.",
          href: overviewHref,
        },
        {
          title: "Bookmarks",
          body: "Save this scope or a diagnosis deep-link for the team.",
          href: bookmarksHref,
        },
        {
          title: "Alerts",
          body: "Dispatch history and alert settings for follow-up.",
          href: alertsHref,
        },
      ] as const,
    [alertsHref, bookmarksHref, diagnosisHref, logsHref, overviewHref, queryExplorerHref, requestsHref, tracesHref],
  );

  return (
    <section className="space-y-6">
      <div className="rounded-2xl border border-slate-200/90 bg-white/95 p-5 shadow-sm dark:border-neutral-800 dark:bg-neutral-900">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0">
            <p className="text-xs font-semibold uppercase tracking-wide text-sky-700 dark:text-sky-300">
              Incident worksheet
            </p>
            <h1 className="mt-1 text-xl font-semibold tracking-tight text-slate-900 dark:text-neutral-100">
              Collect evidence in one place
            </h1>
            <p className="mt-2 max-w-3xl text-sm leading-relaxed text-slate-600 dark:text-neutral-400">
              Use the <strong className="font-medium text-slate-800 dark:text-neutral-200">Incident scope</strong>{" "}
              toolbar above to lock the time window and server filters. The{" "}
              <strong className="font-medium text-slate-800 dark:text-neutral-200">notebook</strong> below supports
              Jupyter-style cells (markdown, notes, runnable SQL, dividers). Quick links open the rest of the console
              with the same scope.{" "}
              <span className="text-slate-500 dark:text-neutral-500">{formatWindowSummary(d)}</span>
            </p>
          </div>
          <div className="flex shrink-0 flex-col gap-2 sm:items-end">
            <button
              type="button"
              className="inline-flex items-center justify-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-800 shadow-sm transition hover:bg-slate-50 dark:border-neutral-700 dark:bg-neutral-800 dark:text-neutral-100 dark:hover:bg-neutral-700"
              onClick={() => void copyEvidencePack()}
            >
              <ClipboardList className="size-4 shrink-0" aria-hidden />
              Copy evidence pack
            </button>
            <p className="max-w-[16rem] text-right text-[11px] leading-snug text-slate-500 dark:text-neutral-500">
              Markdown checklist with deep links; notebook content stays in this browser until you copy it out.
            </p>
          </div>
        </div>
      </div>

      <div className="rounded-2xl border border-slate-200/90 bg-white/95 p-5 shadow-sm dark:border-neutral-800 dark:bg-neutral-900">
        <h2 className="text-base font-semibold text-slate-900 dark:text-neutral-100">Incident notebook</h2>
        <p className="mt-1 text-sm text-slate-600 dark:text-neutral-400">
          Add rows, reorder with the arrows, run SQL against <code className="rounded bg-slate-100 px-1 text-xs dark:bg-neutral-800">scoped_events</code> (same contract as Query Explorer). Stored locally per project + scope hash{" "}
          <code className="rounded bg-slate-100 px-1 text-xs dark:bg-neutral-800">{shortScopeHash(scopedQs)}</code>.
        </p>
        <div className="mt-4">
          <IncidentNotebook storageKey={notebookKey} legacyPlaintextStorageKey={legacyNotesKey} />
        </div>
      </div>

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        {evidenceCards.map((card) => (
          <Link
            key={card.title}
            href={card.href}
            className="group flex flex-col rounded-xl border border-slate-200/90 bg-white p-4 shadow-sm ring-1 ring-slate-900/[0.04] transition hover:border-sky-300/80 hover:ring-sky-500/15 dark:border-neutral-700 dark:bg-neutral-900 dark:ring-white/[0.06] dark:hover:border-sky-600/50"
          >
            <span className="flex items-start justify-between gap-2">
              <span className="text-sm font-semibold text-slate-900 dark:text-neutral-100">{card.title}</span>
              <ExternalLink className="size-4 shrink-0 text-slate-400 opacity-0 transition group-hover:opacity-100 dark:text-neutral-500" aria-hidden />
            </span>
            <p className="mt-2 text-xs leading-relaxed text-slate-600 dark:text-neutral-400">{card.body}</p>
          </Link>
        ))}
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <div className="rounded-xl border border-slate-200/90 bg-white p-4 shadow-sm dark:border-neutral-700 dark:bg-neutral-900">
          <h2 className="text-sm font-semibold text-slate-900 dark:text-neutral-100">Snapshots & exports</h2>
          <p className="mt-1 text-xs leading-relaxed text-slate-600 dark:text-neutral-400">
            There is no server-side incident blob yet — capture what you need from each tool, then use{" "}
            <strong className="font-medium text-slate-800 dark:text-neutral-200">Copy evidence pack</strong> for a
            single clipboard payload. For reusable deep links, save a{" "}
            <Link href={bookmarksHref} className="font-medium text-sky-700 underline-offset-2 hover:underline dark:text-sky-300">
              bookmark
            </Link>
            .
          </p>
        </div>
        <div className="rounded-xl border border-slate-200/90 bg-white p-4 shadow-sm dark:border-neutral-700 dark:bg-neutral-900">
          <h2 className="flex items-center gap-2 text-sm font-semibold text-slate-900 dark:text-neutral-100">
            <Share2 className="size-4 text-slate-500 dark:text-neutral-400" aria-hidden />
            Share incident window
          </h2>
          <p className="mt-1 text-xs text-slate-600 dark:text-neutral-400">
            Short URL (time only) for handoff — recipients land on this worksheet with the same window.
          </p>
          <code className="mt-3 block max-h-24 overflow-auto rounded-lg bg-slate-50 px-2 py-2 text-[11px] leading-snug text-slate-800 dark:bg-neutral-950 dark:text-neutral-200">
            {typeof window !== "undefined" ? new URL(handoffPath, window.location.origin).href : handoffPath}
          </code>
        </div>
      </div>
    </section>
  );
}
