"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { CardSpinner } from "../../ui/CardSpinner";
import { buildDashboardNetworkError } from "../../../utils/dashboardFetchErrors";
import { parseDashboardMembershipItemsPayload } from "../../../utils/dashboardResponseGuards";
import {
  defaultEmptyIncidentScope,
  defaultIncidentNotebook,
  moveCell,
  newChecklistCell,
  newDividerCell,
  newLinkCell,
  newMarkdownCell,
  newScopeCell,
  newSqlCell,
  newTextCell,
  parseIncidentNotebookJson,
  removeCellAt,
  serializeIncidentNotebook,
  type IncidentNotebookCell,
  type IncidentNotebookDocument,
  type IncidentScopeCapturedState,
} from "../../../utils/incidentNotebookModel";
import {
  buildQueryExplorerExecutePayload,
  type QueryExplorerExecuteInput,
} from "../../../utils/queryExplorerExecute";
import { parseQueryExplorerResponse } from "../../../utils/dashboardResponseGuards";
import { ChevronDown, ChevronUp, ClipboardList, ExternalLink, Plus, Trash2 } from "../../../lib/icons";
import { useDashboardData } from "../DashboardDataContext";
import { dashboardSessionFetch, dashboardSessionJsonPost } from "../dashboardSessionFetch";
import type { DashboardMembershipItem, QueryExplorerResponse } from "../dashboardTypes";

const IncidentMarkdownBody = dynamic(
  () => import("./IncidentMarkdownBody").then((m) => m.IncidentMarkdownBody),
  { ssr: false, loading: () => <p className="text-xs text-slate-500 dark:text-neutral-500">Loading preview…</p> },
);

type SqlOutput = { loading: boolean; error: string | null; data: QueryExplorerResponse | null };
type NotebookSaveState = "idle" | "saving" | "saved" | "error";
type NotebookSnapshot = { id: string; name: string; savedAtIso: string; payload: string };
type FlowChecklist = {
  captured: boolean;
  investigated: boolean;
  handoffReady: boolean;
};

const FLOW_CHECKLIST_DEFAULT: FlowChecklist = {
  captured: false,
  investigated: false,
  handoffReady: false,
};

