"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { IncidentNotebook } from "../incident/IncidentNotebook";
import { applyDashboardScopedQueryState } from "../applyDashboardScopedQuery";
import { DashboardDetailModal } from "../DashboardDetailModal";
import { useDashboardData } from "../DashboardDataContext";
import { dashboardSessionFetch, dashboardSessionJsonPost } from "../dashboardSessionFetch";
import {
  buildCurrentScopedState,
  buildDiagnosisPageHref,
  buildScopedQuery,
  parseScopedQuery,
  type DashboardScopedQueryState,
} from "../dashboardQueryState";
import { logicalDashboardLocationHref } from "../dashboardRoutePath";
import { Library } from "../../../lib/icons";
import {
  defaultIncidentNotebook,
  parseIncidentNotebookFromUnknown,
  serializeIncidentNotebook,
  type IncidentNotebookDocument,
  type IncidentScopeCapturedState,
} from "../../../utils/incidentNotebookModel";
import { SavedIncidentsModalPanel } from "./SavedIncidentsModalPanel";

function shortScopeHash(scopedQs: string): string {
  let h = 5381;
  for (let i = 0; i < scopedQs.length; i++) {
    h = Math.imul(33, h) ^ scopedQs.charCodeAt(i);
  }
  return (h >>> 0).toString(36);
}

const LEGACY_NOTES_STORAGE_PREFIX = "lumonox.incidentWorksheetNotes.v1";
const NOTEBOOK_STORAGE_PREFIX = "lumonox.incidentNotebook.v2";

function legacyNotesStorageKey(projectId: string | null, scopedQs: string, serverSavedIncidentId: string | null): string {
  const pid = projectId?.trim() || "unknown";
  const sfx = serverSavedIncidentId?.trim();
  const scopePart = shortScopeHash(scopedQs);
  return sfx
    ? `${LEGACY_NOTES_STORAGE_PREFIX}:${pid}:${scopePart}:${sfx}`
    : `${LEGACY_NOTES_STORAGE_PREFIX}:${pid}:${scopePart}`;
}

