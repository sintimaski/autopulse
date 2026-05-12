"use client";

import { useCallback, useEffect, useMemo, useRef } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { IncidentNotebook } from "../incident/IncidentNotebook";
import { applyDashboardScopedQueryState } from "../applyDashboardScopedQuery";
import { useDashboardData } from "../DashboardDataContext";
import { dashboardSessionJsonPost } from "../dashboardSessionFetch";
import {
  buildCurrentScopedState,
  buildDiagnosisPageHref,
  buildScopedQuery,
  parseScopedQuery,
  type DashboardScopedQueryState,
} from "../dashboardQueryState";
import { logicalDashboardLocationHref } from "../dashboardRoutePath";
import type { IncidentScopeCapturedState } from "../../../utils/incidentNotebookModel";

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
    return `Fixed window · ${d.windowFromTimestamp.slice(0, 19)}Z -> ${d.windowToTimestamp.slice(0, 19)}Z`;
  }
  return `Rolling window · last ${d.windowMinutes} minutes`;
}

export function IncidentWorkspaceContent() {
  const d = useDashboardData();
  const router = useRouter();
  const searchParams = useSearchParams();
  const shareRedeemDoneRef = useRef(false);

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
  const scopeHash = useMemo(() => shortScopeHash(scopedQs), [scopedQs]);
  const diagnosisHref = useMemo(() => buildDiagnosisPageHref(scopedState, {}, "#grouped-errors"), [scopedState]);
  const requestsHref = useMemo(() => `/requests?${scopedQs}`, [scopedQs]);
  const queryExplorerHref = useMemo(() => `/query-explorer?${scopedQs}`, [scopedQs]);
  const overviewHref = useMemo(() => `/dashboard?${scopedQs}`, [scopedQs]);
  const tracesHref = "/traces";
  const bookmarksHref = "/bookmarks";
  const incidentPagePath = useMemo(() => logicalDashboardLocationHref("/incident"), []);
  const notebookKey = useMemo(() => notebookStorageKey(d.sessionProjectId, scopedQs), [d.sessionProjectId, scopedQs]);
  const legacyNotesKey = useMemo(
    () => legacyNotesStorageKey(d.sessionProjectId, scopedQs),
    [d.sessionProjectId, scopedQs],
  );
  const scopeDetailRows = useMemo(
    () =>
      [
        `Method: ${d.method}`,
        `Status: ${d.statusClass}`,
        d.pathQuery.trim() ? `Path filter: ${d.pathQuery.trim()}` : "Path filter: (none)",
        d.serverEnvironmentQuery.trim()
          ? `Environment filter: ${d.serverEnvironmentQuery.trim()}`
          : "Environment filter: (none)",
        d.serverServiceQuery.trim() ? `Service filter: ${d.serverServiceQuery.trim()}` : "Service filter: (none)",
        d.correlationRequestId.trim()
          ? `Correlation request_id: ${d.correlationRequestId.trim()}`
          : "Correlation request_id: (none)",
      ] as const,
    [
      d.correlationRequestId,
      d.method,
      d.pathQuery,
      d.serverEnvironmentQuery,
      d.serverServiceQuery,
      d.statusClass,
    ],
  );

  const applyTargets = useMemo(
    () => ({
      setAbsoluteWindow: d.setAbsoluteWindow,
      clearAbsoluteWindow: d.clearAbsoluteWindow,
      onServerWindowChange: d.onServerWindowChange,
      onServerMethodChange: d.onServerMethodChange,
      onServerStatusClassChange: d.onServerStatusClassChange,
      setPathQuery: d.setPathQuery,
      setMinLatencyMs: d.setMinLatencyMs,
      setMaxLatencyMs: d.setMaxLatencyMs,
      setServerEnvironmentQuery: d.setServerEnvironmentQuery,
      setServerServiceQuery: d.setServerServiceQuery,
      setRequestLimit: d.setRequestLimit,
      setRequestPage: d.setRequestPage,
      setErrorGroupLimit: d.setErrorGroupLimit,
      setErrorGroupPage: d.setErrorGroupPage,
      setErrorGroupSort: d.setErrorGroupSort,
      setSqlFilterApplied: d.setSqlFilterApplied,
      setSqlFilterDraft: d.setSqlFilterDraft,
      setSqlFilterEnabled: d.setSqlFilterEnabled,
      setCorrelationRequestId: d.setCorrelationRequestId,
    }),
    [
      d.clearAbsoluteWindow,
      d.onServerMethodChange,
      d.onServerStatusClassChange,
      d.onServerWindowChange,
      d.setAbsoluteWindow,
      d.setCorrelationRequestId,
      d.setErrorGroupLimit,
      d.setErrorGroupPage,
      d.setErrorGroupSort,
      d.setMaxLatencyMs,
      d.setMinLatencyMs,
      d.setPathQuery,
      d.setRequestLimit,
      d.setRequestPage,
      d.setServerEnvironmentQuery,
      d.setServerServiceQuery,
      d.setSqlFilterApplied,
      d.setSqlFilterDraft,
      d.setSqlFilterEnabled,
    ],
  );

  const onApplyDashboardScope = useCallback(
    (state: IncidentScopeCapturedState) => {
      applyDashboardScopedQueryState(applyTargets, state as DashboardScopedQueryState);
    },
    [applyTargets],
  );

  const getLiveScopeState = useCallback((): IncidentScopeCapturedState => {
    return buildCurrentScopedState({
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
    }) as IncidentScopeCapturedState;
  }, [
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
  ]);

  useEffect(() => {
    const token = searchParams.get("incident_share");
    if (!token?.trim() || shareRedeemDoneRef.current) {
      return;
    }
    shareRedeemDoneRef.current = true;
    void (async () => {
      try {
        const res = await dashboardSessionJsonPost("/dashboard/incident-shares/redeem", {
          token: token.trim(),
        });
        const raw: unknown = await res.json();
        if (res.status === 409 && typeof raw === "object" && raw && "code" in raw && (raw as { code?: string }).code === "wrong_project") {
          const pid = (raw as { project_id?: string }).project_id ?? "";
          window.alert(
            `This incident link targets another project. Switch the dashboard to project ${pid} and open the link again.`,
          );
          shareRedeemDoneRef.current = false;
          return;
        }
        if (!res.ok) {
          const detail =
            typeof raw === "object" && raw && "detail" in raw && typeof (raw as { detail: unknown }).detail === "string"
              ? (raw as { detail: string }).detail
              : `Could not open share link (${res.status})`;
          window.alert(detail);
          shareRedeemDoneRef.current = false;
          return;
        }
        const scopedQuery =
          typeof raw === "object" && raw && "scoped_query" in raw && typeof (raw as { scoped_query: unknown }).scoped_query === "string"
            ? (raw as { scoped_query: string }).scoped_query
            : "";
        const parsed = parseScopedQuery(new URLSearchParams(scopedQuery));
        applyDashboardScopedQueryState(applyTargets, parsed);
        const nextHref = logicalDashboardLocationHref(scopedQuery ? `/incident?${scopedQuery}` : "/incident");
        router.replace(nextHref);
      } catch {
        shareRedeemDoneRef.current = false;
      }
    })();
  }, [applyTargets, router, searchParams]);

  return (
    <section className="space-y-4">
      <div className="rounded-2xl border border-slate-200/90 bg-white/95 p-5 shadow-sm dark:border-neutral-800 dark:bg-neutral-900">
        <h1 className="text-xl font-semibold tracking-tight text-slate-900 dark:text-neutral-100">Incident notebook</h1>
        <p className="mt-2 text-sm leading-relaxed text-slate-600 dark:text-neutral-400">
          Build the incident narrative, capture and apply scope, run SQL, and share with controlled links.
          <span className="ml-1 text-slate-500 dark:text-neutral-500">{formatWindowSummary(d)}</span>
        </p>
        <div className="mt-4">
          <IncidentNotebook
            storageKey={notebookKey}
            legacyPlaintextStorageKey={legacyNotesKey}
            scopeSummary={formatWindowSummary(d)}
            scopeDetailRows={scopeDetailRows}
            scopeHash={scopeHash}
            incidentPagePath={incidentPagePath}
            quickLinks={[
              { label: "Errors & diagnosis", href: diagnosisHref },
              { label: "Requests", href: requestsHref },
              { label: "Query Explorer", href: queryExplorerHref },
              { label: "Overview", href: overviewHref },
              { label: "Traces", href: tracesHref },
              { label: "Bookmarks", href: bookmarksHref },
            ]}
            onApplyDashboardScope={onApplyDashboardScope}
            getLiveScopeState={getLiveScopeState}
            sessionOrganizationId={d.sessionOrganizationId}
          />
        </div>
      </div>
    </section>
  );
}