function randomId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `snapshot-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

function formatSavedAt(ts: string): string {
  const ms = Date.parse(ts);
  if (!Number.isFinite(ms)) {
    return "Unknown time";
  }
  return new Date(ms).toLocaleString();
}

function parseSnapshotList(raw: string | null): NotebookSnapshot[] {
  if (!raw) {
    return [];
  }
  let parsed: unknown;
  try {
    parsed = JSON.parse(raw) as unknown;
  } catch {
    return [];
  }
  if (!Array.isArray(parsed)) {
    return [];
  }
  const list: NotebookSnapshot[] = [];
  for (const item of parsed) {
    if (typeof item !== "object" || item === null || Array.isArray(item)) {
      continue;
    }
    const id = "id" in item && typeof item.id === "string" ? item.id : "";
    const name = "name" in item && typeof item.name === "string" ? item.name : "";
    const savedAtIso = "savedAtIso" in item && typeof item.savedAtIso === "string" ? item.savedAtIso : "";
    const payload = "payload" in item && typeof item.payload === "string" ? item.payload : "";
    if (!id || !name || !savedAtIso || !payload) {
      continue;
    }
    list.push({ id, name, savedAtIso, payload });
  }
  return list;
}

function parseFlowChecklist(raw: string | null): FlowChecklist {
  if (!raw) {
    return FLOW_CHECKLIST_DEFAULT;
  }
  let parsed: unknown;
  try {
    parsed = JSON.parse(raw) as unknown;
  } catch {
    return FLOW_CHECKLIST_DEFAULT;
  }
  if (typeof parsed !== "object" || parsed === null || Array.isArray(parsed)) {
    return FLOW_CHECKLIST_DEFAULT;
  }
  return {
    captured: "captured" in parsed && Boolean(parsed.captured),
    investigated: "investigated" in parsed && Boolean(parsed.investigated),
    handoffReady: "handoffReady" in parsed && Boolean(parsed.handoffReady),
  };
}

function briefCell(cell: IncidentNotebookCell): string {
  if (cell.type === "divider") {
    return "Divider";
  }
  if (cell.type === "scope") {
    const tag = cell.filters ? " [saved filters]" : "";
    return cell.source.trim() ? `Scope${tag}: ${cell.source.trim()}` : `Scope${tag}`;
  }
  if (cell.type === "checklist") {
    return cell.title.trim() || "Checklist";
  }
  if (cell.type === "link") {
    return cell.label.trim() || cell.href.trim() || "Link";
  }
  const first = cell.source
    .trim()
    .split("\n")
    .map((line) => line.trim())
    .find(Boolean);
  if (!first) {
    return cell.type === "sql" ? "SQL (empty)" : `${cell.type} (empty)`;
  }
  return first.length > 120 ? `${first.slice(0, 117)}...` : first;
}

function buildHandoffBrief(
  doc: IncidentNotebookDocument,
  scopeSummary: string,
  quickLinks: ReadonlyArray<{ label: string; href: string }>,
  incidentPageHref: string,
): string {
  const lines: string[] = [
    "# Incident handoff brief",
    "",
    `- Scope: ${scopeSummary}`,
    `- Incident page: ${incidentPageHref}`,
    "",
    "## Quick links",
    "",
    ...quickLinks.map((item) => `- ${item.label}: ${item.href}`),
    "",
    "## Notebook highlights",
    "",
    ...doc.cells.map((cell, idx) => `${idx + 1}. [${cell.type}] ${briefCell(cell)}`),
    "",
  ];
  return lines.join("\n");
}

function cloneCell(cell: IncidentNotebookCell): IncidentNotebookCell {
  if (cell.type === "divider") {
    return newDividerCell();
  }
  if (cell.type === "scope") {
    return newScopeCell(cell.source, cell.filters);
  }
  if (cell.type === "checklist") {
    return newChecklistCell(
      cell.title,
      cell.items.map((it) => ({ ...it, id: randomId() })),
    );
  }
  if (cell.type === "link") {
    return newLinkCell(cell.label, cell.href, cell.note);
  }
  if (cell.type === "markdown") {
    return newMarkdownCell(cell.source);
  }
  if (cell.type === "text") {
    return newTextCell(cell.source);
  }
  return newSqlCell(cell.source, cell.rowLimit, cell.applyTimeWindow);
}

function ResultTable({ data }: { data: QueryExplorerResponse }) {
  return (
    <div className="mt-3 overflow-x-auto rounded-lg border border-slate-200 dark:border-neutral-700">
      <table className="min-w-full text-left text-xs">
        <thead className="bg-slate-50 dark:bg-neutral-800">
          <tr>
            {data.columns.map((column) => (
              <th key={column} className="px-2 py-1.5 font-semibold text-slate-700 dark:text-neutral-200">
                {column}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100 dark:divide-neutral-800">
          {data.rows.map((row, idx) => (
            <tr key={`${idx}-${row.length}`}>
              {row.map((cell, cellIdx) => (
                <td key={`${idx}-${cellIdx}`} className="px-2 py-1.5 text-slate-700 dark:text-neutral-300">
                  {cell === null ? "null" : String(cell)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function IncidentScopeCellBody({
  cell,
  index,
  updateCell,
  onApplyDashboardScope,
  getLiveScopeState,
  scopeSummary,
  scopeDetailRows,
  methodOptions,
  statusClassOptions,
}: {
  cell: Extract<IncidentNotebookCell, { type: "scope" }>;
  index: number;
  updateCell: (idx: number, next: IncidentNotebookCell) => void;
  onApplyDashboardScope: (state: IncidentScopeCapturedState) => void;
  getLiveScopeState: () => IncidentScopeCapturedState;
  scopeSummary: string;
  scopeDetailRows: readonly string[];
  methodOptions: readonly string[];
  statusClassOptions: readonly string[];
}) {
  const f = cell.filters ?? defaultEmptyIncidentScope();
  const patch = (partial: Partial<IncidentScopeCapturedState>) => {
    const base = cell.filters ?? defaultEmptyIncidentScope();
    updateCell(index, { ...cell, filters: { ...base, ...partial } });
  };

  return (
    <div className="space-y-3">
      <div className="rounded-lg border border-sky-100 bg-sky-50/70 px-3 py-2 text-xs text-slate-700 dark:border-sky-950/50 dark:bg-sky-950/20 dark:text-neutral-200">
        <p className="font-semibold text-slate-900 dark:text-neutral-100">Live session scope</p>
        <p className="mt-1">{scopeSummary}</p>
        <ul className="mt-2 list-disc space-y-1 pl-4 text-slate-600 dark:text-neutral-300">
          {scopeDetailRows.map((item) => (
            <li key={`${cell.id}-live-${item}`}>{item}</li>
          ))}
        </ul>
      </div>

      <div className="rounded-lg border border-slate-200/90 bg-slate-50/60 px-3 py-2 text-xs dark:border-neutral-700 dark:bg-neutral-950/40">
        <p className="font-semibold text-slate-900 dark:text-neutral-100">Scope constraints (saved in this cell)</p>
        <p className="mt-1 text-[10px] leading-relaxed text-slate-500 dark:text-neutral-500">
          Edit filters below, then apply to the dashboard. Values persist in the notebook; empty storage uses defaults until you capture or edit.
        </p>
        <div className="mt-3 grid gap-2 sm:grid-cols-2">
          <label className="flex flex-col gap-0.5 text-[11px] text-slate-600 dark:text-neutral-400">
            <span>HTTP method</span>
            <select
              className="rounded border border-slate-200 bg-white px-2 py-1 text-xs dark:border-neutral-600 dark:bg-neutral-900 dark:text-neutral-100"
              value={f.method}
              onChange={(e) => patch({ method: e.target.value })}
            >
              {methodOptions.map((m) => (
                <option key={m} value={m}>
                  {m}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-0.5 text-[11px] text-slate-600 dark:text-neutral-400">
            <span>Status class</span>
            <select
              className="rounded border border-slate-200 bg-white px-2 py-1 text-xs dark:border-neutral-600 dark:bg-neutral-900 dark:text-neutral-100"
              value={f.statusClass}
              onChange={(e) => patch({ statusClass: e.target.value })}
            >
              {statusClassOptions.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </label>
          <label className="flex items-center gap-2 text-[11px] text-slate-700 dark:text-neutral-300 sm:col-span-2">
            <input
              type="checkbox"
              className="size-3.5 rounded border-slate-300 text-sky-600 dark:border-neutral-600"
              checked={f.isAbsoluteWindow}
              onChange={(e) => patch({ isAbsoluteWindow: e.target.checked })}
            />
            Fixed time window (use from / to timestamps)
          </label>
          {f.isAbsoluteWindow ? (
            <>
              <label className="flex flex-col gap-0.5 text-[11px] text-slate-600 dark:text-neutral-400">
                <span>From (ISO)</span>
                <input
                  type="text"
                  value={f.windowFromTimestamp}
                  onChange={(e) => patch({ windowFromTimestamp: e.target.value })}
                  placeholder="2026-01-01T00:00:00.000Z"
                  className="rounded border border-slate-200 bg-white px-2 py-1 font-mono text-[11px] dark:border-neutral-600 dark:bg-neutral-900 dark:text-neutral-100"
                />
              </label>
              <label className="flex flex-col gap-0.5 text-[11px] text-slate-600 dark:text-neutral-400">
                <span>To (ISO)</span>
                <input
                  type="text"
                  value={f.windowToTimestamp}
                  onChange={(e) => patch({ windowToTimestamp: e.target.value })}
                  placeholder="2026-01-01T01:00:00.000Z"
                  className="rounded border border-slate-200 bg-white px-2 py-1 font-mono text-[11px] dark:border-neutral-600 dark:bg-neutral-900 dark:text-neutral-100"
                />
              </label>
            </>
          ) : (
            <label className="flex flex-col gap-0.5 text-[11px] text-slate-600 dark:text-neutral-400 sm:col-span-2">
              <span>Rolling window (minutes)</span>
              <input
                type="number"
                min={1}
                max={10080}
                value={f.windowMinutes}
                onChange={(e) =>
                  patch({ windowMinutes: Math.max(1, Math.min(10080, Math.floor(Number(e.target.value) || 60))) })
                }
                className="max-w-[10rem] rounded border border-slate-200 bg-white px-2 py-1 text-xs dark:border-neutral-600 dark:bg-neutral-900 dark:text-neutral-100"
              />
            </label>
          )}
          <label className="flex flex-col gap-0.5 text-[11px] text-slate-600 dark:text-neutral-400 sm:col-span-2">
            <span>Path contains</span>
            <input
              type="text"
              value={f.pathQuery}
              onChange={(e) => patch({ pathQuery: e.target.value })}
              className="rounded border border-slate-200 bg-white px-2 py-1 font-mono text-[11px] dark:border-neutral-600 dark:bg-neutral-900 dark:text-neutral-100"
            />
          </label>
          <label className="flex flex-col gap-0.5 text-[11px] text-slate-600 dark:text-neutral-400">
            <span>Environments (comma)</span>
            <input
              type="text"
              value={f.serverEnvironmentQuery}
              onChange={(e) => patch({ serverEnvironmentQuery: e.target.value })}
              className="rounded border border-slate-200 bg-white px-2 py-1 font-mono text-[11px] dark:border-neutral-600 dark:bg-neutral-900 dark:text-neutral-100"
            />
          </label>
          <label className="flex flex-col gap-0.5 text-[11px] text-slate-600 dark:text-neutral-400">
            <span>Services (comma)</span>
            <input
              type="text"
              value={f.serverServiceQuery}
              onChange={(e) => patch({ serverServiceQuery: e.target.value })}
              className="rounded border border-slate-200 bg-white px-2 py-1 font-mono text-[11px] dark:border-neutral-600 dark:bg-neutral-900 dark:text-neutral-100"
            />
          </label>
          <label className="flex flex-col gap-0.5 text-[11px] text-slate-600 dark:text-neutral-400">
            <span>Min latency (ms)</span>
            <input
              type="text"
              value={f.minLatencyMs}
              onChange={(e) => patch({ minLatencyMs: e.target.value })}
              className="rounded border border-slate-200 bg-white px-2 py-1 font-mono text-[11px] dark:border-neutral-600 dark:bg-neutral-900 dark:text-neutral-100"
            />
          </label>
          <label className="flex flex-col gap-0.5 text-[11px] text-slate-600 dark:text-neutral-400">
            <span>Max latency (ms)</span>
            <input
              type="text"
              value={f.maxLatencyMs}
              onChange={(e) => patch({ maxLatencyMs: e.target.value })}
              className="rounded border border-slate-200 bg-white px-2 py-1 font-mono text-[11px] dark:border-neutral-600 dark:bg-neutral-900 dark:text-neutral-100"
            />
          </label>
          <label className="flex flex-col gap-0.5 text-[11px] text-slate-600 dark:text-neutral-400 sm:col-span-2">
            <span>Correlation request id</span>
            <input
              type="text"
              value={f.correlationRequestId}
              onChange={(e) => patch({ correlationRequestId: e.target.value })}
              className="rounded border border-slate-200 bg-white px-2 py-1 font-mono text-[11px] dark:border-neutral-600 dark:bg-neutral-900 dark:text-neutral-100"
            />
          </label>
          <label className="flex items-center gap-2 text-[11px] text-slate-700 dark:text-neutral-300 sm:col-span-2">
            <input
              type="checkbox"
              className="size-3.5 rounded border-slate-300 text-sky-600 dark:border-neutral-600"
              checked={f.sqlFilterEnabled}
              onChange={(e) => patch({ sqlFilterEnabled: e.target.checked })}
            />
            Apply SQL filter (requests / diagnosis)
          </label>
          <label className="flex flex-col gap-0.5 text-[11px] text-slate-600 dark:text-neutral-400 sm:col-span-2">
            <span>SQL filter expression</span>
            <textarea
              value={f.sqlFilterApplied}
              onChange={(e) => patch({ sqlFilterApplied: e.target.value })}
              rows={2}
              spellCheck={false}
              className="rounded border border-slate-200 bg-white px-2 py-1 font-mono text-[11px] dark:border-neutral-600 dark:bg-neutral-900 dark:text-neutral-100"
            />
          </label>
          <label className="flex flex-col gap-0.5 text-[11px] text-slate-600 dark:text-neutral-400">
            <span>Request limit</span>
            <select
              className="rounded border border-slate-200 bg-white px-2 py-1 text-xs dark:border-neutral-600 dark:bg-neutral-900 dark:text-neutral-100"
              value={f.requestLimit}
              onChange={(e) => patch({ requestLimit: Number(e.target.value) })}
            >
              {[50, 100, 200].map((n) => (
                <option key={n} value={n}>
                  {n}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-0.5 text-[11px] text-slate-600 dark:text-neutral-400">
            <span>Error group limit</span>
            <select
              className="rounded border border-slate-200 bg-white px-2 py-1 text-xs dark:border-neutral-600 dark:bg-neutral-900 dark:text-neutral-100"
              value={f.errorGroupLimit}
              onChange={(e) => patch({ errorGroupLimit: Number(e.target.value) })}
            >
              {[10, 25, 50].map((n) => (
                <option key={n} value={n}>
                  {n}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-0.5 text-[11px] text-slate-600 dark:text-neutral-400 sm:col-span-2">
            <span>Error groups sort</span>
            <select
              className="max-w-xs rounded border border-slate-200 bg-white px-2 py-1 text-xs dark:border-neutral-600 dark:bg-neutral-900 dark:text-neutral-100"
              value={f.errorGroupSort}
              onChange={(e) => patch({ errorGroupSort: e.target.value === "count" ? "count" : "last_seen" })}
            >
              <option value="last_seen">Last seen</option>
              <option value="count">Count</option>
            </select>
          </label>
        </div>
      </div>

      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          className="rounded-lg border border-slate-200 bg-white px-2 py-1 text-xs font-medium text-slate-700 shadow-sm hover:bg-slate-50 dark:border-neutral-600 dark:bg-neutral-800 dark:text-neutral-200"
          onClick={() => updateCell(index, { ...cell, filters: getLiveScopeState() })}
        >
          Capture filters from session
        </button>
        <button
          type="button"
          className="ap-btn text-xs"
          onClick={() => onApplyDashboardScope(cell.filters ?? defaultEmptyIncidentScope())}
        >
          Apply cell scope to dashboard
        </button>
        {cell.filters ? (
          <button
            type="button"
            className="rounded-lg border border-slate-200 bg-white px-2 py-1 text-xs font-medium text-slate-700 shadow-sm hover:bg-slate-50 dark:border-neutral-600 dark:bg-neutral-800 dark:text-neutral-200"
            onClick={() => updateCell(index, { ...cell, filters: null })}
          >
            Clear saved filters
          </button>
        ) : null}
      </div>
    </div>
  );
}

export function IncidentNotebook({
  storageKey,
  legacyPlaintextStorageKey,
  scopeSummary,
  scopeDetailRows,
  scopeHash,
  incidentPagePath,
  quickLinks,
  onApplyDashboardScope,
  getLiveScopeState,
  sessionOrganizationId,
}: {
  storageKey: string;
  legacyPlaintextStorageKey?: string;
  scopeSummary: string;
  scopeDetailRows: readonly string[];
  scopeHash: string;
  incidentPagePath: string;
  quickLinks: ReadonlyArray<{ label: string; href: string }>;
  onApplyDashboardScope: (state: IncidentScopeCapturedState) => void;
  getLiveScopeState: () => IncidentScopeCapturedState;
  sessionOrganizationId: string | null;
}) {
  const d = useDashboardData();
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [doc, setDoc] = useState<IncidentNotebookDocument>(() => defaultIncidentNotebook());
  const [hydrated, setHydrated] = useState(false);
  const [sqlOutputs, setSqlOutputs] = useState<Record<string, SqlOutput>>({});
  const [saveState, setSaveState] = useState<NotebookSaveState>("idle");
  const [snapshots, setSnapshots] = useState<NotebookSnapshot[]>([]);
  const [selectedSnapshotId, setSelectedSnapshotId] = useState<string>("");
  const [collapsedCellIds, setCollapsedCellIds] = useState<Set<string>>(new Set());
  const [flowChecklist, setFlowChecklist] = useState<FlowChecklist>(FLOW_CHECKLIST_DEFAULT);
  const [shareAccessMode, setShareAccessMode] = useState<"organization" | "restricted">("organization");
  const [shareExpiresDays, setShareExpiresDays] = useState(7);
  const [orgMembers, setOrgMembers] = useState<DashboardMembershipItem[]>([]);
  const [orgMembersLoad, setOrgMembersLoad] = useState<"idle" | "loading" | "ready">("idle");
  const [selectedShareUserIds, setSelectedShareUserIds] = useState<Set<string>>(() => new Set());
  const [shareBusy, setShareBusy] = useState(false);
  const [shareMessage, setShareMessage] = useState<string | null>(null);
  const [lastCreatedShareUrl, setLastCreatedShareUrl] = useState<string | null>(null);
  const [publishedShares, setPublishedShares] = useState<
    {
      id: string;
      created_at: string;
      expires_at: string;
      access_mode: string;
      allowed_user_ids: string[] | null;
      revoked_at: string | null;
    }[]
  >([]);
  const [publishedSharesLoad, setPublishedSharesLoad] = useState<"idle" | "loading" | "ready" | "error">("idle");
  const snapshotsStorageKey = `${storageKey}:snapshots.v1`;
  const flowChecklistStorageKey = `${storageKey}:flow-checklist.v1`;

  const incidentPageHref = useMemo(() => {
    if (typeof window === "undefined") {
      return incidentPagePath;
    }
    return new URL(incidentPagePath, window.location.origin).href;
  }, [incidentPagePath]);

  useEffect(() => {
    if (!sessionOrganizationId) {
      setOrgMembers([]);
      setOrgMembersLoad("idle");
      return;
    }
    let cancelled = false;
    setOrgMembersLoad("loading");
    void (async () => {
      try {
        const res = await dashboardSessionFetch(
          `/dashboard/organizations/${sessionOrganizationId}/members`,
        );
        if (!res.ok || cancelled) {
          if (!cancelled) {
            setOrgMembers([]);
          }
          return;
        }
        const raw: unknown = await res.json();
        const parsed = parseDashboardMembershipItemsPayload(raw);
        if (!cancelled) {
          setOrgMembers(parsed ?? []);
        }
      } catch {
        if (!cancelled) {
          setOrgMembers([]);
        }
      } finally {
        if (!cancelled) {
          setOrgMembersLoad("ready");
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [sessionOrganizationId]);

  const loadPublishedShares = useCallback(async () => {
    setPublishedSharesLoad("loading");
    try {
      const res = await dashboardSessionFetch("/dashboard/incident-shares?limit=50");
      if (!res.ok) {
        setPublishedSharesLoad("error");
        return;
      }
      const raw: unknown = await res.json();
      if (!Array.isArray(raw)) {
        setPublishedShares([]);
        setPublishedSharesLoad("ready");
        return;
      }
      const rows: {
        id: string;
        created_at: string;
        expires_at: string;
        access_mode: string;
        allowed_user_ids: string[] | null;
        revoked_at: string | null;
      }[] = [];
      for (const item of raw) {
        if (typeof item !== "object" || item === null) {
          continue;
        }
        const rec = item as Record<string, unknown>;
        const id = typeof rec.id === "string" ? rec.id : "";
        const created_at = typeof rec.created_at === "string" ? rec.created_at : "";
        const expires_at = typeof rec.expires_at === "string" ? rec.expires_at : "";
        const access_mode = typeof rec.access_mode === "string" ? rec.access_mode : "";
        const revoked_at =
          rec.revoked_at === null || rec.revoked_at === undefined
            ? null
            : typeof rec.revoked_at === "string"
              ? rec.revoked_at
              : null;
        let allowed_user_ids: string[] | null = null;
        if (Array.isArray(rec.allowed_user_ids)) {
          allowed_user_ids = rec.allowed_user_ids.filter((x): x is string => typeof x === "string");
        }
        if (!id || !created_at || !expires_at || !access_mode) {
          continue;
        }
        rows.push({ id, created_at, expires_at, access_mode, allowed_user_ids, revoked_at });
      }
      setPublishedShares(rows);
      setPublishedSharesLoad("ready");
    } catch {
      setPublishedSharesLoad("error");
    }
  }, []);

  useEffect(() => {
    void loadPublishedShares();
  }, [loadPublishedShares]);

  const createDbShare = useCallback(async () => {
    setShareMessage(null);
    if (shareAccessMode === "restricted" && selectedShareUserIds.size === 0) {
      setShareMessage("Select at least one user for restricted access.");
      return;
    }
    setShareBusy(true);
    try {
      const scope_state = getLiveScopeState();
      const body = {
        scope_state,
        access_mode: shareAccessMode,
        allowed_user_ids:
          shareAccessMode === "restricted" ? Array.from(selectedShareUserIds) : null,
        expires_in_days: shareExpiresDays,
      };
      const res = await dashboardSessionJsonPost("/dashboard/incident-shares", body);
      const raw: unknown = await res.json();
      if (!res.ok) {
        const detail =
          typeof raw === "object" && raw && "detail" in raw && typeof (raw as { detail: unknown }).detail === "string"
            ? (raw as { detail: string }).detail
            : `Create failed (${res.status})`;
        setShareMessage(detail);
        return;
      }
      const token =
        typeof raw === "object" && raw && "token" in raw && typeof (raw as { token: unknown }).token === "string"
          ? (raw as { token: string }).token
          : null;
      if (!token) {
        setShareMessage("Unexpected response.");
        return;
      }
      const base = new URL(
        incidentPagePath,
        typeof window !== "undefined" ? window.location.origin : "http://localhost",
      );
      base.searchParams.set("incident_share", token);
      setLastCreatedShareUrl(`${base.pathname}${base.search}${base.hash}`);
      setShareMessage("Share link created. Copy the URL below.");
      void loadPublishedShares();
    } catch (e) {
      setShareMessage(buildDashboardNetworkError(e));
    } finally {
      setShareBusy(false);
    }
  }, [
    getLiveScopeState,
    incidentPagePath,
    loadPublishedShares,
    selectedShareUserIds,
    shareAccessMode,
    shareExpiresDays,
  ]);

  const executeInput = useMemo(
    (): Omit<QueryExplorerExecuteInput, "query" | "rowLimit" | "applyTimeWindow"> => ({
      windowMinutes: d.windowMinutes,
      isAbsoluteWindow: d.isAbsoluteWindow,
      windowFromTimestamp: d.windowFromTimestamp,
      windowToTimestamp: d.windowToTimestamp,
      method: d.method,
      statusClass: d.statusClass,
      pathQuery: d.pathQuery,
      serverEnvironmentQuery: d.serverEnvironmentQuery,
      serverServiceQuery: d.serverServiceQuery,
      minLatencyMs: d.minLatencyMs,
      maxLatencyMs: d.maxLatencyMs,
      sqlFilterEnabled: d.sqlFilterEnabled,
      sqlFilterApplied: d.sqlFilterApplied,
    }),
    [
      d.isAbsoluteWindow,
      d.maxLatencyMs,
      d.method,
      d.minLatencyMs,
      d.pathQuery,
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

  const persistSnapshots = useCallback(
    (next: NotebookSnapshot[]) => {
      setSnapshots(next);
      try {
        window.localStorage.setItem(snapshotsStorageKey, JSON.stringify(next));
      } catch {
        /* ignore */
      }
    },
    [snapshotsStorageKey],
  );

  useEffect(() => {
    let raw: string | null = null;
    try {
      raw = window.localStorage.getItem(storageKey);
    } catch {
      raw = null;
    }
    if (!raw && legacyPlaintextStorageKey) {
      try {
        raw = window.localStorage.getItem(legacyPlaintextStorageKey);
      } catch {
        raw = null;
      }
    }
    if (raw) {
      const parsed = parseIncidentNotebookJson(raw);
      if (parsed) {
        setDoc(parsed);
      } else if (raw.trim() && !raw.trim().startsWith("{")) {
        setDoc({
          version: 1,
          cells: [newTextCell(raw)],
        });
      } else {
        setDoc(defaultIncidentNotebook());
      }
    } else {
      setDoc(defaultIncidentNotebook());
    }
    try {
      const snapshotRaw = window.localStorage.getItem(snapshotsStorageKey);
      const list = parseSnapshotList(snapshotRaw).sort((a, b) => b.savedAtIso.localeCompare(a.savedAtIso));
      setSnapshots(list);
      setSelectedSnapshotId((prev) => prev || list[0]?.id || "");
    } catch {
      setSnapshots([]);
    }
    try {
      const flowRaw = window.localStorage.getItem(flowChecklistStorageKey);
      setFlowChecklist(parseFlowChecklist(flowRaw));
    } catch {
      setFlowChecklist(FLOW_CHECKLIST_DEFAULT);
    }
    setHydrated(true);
  }, [flowChecklistStorageKey, legacyPlaintextStorageKey, snapshotsStorageKey, storageKey]);

  useEffect(() => {
    if (!hydrated) {
      return;
    }
    setSaveState("saving");
    const handle = window.setTimeout(() => {
      try {
        window.localStorage.setItem(storageKey, serializeIncidentNotebook(doc));
        setSaveState("saved");
      } catch {
        setSaveState("error");
      }
    }, 350);
    return () => window.clearTimeout(handle);
  }, [doc, hydrated, storageKey]);

  useEffect(() => {
    if (!hydrated) {
      return;
    }
    try {
      window.localStorage.setItem(flowChecklistStorageKey, JSON.stringify(flowChecklist));
    } catch {
      /* ignore */
    }
  }, [flowChecklist, flowChecklistStorageKey, hydrated]);

  const updateCell = useCallback((index: number, next: IncidentNotebookCell) => {
    setDoc((prev) => {
      const cells = [...prev.cells];
      cells[index] = next;
      return { ...prev, cells };
    });
  }, []);

  const runSqlCell = useCallback(
    async (cell: Extract<IncidentNotebookCell, { type: "sql" }>) => {
      const q = cell.source.trim();
      if (!q) {
        setSqlOutputs((o) => ({
          ...o,
          [cell.id]: { loading: false, error: "Empty query.", data: null },
        }));
        return;
      }
      setSqlOutputs((o) => ({ ...o, [cell.id]: { loading: true, error: null, data: o[cell.id]?.data ?? null } }));
      try {
        const body = buildQueryExplorerExecutePayload({
          ...executeInput,
          query: q,
          rowLimit: cell.rowLimit,
          applyTimeWindow: cell.applyTimeWindow,
        });
        const response = await dashboardSessionJsonPost("/dashboard/query-explorer/execute", body);
        const rawResponse: unknown = await response.json();
        if (!response.ok) {
          const detail =
            typeof rawResponse === "object" &&
            rawResponse !== null &&
            "detail" in rawResponse &&
            typeof (rawResponse as { detail: unknown }).detail === "string"
              ? (rawResponse as { detail: string }).detail
              : `Query failed (${response.status})`;
          setSqlOutputs((o) => ({ ...o, [cell.id]: { loading: false, error: detail, data: null } }));
          return;
        }
        const parsed = parseQueryExplorerResponse(rawResponse);
        if (!parsed) {
          setSqlOutputs((o) => ({
            ...o,
            [cell.id]: { loading: false, error: "Unexpected response shape from server.", data: null },
          }));
          return;
        }
        setSqlOutputs((o) => ({ ...o, [cell.id]: { loading: false, error: null, data: parsed } }));
      } catch (err) {
        setSqlOutputs((o) => ({
          ...o,
          [cell.id]: { loading: false, error: buildDashboardNetworkError(err), data: null },
        }));
      }
    },
    [executeInput],
  );

  const addSnapshot = useCallback(() => {
    const defaultName = `Snapshot ${new Date().toLocaleString()}`;
    const name = window.prompt("Save notebook snapshot as:", defaultName)?.trim();
    if (!name) {
      return;
    }
    const payload = serializeIncidentNotebook(doc);
    const snapshot: NotebookSnapshot = {
      id: randomId(),
      name,
      savedAtIso: new Date().toISOString(),
      payload,
    };
    const next = [snapshot, ...snapshots].slice(0, 30);
    persistSnapshots(next);
    setSelectedSnapshotId(snapshot.id);
  }, [doc, persistSnapshots, snapshots]);

  const loadSnapshot = useCallback(() => {
    if (!selectedSnapshotId) {
      return;
    }
    const found = snapshots.find((item) => item.id === selectedSnapshotId);
    if (!found) {
      return;
    }
    const parsed = parseIncidentNotebookJson(found.payload);
    if (!parsed) {
      window.alert("Saved snapshot is not valid notebook JSON.");
      return;
    }
    if (!window.confirm(`Replace notebook with "${found.name}"?`)) {
      return;
    }
    setDoc(parsed);
    setSqlOutputs({});
  }, [selectedSnapshotId, snapshots]);

  const deleteSnapshot = useCallback(() => {
    if (!selectedSnapshotId) {
      return;
    }
    const found = snapshots.find((item) => item.id === selectedSnapshotId);
    if (!found) {
      return;
    }
    if (!window.confirm(`Delete snapshot "${found.name}"?`)) {
      return;
    }
    const next = snapshots.filter((item) => item.id !== selectedSnapshotId);
    persistSnapshots(next);
    setSelectedSnapshotId(next[0]?.id ?? "");
  }, [persistSnapshots, selectedSnapshotId, snapshots]);

  const exportNotebook = useCallback(() => {
    const blob = new Blob([serializeIncidentNotebook(doc)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `incident-notebook-${scopeHash}.json`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  }, [doc, scopeHash]);

  const handleImportClick = useCallback(() => {
    fileInputRef.current?.click();
  }, []);

  const importNotebookFile = useCallback(async (file: File) => {
    let text: string;
    try {
      text = await file.text();
    } catch {
      window.alert("Could not read file.");
      return;
    }
    const parsed = parseIncidentNotebookJson(text);
    if (!parsed) {
      window.alert("File is not valid incident notebook JSON.");
      return;
    }
    if (!window.confirm("Replace current notebook with imported file?")) {
      return;
    }
    setDoc(parsed);
    setSqlOutputs({});
  }, []);

  const copyNotebookJson = useCallback(async () => {
    const json = serializeIncidentNotebook(doc);
    try {
      await navigator.clipboard.writeText(json);
    } catch {
      window.prompt("Copy notebook JSON (Ctrl+C / Cmd+C):", json);
    }
  }, [doc]);

  const copyHandoffBrief = useCallback(async () => {
    const brief = buildHandoffBrief(doc, scopeSummary, quickLinks, incidentPageHref);
    try {
      await navigator.clipboard.writeText(brief);
    } catch {
      window.prompt("Copy handoff brief (Ctrl+C / Cmd+C):", brief);
    }
  }, [doc, incidentPageHref, quickLinks, scopeSummary]);

  const applyStarterTemplate = useCallback(() => {
    if (!window.confirm("Replace notebook with the incident starter template?")) {
      return;
    }
    setDoc({
      version: 1,
      cells: [
        newScopeCell("Scope locked for incident triage.", null),
        newMarkdownCell("## Symptom\n\nWhat broke and how is user impact showing up?"),
        newSqlCell(
          [
            "SELECT",
            "  status_code,",
            "  COUNT(*) AS requests,",
            "  AVG(latency_ms) AS avg_latency_ms",
            "FROM scoped_events",
            "GROUP BY 1",
            "ORDER BY requests DESC",
          ].join("\n"),
          200,
          true,
        ),
        newMarkdownCell(
          [
            "## Findings timeline",
            "",
            "- [time] Observation",
            "- [time] Hypothesis",
            "- [time] Validation result",
          ].join("\n"),
        ),
      ],
    });
    setSqlOutputs({});
    setCollapsedCellIds(new Set());
  }, []);

  const appendInvestigationBundle = useCallback(() => {
    setDoc((prev) => ({
      ...prev,
      cells: [
        ...prev.cells,
        newDividerCell(),
        newMarkdownCell("## Hypotheses\n\n- Hypothesis A\n- Hypothesis B"),
        newTextCell("Decision log:\n- Tested:\n- Result:\n- Next:"),
        newSqlCell(
          [
            "SELECT",
            "  service_name,",
            "  environment,",
            "  COUNT(*) AS requests,",
            "  SUM(CASE WHEN status_code >= 500 THEN 1 ELSE 0 END) AS errors_5xx",
            "FROM scoped_events",
            "GROUP BY 1, 2",
            "ORDER BY errors_5xx DESC, requests DESC",
          ].join("\n"),
          200,
          true,
        ),
      ],
    }));
  }, []);

  const appendHandoffBundle = useCallback(() => {
    setDoc((prev) => ({
      ...prev,
      cells: [
        ...prev.cells,
        newDividerCell(),
        newMarkdownCell(
          [
            "## Handoff summary",
            "",
            "### Impact",
            "-",
            "",
            "### Root cause confidence",
            "-",
            "",
            "### Mitigation / rollback",
            "-",
            "",
            "### Next owner",
            "-",
          ].join("\n"),
        ),
      ],
    }));
  }, []);

  const toggleCellCollapsed = useCallback((cellId: string) => {
    setCollapsedCellIds((prev) => {
      const next = new Set(prev);
      if (next.has(cellId)) {
        next.delete(cellId);
      } else {
        next.add(cellId);
      }
      return next;
    });
  }, []);

  const duplicateCellAt = useCallback((index: number) => {
    setDoc((prev) => {
      const original = prev.cells[index];
      if (!original) {
        return prev;
      }
      const nextCells = [...prev.cells];
      nextCells.splice(index + 1, 0, cloneCell(original));
      return { ...prev, cells: nextCells };
    });
  }, []);

  const cellShell =
    "rounded-xl border border-slate-200/90 bg-white shadow-sm dark:border-neutral-700 dark:bg-neutral-900";

  if (!hydrated) {
    return <CardSpinner size="compact" label="Loading notebook..." />;
  }

  return (
    <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_20rem]">
      <div className="space-y-4">
        <div className="rounded-xl border border-slate-200/90 bg-slate-50/70 p-3 dark:border-neutral-700 dark:bg-neutral-900/70">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-600 dark:text-neutral-300">
                Notebook storage
              </p>
              <p className="mt-1 text-xs text-slate-600 dark:text-neutral-400">
                Autosave:{" "}
                <span className="font-medium text-slate-800 dark:text-neutral-100">
                  {saveState === "saving"
                    ? "Saving..."
                    : saveState === "saved"
                      ? "Saved"
                      : saveState === "error"
                        ? "Failed (localStorage unavailable)"
                        : "Idle"}
                </span>
              </p>
              <p className="mt-1 text-[11px] text-slate-500 dark:text-neutral-500">
                Scope key <code className="rounded bg-white px-1 dark:bg-neutral-950">{scopeHash}</code>
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <button
                type="button"
                className="inline-flex items-center gap-1 rounded-lg border border-slate-200 bg-white px-2 py-1 text-xs font-medium text-slate-700 shadow-sm hover:bg-slate-50 dark:border-neutral-600 dark:bg-neutral-800 dark:text-neutral-200 dark:hover:bg-neutral-700"
                onClick={addSnapshot}
              >
                <ClipboardList className="size-3.5" aria-hidden /> Save snapshot
              </button>
              <select
                className="rounded-lg border border-slate-200 bg-white px-2 py-1 text-xs text-slate-700 dark:border-neutral-600 dark:bg-neutral-800 dark:text-neutral-100"
                value={selectedSnapshotId}
                onChange={(e) => setSelectedSnapshotId(e.target.value)}
              >
                <option value="">Choose snapshot...</option>
                {snapshots.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.name} - {formatSavedAt(item.savedAtIso)}
                  </option>
                ))}
              </select>
              <button
                type="button"
                className="rounded-lg border border-slate-200 bg-white px-2 py-1 text-xs font-medium text-slate-700 shadow-sm hover:bg-slate-50 disabled:opacity-50 dark:border-neutral-600 dark:bg-neutral-800 dark:text-neutral-100 dark:hover:bg-neutral-700"
                disabled={!selectedSnapshotId}
                onClick={loadSnapshot}
              >
                Load
              </button>
              <button
                type="button"
                className="rounded-lg border border-rose-200 bg-white px-2 py-1 text-xs font-medium text-rose-700 shadow-sm hover:bg-rose-50 disabled:opacity-50 dark:border-rose-900/40 dark:bg-neutral-800 dark:text-rose-300 dark:hover:bg-rose-950/40"
                disabled={!selectedSnapshotId}
                onClick={deleteSnapshot}
              >
                Delete
              </button>
              <button
                type="button"
                className="rounded-lg border border-slate-200 bg-white px-2 py-1 text-xs font-medium text-slate-700 shadow-sm hover:bg-slate-50 dark:border-neutral-600 dark:bg-neutral-800 dark:text-neutral-100 dark:hover:bg-neutral-700"
                onClick={copyNotebookJson}
              >
                Copy JSON
              </button>
              <button
                type="button"
                className="rounded-lg border border-slate-200 bg-white px-2 py-1 text-xs font-medium text-slate-700 shadow-sm hover:bg-slate-50 dark:border-neutral-600 dark:bg-neutral-800 dark:text-neutral-100 dark:hover:bg-neutral-700"
                onClick={copyHandoffBrief}
              >
                Copy handoff brief
              </button>
              <button
                type="button"
                className="rounded-lg border border-slate-200 bg-white px-2 py-1 text-xs font-medium text-slate-700 shadow-sm hover:bg-slate-50 dark:border-neutral-600 dark:bg-neutral-800 dark:text-neutral-100 dark:hover:bg-neutral-700"
                onClick={exportNotebook}
              >
                Export
              </button>
              <button
                type="button"
                className="rounded-lg border border-slate-200 bg-white px-2 py-1 text-xs font-medium text-slate-700 shadow-sm hover:bg-slate-50 dark:border-neutral-600 dark:bg-neutral-800 dark:text-neutral-100 dark:hover:bg-neutral-700"
                onClick={handleImportClick}
              >
                Import
              </button>
              <input
                ref={fileInputRef}
                type="file"
                className="hidden"
                accept=".json,application/json"
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (file) {
                    void importNotebookFile(file);
                  }
                  e.currentTarget.value = "";
                }}
              />
            </div>
          </div>
        </div>

        <div className="rounded-xl border border-slate-200/90 bg-white p-3 shadow-sm dark:border-neutral-700 dark:bg-neutral-900">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs font-medium uppercase tracking-wide text-slate-500 dark:text-neutral-400">Templates</span>
            <button
              type="button"
              className="inline-flex items-center gap-1 rounded-lg border border-sky-200 bg-sky-50 px-2 py-1 text-xs font-medium text-sky-800 shadow-sm hover:bg-sky-100 dark:border-sky-900/40 dark:bg-sky-950/40 dark:text-sky-200 dark:hover:bg-sky-950/60"
              onClick={applyStarterTemplate}
            >
              Apply starter template
            </button>
            <button
              type="button"
              className="inline-flex items-center gap-1 rounded-lg border border-slate-200 bg-white px-2 py-1 text-xs font-medium text-slate-700 shadow-sm hover:bg-slate-50 dark:border-neutral-600 dark:bg-neutral-800 dark:text-neutral-200 dark:hover:bg-neutral-700"
              onClick={appendInvestigationBundle}
            >
              Add investigation bundle
            </button>
            <button
              type="button"
              className="inline-flex items-center gap-1 rounded-lg border border-slate-200 bg-white px-2 py-1 text-xs font-medium text-slate-700 shadow-sm hover:bg-slate-50 dark:border-neutral-600 dark:bg-neutral-800 dark:text-neutral-200 dark:hover:bg-neutral-700"
              onClick={appendHandoffBundle}
            >
              Add handoff bundle
            </button>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs font-medium uppercase tracking-wide text-slate-500 dark:text-neutral-400">Cells</span>
          <button
            type="button"
            className="inline-flex items-center gap-1 rounded-lg border border-slate-200 bg-white px-2 py-1 text-xs font-medium text-slate-700 shadow-sm hover:bg-slate-50 dark:border-neutral-600 dark:bg-neutral-800 dark:text-neutral-200 dark:hover:bg-neutral-700"
            onClick={() => setDoc((p) => ({ ...p, cells: [...p.cells, newScopeCell()] }))}
          >
            <Plus className="size-3.5" aria-hidden /> Scope
          </button>
          <button
            type="button"
            className="inline-flex items-center gap-1 rounded-lg border border-slate-200 bg-white px-2 py-1 text-xs font-medium text-slate-700 shadow-sm hover:bg-slate-50 dark:border-neutral-600 dark:bg-neutral-800 dark:text-neutral-200 dark:hover:bg-neutral-700"
            onClick={() => setDoc((p) => ({ ...p, cells: [...p.cells, newMarkdownCell()] }))}
          >
            <Plus className="size-3.5" aria-hidden /> Markdown
          </button>
          <button
            type="button"
            className="inline-flex items-center gap-1 rounded-lg border border-slate-200 bg-white px-2 py-1 text-xs font-medium text-slate-700 shadow-sm hover:bg-slate-50 dark:border-neutral-600 dark:bg-neutral-800 dark:text-neutral-200 dark:hover:bg-neutral-700"
            onClick={() => setDoc((p) => ({ ...p, cells: [...p.cells, newTextCell()] }))}
          >
            <Plus className="size-3.5" aria-hidden /> Note
          </button>
          <button
            type="button"
            className="inline-flex items-center gap-1 rounded-lg border border-slate-200 bg-white px-2 py-1 text-xs font-medium text-slate-700 shadow-sm hover:bg-slate-50 dark:border-neutral-600 dark:bg-neutral-800 dark:text-neutral-200 dark:hover:bg-neutral-700"
            onClick={() => setDoc((p) => ({ ...p, cells: [...p.cells, newSqlCell()] }))}
          >
            <Plus className="size-3.5" aria-hidden /> SQL
          </button>
          <button
            type="button"
            className="inline-flex items-center gap-1 rounded-lg border border-slate-200 bg-white px-2 py-1 text-xs font-medium text-slate-700 shadow-sm hover:bg-slate-50 dark:border-neutral-600 dark:bg-neutral-800 dark:text-neutral-200 dark:hover:bg-neutral-700"
            onClick={() => setDoc((p) => ({ ...p, cells: [...p.cells, newDividerCell()] }))}
          >
            <Plus className="size-3.5" aria-hidden /> Divider
          </button>
          <button
            type="button"
            className="inline-flex items-center gap-1 rounded-lg border border-slate-200 bg-white px-2 py-1 text-xs font-medium text-slate-700 shadow-sm hover:bg-slate-50 dark:border-neutral-600 dark:bg-neutral-800 dark:text-neutral-200 dark:hover:bg-neutral-700"
            onClick={() => setDoc((p) => ({ ...p, cells: [...p.cells, newChecklistCell()] }))}
          >
            <Plus className="size-3.5" aria-hidden /> Checklist
          </button>
          <button
            type="button"
            className="inline-flex items-center gap-1 rounded-lg border border-slate-200 bg-white px-2 py-1 text-xs font-medium text-slate-700 shadow-sm hover:bg-slate-50 dark:border-neutral-600 dark:bg-neutral-800 dark:text-neutral-200 dark:hover:bg-neutral-700"
            onClick={() => setDoc((p) => ({ ...p, cells: [...p.cells, newLinkCell()] }))}
          >
            <Plus className="size-3.5" aria-hidden /> Link
          </button>
          <button
            type="button"
            className="ml-auto text-xs text-rose-600 hover:underline dark:text-rose-400"
            onClick={() => {
              if (window.confirm("Reset the entire notebook to the default template?")) {
                setDoc(defaultIncidentNotebook());
                setSqlOutputs({});
                setCollapsedCellIds(new Set());
              }
            }}
          >
            Reset notebook
          </button>
        </div>

        <div className="space-y-3">
          {doc.cells.map((cell, index) => {
            const collapsed = collapsedCellIds.has(cell.id);
            if (cell.type === "divider") {
              return (
                <div key={cell.id} className={`${cellShell} flex items-center gap-2 px-3 py-2`}>
                  <span className="text-[10px] font-semibold uppercase tracking-wide text-slate-400 dark:text-neutral-500">
                    Divider
                  </span>
                  <hr className="min-w-0 flex-1 border-slate-200 dark:border-neutral-600" />
                  <button
                    type="button"
                    aria-label="Move row up"
                    className="rounded p-1 text-slate-500 hover:bg-slate-100 disabled:opacity-30 dark:hover:bg-neutral-800"
                    disabled={index === 0}
                    onClick={() => setDoc((p) => ({ ...p, cells: moveCell(p.cells, index, -1) }))}
                  >
                    <ChevronUp className="size-4" />
                  </button>
                  <button
                    type="button"
                    aria-label="Move row down"
                    className="rounded p-1 text-slate-500 hover:bg-slate-100 disabled:opacity-30 dark:hover:bg-neutral-800"
                    disabled={index >= doc.cells.length - 1}
                    onClick={() => setDoc((p) => ({ ...p, cells: moveCell(p.cells, index, 1) }))}
                  >
                    <ChevronDown className="size-4" />
                  </button>
                  <button
                    type="button"
                    aria-label="Delete row"
                    className="rounded p-1 text-rose-600 hover:bg-rose-50 dark:hover:bg-rose-950/40"
                    disabled={doc.cells.length <= 1}
                    onClick={() =>
                      setDoc((p) => ({
                        ...p,
                        cells: p.cells.length <= 1 ? p.cells : removeCellAt(p.cells, index),
                      }))
                    }
                  >
                    <Trash2 className="size-4" />
                  </button>
                </div>
              );
            }

            const isMd = cell.type === "markdown";
            const isText = cell.type === "text";
            const isSql = cell.type === "sql";
            const isChecklist = cell.type === "checklist";
            const isLink = cell.type === "link";
            const cellTypeLabel = isMd
              ? "Markdown"
              : isText
                ? "Note"
                : isSql
                  ? "SQL"
                  : cell.type === "scope"
                    ? "Scope"
                    : isChecklist
                      ? "Checklist"
                      : isLink
                        ? "Link"
                        : "Cell";

            return (
              <div key={cell.id} className={cellShell}>
                <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 px-3 py-2 dark:border-neutral-800">
                  <span className="text-[10px] font-bold uppercase tracking-wide text-slate-500 dark:text-neutral-400">
                    {cellTypeLabel}
                  </span>
                  <div className="flex items-center gap-1">
                    <button
                      type="button"
                      className="rounded px-1.5 py-0.5 text-[11px] text-slate-600 hover:bg-slate-100 dark:text-neutral-300 dark:hover:bg-neutral-800"
                      onClick={() => toggleCellCollapsed(cell.id)}
                    >
                      {collapsed ? "Expand" : "Collapse"}
                    </button>
                    <button
                      type="button"
                      className="rounded px-1.5 py-0.5 text-[11px] text-slate-600 hover:bg-slate-100 dark:text-neutral-300 dark:hover:bg-neutral-800"
                      onClick={() => duplicateCellAt(index)}
                    >
                      Duplicate
                    </button>
                    <button
                      type="button"
                      aria-label="Move row up"
                      className="rounded p-1 text-slate-500 hover:bg-slate-100 disabled:opacity-30 dark:hover:bg-neutral-800"
                      disabled={index === 0}
                      onClick={() => setDoc((p) => ({ ...p, cells: moveCell(p.cells, index, -1) }))}
                    >
                      <ChevronUp className="size-4" />
                    </button>
                    <button
                      type="button"
                      aria-label="Move row down"
                      className="rounded p-1 text-slate-500 hover:bg-slate-100 disabled:opacity-30 dark:hover:bg-neutral-800"
                      disabled={index >= doc.cells.length - 1}
                      onClick={() => setDoc((p) => ({ ...p, cells: moveCell(p.cells, index, 1) }))}
                    >
                      <ChevronDown className="size-4" />
                    </button>
                    <button
                      type="button"
                      aria-label="Delete row"
                      className="rounded p-1 text-rose-600 hover:bg-rose-50 dark:hover:bg-rose-950/40 disabled:opacity-30"
                      disabled={doc.cells.length <= 1}
                      onClick={() =>
                        setDoc((p) => ({
                          ...p,
                          cells: p.cells.length <= 1 ? p.cells : removeCellAt(p.cells, index),
                        }))
                      }
                    >
                      <Trash2 className="size-4" />
                    </button>
                  </div>
                </div>

                {collapsed ? (
                  <div className="px-3 py-2 text-xs text-slate-600 dark:text-neutral-300">{briefCell(cell)}</div>
                ) : (
                  <div className="p-3">
                    {cell.type === "scope" ? (
                      <>
                        <IncidentScopeCellBody
                          cell={cell}
                          index={index}
                          updateCell={updateCell}
                          onApplyDashboardScope={onApplyDashboardScope}
                          getLiveScopeState={getLiveScopeState}
                          scopeSummary={scopeSummary}
                          scopeDetailRows={scopeDetailRows}
                          methodOptions={d.METHOD_OPTIONS}
                          statusClassOptions={d.STATUS_CLASS_OPTIONS}
                        />
                        <textarea
                          value={cell.source}
                          onChange={(e) => updateCell(index, { ...cell, source: e.target.value })}
                          rows={4}
                          spellCheck
                          placeholder="Optional scope notes (why this scope, missing filters, etc.)"
                          className="mt-3 w-full rounded-lg border border-slate-200 bg-slate-50/80 px-3 py-2 text-xs text-slate-900 dark:border-neutral-600 dark:bg-neutral-950 dark:text-neutral-100"
                          aria-label="Scope notes cell"
                        />
                      </>
                    ) : null}

                    {(isMd || isText) && (
                      <textarea
                        value={cell.source}
                        onChange={(e) => updateCell(index, { ...cell, source: e.target.value })}
                        rows={isMd ? 8 : 5}
                        spellCheck={isText}
                        className="w-full rounded-lg border border-slate-200 bg-slate-50/80 px-3 py-2 font-mono text-xs text-slate-900 dark:border-neutral-600 dark:bg-neutral-950 dark:text-neutral-100"
                        aria-label={isMd ? "Markdown cell" : "Note cell"}
                      />
                    )}
                    {isMd ? (
                      <div className="mt-3 rounded-lg border border-slate-100 bg-white px-3 py-2 dark:border-neutral-800 dark:bg-neutral-950">
                        <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-500 dark:text-neutral-400">
                          Rendered markdown
                        </p>
                        <div className="mt-2 max-h-[28rem] overflow-y-auto">
                          <IncidentMarkdownBody markdown={cell.source} />
                        </div>
                      </div>
                    ) : null}

                    {isChecklist ? (
                      <div className="space-y-2">
                        <input
                          type="text"
                          value={cell.title}
                          onChange={(e) => updateCell(index, { ...cell, title: e.target.value })}
                          placeholder="Checklist title"
                          className="w-full rounded-lg border border-slate-200 bg-white px-2 py-1.5 text-sm font-medium text-slate-900 dark:border-neutral-600 dark:bg-neutral-900 dark:text-neutral-100"
                        />
                        <ul className="space-y-2">
                          {cell.items.map((it, itemIdx) => (
                            <li key={it.id} className="flex items-start gap-2">
                              <input
                                type="checkbox"
                                className="mt-1 size-3.5 rounded border-slate-300 text-sky-600 dark:border-neutral-600"
                                checked={it.checked}
                                onChange={(e) => {
                                  const items = cell.items.map((row, j) =>
                                    j === itemIdx ? { ...row, checked: e.target.checked } : row,
                                  );
                                  updateCell(index, { ...cell, items });
                                }}
                              />
                              <input
                                type="text"
                                value={it.text}
                                onChange={(e) => {
                                  const items = cell.items.map((row, j) =>
                                    j === itemIdx ? { ...row, text: e.target.value } : row,
                                  );
                                  updateCell(index, { ...cell, items });
                                }}
                                className="min-w-0 flex-1 rounded border border-slate-200 bg-white px-2 py-1 text-xs dark:border-neutral-600 dark:bg-neutral-900 dark:text-neutral-100"
                              />
                              <button
                                type="button"
                                className="shrink-0 text-rose-600 text-xs hover:underline dark:text-rose-400"
                                onClick={() => {
                                  const items = cell.items.filter((_, j) => j !== itemIdx);
                                  updateCell(index, {
                                    ...cell,
                                    items: items.length ? items : [{ id: randomId(), text: "", checked: false }],
                                  });
                                }}
                              >
                                Remove
                              </button>
                            </li>
                          ))}
                        </ul>
                        <button
                          type="button"
                          className="text-xs font-medium text-sky-700 hover:underline dark:text-sky-300"
                          onClick={() =>
                            updateCell(index, {
                              ...cell,
                              items: [...cell.items, { id: randomId(), text: "", checked: false }],
                            })
                          }
                        >
                          Add item
                        </button>
                      </div>
                    ) : null}

                    {isLink ? (
                      <div className="space-y-2">
                        <input
                          type="text"
                          value={cell.label}
                          onChange={(e) => updateCell(index, { ...cell, label: e.target.value })}
                          placeholder="Link label"
                          className="w-full rounded-lg border border-slate-200 bg-white px-2 py-1.5 text-xs dark:border-neutral-600 dark:bg-neutral-900 dark:text-neutral-100"
                        />
                        <input
                          type="url"
                          value={cell.href}
                          onChange={(e) => updateCell(index, { ...cell, href: e.target.value })}
                          placeholder="https://…"
                          className="w-full rounded-lg border border-slate-200 bg-white px-2 py-1.5 font-mono text-xs dark:border-neutral-600 dark:bg-neutral-900 dark:text-neutral-100"
                        />
                        <textarea
                          value={cell.note}
                          onChange={(e) => updateCell(index, { ...cell, note: e.target.value })}
                          rows={2}
                          placeholder="Optional note"
                          className="w-full rounded-lg border border-slate-200 bg-slate-50/80 px-2 py-1.5 text-xs dark:border-neutral-600 dark:bg-neutral-950 dark:text-neutral-100"
                        />
                        {cell.href.trim() ? (
                          <Link
                            href={cell.href.trim()}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-flex items-center gap-1 text-xs font-medium text-sky-700 hover:underline dark:text-sky-300"
                          >
                            Open link <ExternalLink className="size-3" aria-hidden />
                          </Link>
                        ) : null}
                      </div>
                    ) : null}

                    {isSql && (
                      <>
                        <textarea
                          value={cell.source}
                          onChange={(e) => updateCell(index, { ...cell, source: e.target.value })}
                          rows={10}
                          spellCheck={false}
                          className="w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 font-mono text-xs text-slate-900 dark:border-neutral-600 dark:bg-neutral-950 dark:text-neutral-100"
                          aria-label="SQL cell"
                        />
                        <div className="mt-2 flex flex-wrap items-center gap-3">
                          <label className="flex cursor-pointer items-center gap-2 text-xs text-slate-600 dark:text-neutral-300">
                            <input
                              type="checkbox"
                              className="size-3.5 rounded border-slate-300 text-sky-600 dark:border-neutral-600"
                              checked={cell.applyTimeWindow}
                              onChange={(e) =>
                                updateCell(index, {
                                  ...cell,
                                  applyTimeWindow: e.target.checked,
                                })
                              }
                            />
                            Limit to incident time window
                          </label>
                          <label className="text-xs text-slate-600 dark:text-neutral-300">
                            Row limit{" "}
                            <input
                              type="number"
                              min={1}
                              max={500}
                              value={cell.rowLimit}
                              onChange={(e) =>
                                updateCell(index, {
                                  ...cell,
                                  rowLimit: Math.max(1, Math.min(500, Number(e.target.value) || 1)),
                                })
                              }
                              className="ml-1 w-20 rounded border border-slate-200 bg-white px-2 py-0.5 dark:border-neutral-600 dark:bg-neutral-900"
                            />
                          </label>
                          <button
                            type="button"
                            className="ap-btn text-xs"
                            disabled={sqlOutputs[cell.id]?.loading}
                            onClick={() => void runSqlCell(cell)}
                          >
                            {sqlOutputs[cell.id]?.loading ? "Running..." : "Run"}
                          </button>
                        </div>
                        {sqlOutputs[cell.id]?.error ? (
                          <p className="mt-2 rounded-lg border border-rose-300 bg-rose-50 px-2 py-1.5 text-xs text-rose-800 dark:border-rose-900/50 dark:bg-rose-950/30 dark:text-rose-200">
                            {sqlOutputs[cell.id]?.error}
                          </p>
                        ) : null}
                        {sqlOutputs[cell.id]?.loading ? (
                          <CardSpinner className="mt-3" size="compact" label="Executing SQL..." />
                        ) : null}
                        {sqlOutputs[cell.id]?.data ? (
                          <div className="mt-2">
                            <p className="text-[11px] text-slate-500 dark:text-neutral-400">
                              {sqlOutputs[cell.id]!.data!.rows.length} row(s)
                              {sqlOutputs[cell.id]!.data!.truncated ? " (truncated)" : ""}
                            </p>
                            <ResultTable data={sqlOutputs[cell.id]!.data!} />
                          </div>
                        ) : null}
                      </>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>

        <p className="text-[11px] leading-relaxed text-slate-500 dark:text-neutral-500">
          Notebook data is local to this browser under this incident scope. SQL uses the same{" "}
          <code className="rounded bg-slate-100 px-1 dark:bg-neutral-800">scoped_events</code> rules as Query Explorer
          (read-only <code className="rounded bg-slate-100 px-1 dark:bg-neutral-800">SELECT</code> / CTE).
        </p>
      </div>

      <aside className="space-y-3">
        <div className="rounded-xl border border-slate-200/90 bg-white p-3 shadow-sm dark:border-neutral-700 dark:bg-neutral-900">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-600 dark:text-neutral-300">
            Incident flow
          </p>
          <div className="mt-2 space-y-2 text-xs text-slate-700 dark:text-neutral-200">
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={flowChecklist.captured}
                onChange={(e) =>
                  setFlowChecklist((prev) => ({
                    ...prev,
                    captured: e.target.checked,
                  }))
                }
              />
              Scope + symptom captured
            </label>
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={flowChecklist.investigated}
                onChange={(e) =>
                  setFlowChecklist((prev) => ({
                    ...prev,
                    investigated: e.target.checked,
                  }))
                }
              />
              Evidence query + findings logged
            </label>
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={flowChecklist.handoffReady}
                onChange={(e) =>
                  setFlowChecklist((prev) => ({
                    ...prev,
                    handoffReady: e.target.checked,
                  }))
                }
              />
              Handoff brief + snapshot ready
            </label>
          </div>
        </div>

        <div className="rounded-xl border border-slate-200/90 bg-white p-3 shadow-sm dark:border-neutral-700 dark:bg-neutral-900">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-600 dark:text-neutral-300">
            Investigation links
          </p>
          <div className="mt-2 space-y-2">
            {quickLinks.map((item) => (
              <Link
                key={item.label}
                href={item.href}
                className="group flex items-center justify-between rounded-lg border border-slate-200/90 px-2 py-1.5 text-xs text-slate-700 hover:border-sky-300 hover:bg-sky-50 dark:border-neutral-700 dark:text-neutral-200 dark:hover:border-sky-600/60 dark:hover:bg-sky-950/30"
              >
                <span>{item.label}</span>
                <ExternalLink className="size-3.5 text-slate-400 group-hover:text-sky-600 dark:text-neutral-500 dark:group-hover:text-sky-300" />
              </Link>
            ))}
          </div>
        </div>

        <div className="rounded-xl border border-slate-200/90 bg-white p-3 shadow-sm dark:border-neutral-700 dark:bg-neutral-900">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-600 dark:text-neutral-300">
            DB-backed share link
          </p>
          <p className="mt-1 text-[11px] leading-relaxed text-slate-600 dark:text-neutral-400">
            Stored on the server with expiry and access control. Recipients must be signed in to the same project.
          </p>
          <label className="mt-2 block text-[11px] font-medium text-slate-700 dark:text-neutral-200">Access</label>
          <select
            className="mt-1 w-full rounded-lg border border-slate-200 bg-white px-2 py-1 text-xs dark:border-neutral-600 dark:bg-neutral-800 dark:text-neutral-100"
            value={shareAccessMode}
            onChange={(e) => setShareAccessMode(e.target.value as "organization" | "restricted")}
          >
            <option value="organization">All organization members with project access</option>
            <option value="restricted">Selected users only</option>
          </select>
          {shareAccessMode === "restricted" ? (
            <div className="mt-2 max-h-40 space-y-1 overflow-y-auto rounded-lg border border-slate-100 p-2 dark:border-neutral-800">
              {orgMembersLoad === "loading" ? (
                <p className="text-[11px] text-slate-500">Loading members…</p>
              ) : orgMembers.length === 0 ? (
                <p className="text-[11px] text-slate-500">No members loaded. Open Settings if your org is missing.</p>
              ) : (
                orgMembers.map((m) => (
                  <label key={m.user_id} className="flex items-center gap-2 text-[11px] text-slate-700 dark:text-neutral-200">
                    <input
                      type="checkbox"
                      checked={selectedShareUserIds.has(m.user_id)}
                      onChange={(e) => {
                        setSelectedShareUserIds((prev) => {
                          const next = new Set(prev);
                          if (e.target.checked) {
                            next.add(m.user_id);
                          } else {
                            next.delete(m.user_id);
                          }
                          return next;
                        });
                      }}
                    />
                    <span className="truncate">{m.email}</span>
                  </label>
                ))
              )}
            </div>
          ) : null}
          <label className="mt-2 block text-[11px] font-medium text-slate-700 dark:text-neutral-200">
            Expires in (days)
          </label>
          <input
            type="number"
            min={1}
            max={90}
            value={shareExpiresDays}
            onChange={(e) => setShareExpiresDays(Math.max(1, Math.min(90, Number(e.target.value) || 7)))}
            className="mt-1 w-full rounded-lg border border-slate-200 bg-white px-2 py-1 text-xs dark:border-neutral-600 dark:bg-neutral-800 dark:text-neutral-100"
          />
          <button
            type="button"
            className="ap-btn mt-2 w-full text-xs"
            disabled={shareBusy}
            onClick={() => void createDbShare()}
          >
            {shareBusy ? "Creating…" : "Create share link"}
          </button>
          {shareMessage ? <p className="mt-2 text-[11px] text-slate-600 dark:text-neutral-400">{shareMessage}</p> : null}
          {lastCreatedShareUrl ? (
            <div className="mt-2">
              <p className="text-[10px] font-semibold uppercase text-slate-500 dark:text-neutral-400">Copy URL</p>
              <code className="mt-1 block max-h-24 overflow-auto rounded-lg bg-slate-50 px-2 py-1.5 text-[11px] text-slate-700 dark:bg-neutral-950 dark:text-neutral-200">
                {typeof window !== "undefined" ? new URL(lastCreatedShareUrl, window.location.origin).href : lastCreatedShareUrl}
              </code>
              <button
                type="button"
                className="mt-1 text-xs font-medium text-sky-700 hover:underline dark:text-sky-300"
                onClick={async () => {
                  const full =
                    typeof window !== "undefined"
                      ? new URL(lastCreatedShareUrl!, window.location.origin).href
                      : lastCreatedShareUrl!;
                  try {
                    await navigator.clipboard.writeText(full);
                  } catch {
                    window.prompt("Copy URL:", full);
                  }
                }}
              >
                Copy to clipboard
              </button>
            </div>
          ) : null}
        </div>

        <div className="rounded-xl border border-slate-200/90 bg-white p-3 shadow-sm dark:border-neutral-700 dark:bg-neutral-900">
          <div className="flex items-center justify-between gap-2">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-600 dark:text-neutral-300">
              Published shares
            </p>
            <button
              type="button"
              className="text-[11px] font-medium text-sky-700 hover:underline dark:text-sky-300"
              onClick={() => void loadPublishedShares()}
            >
              Refresh
            </button>
          </div>
          <p className="mt-1 text-[10px] leading-relaxed text-slate-500 dark:text-neutral-500">
            Secret tokens are only shown once when you create a link. This list is metadata for your project.
          </p>
          {publishedSharesLoad === "loading" ? (
            <p className="mt-2 text-[11px] text-slate-500">Loading…</p>
          ) : publishedSharesLoad === "error" ? (
            <p className="mt-2 text-[11px] text-rose-600 dark:text-rose-400">Could not load shares.</p>
          ) : publishedShares.length === 0 ? (
            <p className="mt-2 text-[11px] text-slate-500">No published shares yet.</p>
          ) : (
            <ul className="mt-2 max-h-48 space-y-2 overflow-y-auto text-[11px] text-slate-700 dark:text-neutral-200">
              {publishedShares.map((row) => {
                const exp = Date.parse(row.expires_at);
                const now = Date.now();
                const expired = Number.isFinite(exp) && exp <= now;
                const revoked = Boolean(row.revoked_at);
                const state = revoked ? "Revoked" : expired ? "Expired" : "Active";
                return (
                  <li
                    key={row.id}
                    className="rounded-lg border border-slate-100 px-2 py-1.5 dark:border-neutral-800"
                  >
                    <div className="flex flex-wrap items-center justify-between gap-1">
                      <span className="font-mono text-[10px] text-slate-500 dark:text-neutral-400">{row.id.slice(0, 8)}…</span>
                      <span
                        className={
                          state === "Active"
                            ? "text-emerald-700 dark:text-emerald-400"
                            : "text-slate-500 dark:text-neutral-500"
                        }
                      >
                        {state}
                      </span>
                    </div>
                    <div className="mt-0.5 text-slate-600 dark:text-neutral-400">
                      {row.access_mode}
                      {row.access_mode === "restricted" && row.allowed_user_ids?.length
                        ? ` · ${row.allowed_user_ids.length} user(s)`
                        : ""}
                    </div>
                    <div className="mt-0.5 text-slate-500 dark:text-neutral-500">
                      Expires {Number.isFinite(exp) ? new Date(exp).toLocaleString() : row.expires_at}
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      </aside>
    </div>
  );
}