function notebookStorageKey(projectId: string | null, scopedQs: string, serverSavedIncidentId: string | null): string {
  const pid = projectId?.trim() || "unknown";
  const sfx = serverSavedIncidentId?.trim();
  const scopePart = shortScopeHash(scopedQs);
  return sfx
    ? `${NOTEBOOK_STORAGE_PREFIX}:${pid}:${scopePart}:${sfx}`
    : `${NOTEBOOK_STORAGE_PREFIX}:${pid}:${scopePart}`;
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
  const redeemedShareIdsRef = useRef<Set<string>>(new Set());
  const loadedSavedIdsRef = useRef<Set<string>>(new Set());
  const [handoffNotebook, setHandoffNotebook] = useState<IncidentNotebookDocument | null>(null);
  const [savedIncidentsModalOpen, setSavedIncidentsModalOpen] = useState(false);
  const [creatingNotebook, setCreatingNotebook] = useState(false);

  const shareIdInUrl = useMemo(() => searchParams.get("incident_share_id")?.trim() ?? "", [searchParams]);
  const savedIdInUrl = useMemo(() => searchParams.get("incident_saved_id")?.trim() ?? "", [searchParams]);

  useEffect(() => {
    if (!shareIdInUrl) {
      redeemedShareIdsRef.current.clear();
    }
  }, [shareIdInUrl]);

  useEffect(() => {
    if (!shareIdInUrl && !savedIdInUrl) {
      queueMicrotask(() => {
        setHandoffNotebook(null);
      });
    }
  }, [shareIdInUrl, savedIdInUrl]);

  useEffect(() => {
    if (!savedIdInUrl) {
      loadedSavedIdsRef.current.clear();
      return;
    }
    for (const id of [...loadedSavedIdsRef.current]) {
      if (id !== savedIdInUrl) {
        loadedSavedIdsRef.current.delete(id);
      }
    }
  }, [savedIdInUrl]);

  useEffect(() => {
    if (searchParams.get("saved_incidents") !== "1") {
      return;
    }
    queueMicrotask(() => {
      setSavedIncidentsModalOpen(true);
      const qs = new URLSearchParams(searchParams.toString());
      qs.delete("saved_incidents");
      const s = qs.toString();
      router.replace(s ? `/incident/?${s}` : `/incident/`);
    });
  }, [searchParams, router]);

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

  const openSavedIncidentFromModal = useCallback(
    (id: string) => {
      setSavedIncidentsModalOpen(false);
      const qs = buildScopedQuery(scopedState);
      qs.set("incident_saved_id", id);
      router.replace(`/incident/?${qs.toString()}`);
    },
    [router, scopedState],
  );

  const diagnosisHref = useMemo(() => buildDiagnosisPageHref(scopedState, {}, "#grouped-errors"), [scopedState]);
  const requestsHref = useMemo(() => `/requests?${scopedQs}`, [scopedQs]);
  const queryExplorerHref = useMemo(() => `/query-explorer?${scopedQs}`, [scopedQs]);
  const overviewHref = useMemo(() => `/dashboard?${scopedQs}`, [scopedQs]);
  const tracesHref = "/traces";
  const bookmarksHref = "/bookmarks";
  const incidentPagePath = useMemo(() => logicalDashboardLocationHref("/incident"), []);
  const notebookKey = useMemo(
    () => notebookStorageKey(d.sessionProjectId, scopedQs, savedIdInUrl || null),
    [d.sessionProjectId, savedIdInUrl, scopedQs],
  );
  const legacyNotesKey = useMemo(
    () => legacyNotesStorageKey(d.sessionProjectId, scopedQs, savedIdInUrl || null),
    [d.sessionProjectId, savedIdInUrl, scopedQs],
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

  const openFreshIncidentNotebook = useCallback(async () => {
    setSavedIncidentsModalOpen(false);
    setCreatingNotebook(true);
    setHandoffNotebook(null);
    try {
      const scope_state = getLiveScopeState();
      const notebook_document = JSON.parse(serializeIncidentNotebook(defaultIncidentNotebook())) as Record<
        string,
        unknown
      >;
      const createRes = await dashboardSessionJsonPost("/dashboard/incident-shares", {
        scope_state,
        notebook_document,
        title: null,
        access_mode: "organization",
        expires_in_days: 90,
      });
      const createRaw: unknown = await createRes.json();
      if (!createRes.ok) {
        const detail =
          typeof createRaw === "object" &&
          createRaw &&
          "detail" in createRaw &&
          typeof (createRaw as { detail: unknown }).detail === "string"
            ? (createRaw as { detail: string }).detail
            : `Could not create notebook (${createRes.status})`;
        window.alert(detail);
        return;
      }
      const savedRowIdRaw =
        typeof createRaw === "object" &&
        createRaw &&
        "share_id" in createRaw &&
        (createRaw as { share_id: unknown }).share_id != null
          ? String((createRaw as { share_id: unknown }).share_id)
          : "";
      const savedRowId = savedRowIdRaw.trim();
      if (!savedRowId) {
        window.alert("Server did not return a notebook id.");
        return;
      }
      const getRes = await dashboardSessionFetch(`/dashboard/incident-shares/${savedRowId}`);
      const getRaw: unknown = await getRes.json().catch(() => ({}));
      if (!getRes.ok) {
        const detail =
          typeof getRaw === "object" && getRaw && "detail" in getRaw && typeof (getRaw as { detail: unknown }).detail === "string"
            ? (getRaw as { detail: string }).detail
            : `Could not load new notebook (${getRes.status})`;
        window.alert(detail);
        return;
      }
      const scopedQuery =
        typeof getRaw === "object" &&
        getRaw &&
        "scoped_query" in getRaw &&
        typeof (getRaw as { scoped_query: unknown }).scoped_query === "string"
          ? (getRaw as { scoped_query: string }).scoped_query
          : "";
      const nb = parseIncidentNotebookFromUnknown(
        typeof getRaw === "object" && getRaw && "notebook_document" in getRaw
          ? (getRaw as { notebook_document: unknown }).notebook_document
          : null,
      );
      setHandoffNotebook(nb);
      applyDashboardScopedQueryState(applyTargets, parseScopedQuery(new URLSearchParams(scopedQuery)));
      loadedSavedIdsRef.current.add(savedRowId);
      const qs = new URLSearchParams(scopedQuery);
      qs.delete("incident_share_id");
      qs.set("incident_saved_id", savedRowId);
      router.replace(`/incident/?${qs.toString()}`);
    } catch (e) {
      window.alert(e instanceof Error ? e.message : "Could not create notebook.");
    } finally {
      setCreatingNotebook(false);
    }
  }, [applyTargets, getLiveScopeState, router]);

  useEffect(() => {
    const shareId = searchParams.get("incident_share_id")?.trim();
    if (!shareId || searchParams.get("incident_saved_id")?.trim() || redeemedShareIdsRef.current.has(shareId)) {
      return;
    }
    void (async () => {
      try {
        const res = await dashboardSessionJsonPost("/dashboard/incident-shares/redeem", {
          share_id: shareId,
        });
        const raw: unknown = await res.json();
        if (res.status === 409 && typeof raw === "object" && raw && "code" in raw && (raw as { code?: string }).code === "wrong_project") {
          const pid = (raw as { project_id?: string }).project_id ?? "";
          window.alert(
            `This incident link targets another project. Switch the dashboard to project ${pid} and open the link again.`,
          );
          return;
        }
        if (!res.ok) {
          const detail =
            typeof raw === "object" && raw && "detail" in raw && typeof (raw as { detail: unknown }).detail === "string"
              ? (raw as { detail: string }).detail
              : `Could not open share link (${res.status})`;
          window.alert(detail);
          return;
        }
        const scopedQuery =
          typeof raw === "object" && raw && "scoped_query" in raw && typeof (raw as { scoped_query: unknown }).scoped_query === "string"
            ? (raw as { scoped_query: string }).scoped_query
            : "";
        const parsed = parseScopedQuery(new URLSearchParams(scopedQuery));
        const nb = parseIncidentNotebookFromUnknown(
          typeof raw === "object" && raw && "notebook_document" in raw
            ? (raw as { notebook_document: unknown }).notebook_document
            : null,
        );
        setHandoffNotebook(nb);
        applyDashboardScopedQueryState(applyTargets, parsed);
        const qs = new URLSearchParams(scopedQuery);
        qs.set("incident_share_id", shareId);
        router.replace(`/incident/?${qs.toString()}`);
        redeemedShareIdsRef.current.add(shareId);
      } catch {
        /* allow retry */
      }
    })();
  }, [applyTargets, router, searchParams]);

  useEffect(() => {
    const savedId = searchParams.get("incident_saved_id")?.trim();
    if (!savedId || loadedSavedIdsRef.current.has(savedId)) {
      return;
    }
    void (async () => {
      try {
        const res = await dashboardSessionFetch(`/dashboard/incident-shares/${savedId}`);
        const raw: unknown = await res.json().catch(() => ({}));
        if (!res.ok) {
          const detail =
            typeof raw === "object" && raw && "detail" in raw && typeof (raw as { detail: unknown }).detail === "string"
              ? (raw as { detail: string }).detail
              : `Could not open saved incident (${res.status})`;
          window.alert(detail);
          return;
        }
        const scopedQuery =
          typeof raw === "object" && raw && "scoped_query" in raw && typeof (raw as { scoped_query: unknown }).scoped_query === "string"
            ? (raw as { scoped_query: string }).scoped_query
            : "";
        const parsed = parseScopedQuery(new URLSearchParams(scopedQuery));
        const nb = parseIncidentNotebookFromUnknown(
          typeof raw === "object" && raw && "notebook_document" in raw
            ? (raw as { notebook_document: unknown }).notebook_document
            : null,
        );
        setHandoffNotebook(nb);
        applyDashboardScopedQueryState(applyTargets, parsed);
        const qs = new URLSearchParams(scopedQuery);
        qs.set("incident_saved_id", savedId);
        router.replace(`/incident/?${qs.toString()}`);
        loadedSavedIdsRef.current.add(savedId);
      } catch {
        /* allow retry */
      }
    })();
  }, [applyTargets, router, searchParams]);

  return (
    <section className="space-y-4">
      <div className="rounded-2xl border border-slate-200/90 bg-white/95 p-5 shadow-sm dark:border-neutral-800 dark:bg-neutral-900">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between sm:gap-4">
          <div className="min-w-0 flex-1">
            <h1 className="text-xl font-semibold tracking-tight text-slate-900 dark:text-neutral-100">Incident notebook</h1>
            <p className="mt-2 text-sm leading-relaxed text-slate-600 dark:text-neutral-400">
              Build the incident narrative, capture and apply scope, run SQL, and publish server-backed saves. Use{" "}
              <span className="font-medium text-slate-800 dark:text-neutral-200">Saved incidents</span> to open or manage
              them.
              <span className="ml-1 text-slate-500 dark:text-neutral-500">{formatWindowSummary(d)}</span>
            </p>
          </div>
          <div className="flex w-full shrink-0 flex-wrap gap-2 sm:w-auto sm:justify-end">
            <button
              type="button"
              onClick={() => setSavedIncidentsModalOpen(true)}
              className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-800 shadow-sm hover:bg-slate-50 dark:border-neutral-600 dark:bg-neutral-800 dark:text-neutral-100 dark:hover:bg-neutral-700"
            >
              <Library className="size-4 text-orange-600 dark:text-orange-400" aria-hidden />
              Saved incidents
            </button>
            <button
              type="button"
              disabled={creatingNotebook}
              onClick={() => void openFreshIncidentNotebook()}
              className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-800 shadow-sm hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60 dark:border-neutral-600 dark:bg-neutral-800 dark:text-neutral-100 dark:hover:bg-neutral-700"
            >
              {creatingNotebook ? "Creating…" : "New notebook"}
            </button>
          </div>
        </div>
        <div className="mt-4">
          <IncidentNotebook
            key={notebookKey}
            storageKey={notebookKey}
            legacyPlaintextStorageKey={legacyNotesKey}
            scopeSummary={formatWindowSummary(d)}
            scopeDetailRows={scopeDetailRows}
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
            handoffNotebookDocument={handoffNotebook}
            serverSavedIncidentId={savedIdInUrl || null}
          />
        </div>
      </div>
      <DashboardDetailModal
        open={savedIncidentsModalOpen}
        title="Saved incidents"
        onClose={() => setSavedIncidentsModalOpen(false)}
        size="lg"
      >
        <SavedIncidentsModalPanel
          modalOpen={savedIncidentsModalOpen}
          creatingNewNotebook={creatingNotebook}
          onOpenSaved={openSavedIncidentFromModal}
          onNewIncident={() => void openFreshIncidentNotebook()}
        />
      </DashboardDetailModal>
    </section>
  );
}
