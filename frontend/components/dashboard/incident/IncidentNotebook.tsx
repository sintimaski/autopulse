"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { CardSpinner } from "../../ui/CardSpinner";
import { buildDashboardNetworkError } from "../../../utils/dashboardFetchErrors";
import {
  defaultIncidentNotebook,
  moveCell,
  newDividerCell,
  newMarkdownCell,
  newSqlCell,
  newTextCell,
  parseIncidentNotebookJson,
  removeCellAt,
  serializeIncidentNotebook,
  type IncidentNotebookCell,
  type IncidentNotebookDocument,
} from "../../../utils/incidentNotebookModel";
import {
  buildQueryExplorerExecutePayload,
  type QueryExplorerExecuteInput,
} from "../../../utils/queryExplorerExecute";
import { parseQueryExplorerResponse } from "../../../utils/dashboardResponseGuards";
import { ChevronDown, ChevronUp, Plus, Trash2 } from "../../../lib/icons";
import { useDashboardData } from "../DashboardDataContext";
import { dashboardSessionJsonPost } from "../dashboardSessionFetch";
import type { QueryExplorerResponse } from "../dashboardTypes";

function escapeHtml(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

type SqlOutput = { loading: boolean; error: string | null; data: QueryExplorerResponse | null };

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

export function IncidentNotebook({
  storageKey,
  legacyPlaintextStorageKey,
}: {
  storageKey: string;
  /** Previous single-block notes key — migrated into a `text` cell once. */
  legacyPlaintextStorageKey?: string;
}) {
  const d = useDashboardData();
  const [doc, setDoc] = useState<IncidentNotebookDocument>(() => defaultIncidentNotebook());
  const [hydrated, setHydrated] = useState(false);
  const [sqlOutputs, setSqlOutputs] = useState<Record<string, SqlOutput>>({});

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
    setHydrated(true);
  }, [storageKey, legacyPlaintextStorageKey]);

  useEffect(() => {
    if (!hydrated) {
      return;
    }
    const handle = window.setTimeout(() => {
      try {
        window.localStorage.setItem(storageKey, serializeIncidentNotebook(doc));
      } catch {
        /* ignore */
      }
    }, 400);
    return () => window.clearTimeout(handle);
  }, [doc, hydrated, storageKey]);

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
        const raw: unknown = await response.json();
        if (!response.ok) {
          const detail =
            typeof raw === "object" && raw !== null && "detail" in raw && typeof (raw as { detail: unknown }).detail === "string"
              ? (raw as { detail: string }).detail
              : `Query failed (${response.status})`;
          setSqlOutputs((o) => ({ ...o, [cell.id]: { loading: false, error: detail, data: null } }));
          return;
        }
        const parsed = parseQueryExplorerResponse(raw);
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

  const cellShell =
    "rounded-xl border border-slate-200/90 bg-white shadow-sm dark:border-neutral-700 dark:bg-neutral-900";

  if (!hydrated) {
    return <CardSpinner size="compact" label="Loading notebook…" />;
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs font-medium uppercase tracking-wide text-slate-500 dark:text-neutral-400">
          Cells
        </span>
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
          className="ml-auto text-xs text-rose-600 hover:underline dark:text-rose-400"
          onClick={() => {
            if (window.confirm("Reset the entire notebook to the default template?")) {
              setDoc(defaultIncidentNotebook());
              setSqlOutputs({});
            }
          }}
        >
          Reset notebook
        </button>
      </div>

      <div className="space-y-3">
        {doc.cells.map((cell, index) => {
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

          return (
            <div key={cell.id} className={cellShell}>
              <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 px-3 py-2 dark:border-neutral-800">
                <span className="text-[10px] font-bold uppercase tracking-wide text-slate-500 dark:text-neutral-400">
                  {isMd ? "Markdown" : isText ? "Note" : "SQL"}
                </span>
                <div className="flex items-center gap-0.5">
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

              <div className="p-3">
                {(isMd || isText) && (
                  <textarea
                    value={cell.source}
                    onChange={(e) =>
                      updateCell(index, { ...cell, source: e.target.value } as IncidentNotebookCell)
                    }
                    rows={isMd ? 8 : 5}
                    spellCheck={isText}
                    className="w-full rounded-lg border border-slate-200 bg-slate-50/80 px-3 py-2 font-mono text-xs text-slate-900 dark:border-neutral-600 dark:bg-neutral-950 dark:text-neutral-100"
                    aria-label={isMd ? "Markdown cell" : "Note cell"}
                  />
                )}
                {isMd ? (
                  <details className="mt-2">
                    <summary className="cursor-pointer text-xs font-medium text-sky-700 dark:text-sky-300">
                      Preview (escaped)
                    </summary>
                    <div
                      className="mt-2 rounded-lg border border-slate-100 bg-white px-3 py-2 text-sm leading-relaxed text-slate-800 dark:border-neutral-800 dark:bg-neutral-950 dark:text-neutral-200"
                      dangerouslySetInnerHTML={{
                        __html: escapeHtml(cell.source).replace(/\n/g, "<br/>"),
                      }}
                    />
                  </details>
                ) : null}

                {isSql && (
                  <>
                    <textarea
                      value={cell.source}
                      onChange={(e) =>
                        updateCell(index, { ...cell, source: e.target.value } as IncidentNotebookCell)
                      }
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
                            } as IncidentNotebookCell)
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
                            } as IncidentNotebookCell)
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
                        {sqlOutputs[cell.id]?.loading ? "Running…" : "Run"}
                      </button>
                    </div>
                    {sqlOutputs[cell.id]?.error ? (
                      <p className="mt-2 rounded-lg border border-rose-300 bg-rose-50 px-2 py-1.5 text-xs text-rose-800 dark:border-rose-900/50 dark:bg-rose-950/30 dark:text-rose-200">
                        {sqlOutputs[cell.id]?.error}
                      </p>
                    ) : null}
                    {sqlOutputs[cell.id]?.loading ? (
                      <CardSpinner className="mt-3" size="compact" label="Executing SQL…" />
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
            </div>
          );
        })}
      </div>

      <p className="text-[11px] leading-relaxed text-slate-500 dark:text-neutral-500">
        Notebook JSON is saved to <code className="rounded bg-slate-100 px-1 dark:bg-neutral-800">localStorage</code>{" "}
        under this incident scope. SQL uses the same{" "}
        <code className="rounded bg-slate-100 px-1 dark:bg-neutral-800">scoped_events</code> rules as Query Explorer
        (read-only <code className="rounded bg-slate-100 px-1 dark:bg-neutral-800">SELECT</code> / CTE). Header
        filters (method, path, SQL fragment, etc.) are applied to each run.
      </p>
    </div>
  );
}
