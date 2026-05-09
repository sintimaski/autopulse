"use client";

import { useMemo, useState } from "react";

import { useDashboardData } from "../DashboardDataContext";
import { normalizeCommaSeparated } from "../dashboardQueryState";
import { buildApiUrl, type QueryExplorerResponse } from "../dashboardTypes";

const DEFAULT_QUERY = [
  "SELECT",
  "  service_name,",
  "  environment,",
  "  COUNT(*) AS requests,",
  "  AVG(latency_ms) AS avg_latency_ms,",
  "  SUM(CASE WHEN status_code >= 500 THEN 1 ELSE 0 END) AS error_count",
  "FROM scoped_events",
  "GROUP BY service_name, environment",
  "ORDER BY requests DESC",
].join("\n");

function buildHeaderScopePayload(d: ReturnType<typeof useDashboardData>) {
  const min = Number(d.minLatencyMs);
  const max = Number(d.maxLatencyMs);
  const envCsv = normalizeCommaSeparated(d.serverEnvironmentQuery);
  const svcCsv = normalizeCommaSeparated(d.serverServiceQuery);
  return {
    method: d.method !== "ALL" ? d.method : undefined,
    status_class: d.statusClass !== "ALL" ? Number(d.statusClass) : undefined,
    path_contains: d.pathQuery.trim() || undefined,
    environments: envCsv || undefined,
    services: svcCsv || undefined,
    min_latency_ms:
      d.minLatencyMs.trim() !== "" && Number.isFinite(min) && min >= 0 ? min : undefined,
    max_latency_ms:
      d.maxLatencyMs.trim() !== "" && Number.isFinite(max) && max >= 0 ? max : undefined,
    event_sql_filter:
      d.sqlFilterEnabled && d.sqlFilterApplied.trim() ? d.sqlFilterApplied.trim() : undefined,
  };
}

export function QueryExplorerContent() {
  const d = useDashboardData();
  const [query, setQuery] = useState(DEFAULT_QUERY);
  const [rowLimit, setRowLimit] = useState(200);
  const [loading, setLoading] = useState(false);
  const [loadingKind, setLoadingKind] = useState<"time_window" | "project_wide" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<QueryExplorerResponse | null>(null);

  const payloadWindow = useMemo(
    () => ({
      window_minutes: d.windowMinutes,
      from_timestamp: d.isAbsoluteWindow ? d.windowFromTimestamp : undefined,
      to_timestamp: d.isAbsoluteWindow ? d.windowToTimestamp : undefined,
    }),
    [d.isAbsoluteWindow, d.windowFromTimestamp, d.windowToTimestamp, d.windowMinutes],
  );

  const execute = async (scopeMode: "time_window" | "project_wide") => {
    setLoading(true);
    setLoadingKind(scopeMode);
    setError(null);
    try {
      const body =
        scopeMode === "time_window"
          ? {
              query,
              row_limit: rowLimit,
              scope_mode: "time_window" as const,
              ...payloadWindow,
              ...buildHeaderScopePayload(d),
            }
          : {
              query,
              row_limit: rowLimit,
              scope_mode: "project_wide" as const,
            };
      const response = await fetch(buildApiUrl("/dashboard/query-explorer/execute"), {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const raw = await response.json();
      if (!response.ok) {
        setError(typeof raw?.detail === "string" ? raw.detail : `Query failed (${response.status})`);
        setData(null);
        return;
      }
      setData(raw as QueryExplorerResponse);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Query request failed");
      setData(null);
    } finally {
      setLoading(false);
      setLoadingKind(null);
    }
  };

  return (
    <section className="rounded-2xl bg-white/95 p-6 shadow-sm ring-1 ring-slate-900/[0.06] dark:bg-neutral-900 dark:ring-white/[0.08]">
      <h2 className="text-base font-semibold text-slate-900 dark:text-neutral-100">Query Explorer</h2>
      <p className="mt-1 text-sm text-slate-500 dark:text-neutral-400">
        Read-only DuckDB <code className="rounded bg-slate-100 px-1 py-0.5 dark:bg-neutral-800">SELECT</code> / CTE
        against <code className="rounded bg-slate-100 px-1 py-0.5 dark:bg-neutral-800">scoped_events</code> on the
        server. Use the header <span className="text-slate-600 dark:text-neutral-300">Requests scope</span> panel for
        window, method, path, env, service, latency, and SQL filter; the first run button applies that scope. The
        second button ignores scope and scans the full live <code className="rounded bg-slate-100 px-1 py-0.5 dark:bg-neutral-800">events</code> table for this project (no time slice, no Parquet union).
      </p>
      <div className="mt-4 grid gap-3">
        <textarea
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          className="min-h-[220px] w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 font-mono text-xs text-slate-900 dark:border-neutral-700 dark:bg-neutral-950 dark:text-neutral-100"
          spellCheck={false}
        />
        <div className="flex flex-wrap items-center gap-3">
          <label className="text-sm text-slate-600 dark:text-neutral-300">
            Row limit{" "}
            <input
              type="number"
              min={1}
              max={500}
              value={rowLimit}
              onChange={(event) => setRowLimit(Math.max(1, Math.min(500, Number(event.target.value) || 1)))}
              className="ml-2 w-24 rounded-md border border-slate-200 bg-white px-2 py-1 text-sm dark:border-neutral-700 dark:bg-neutral-900"
            />
          </label>
          <button type="button" onClick={() => void execute("time_window")} disabled={loading} className="ap-btn">
            {loading && loadingKind === "time_window" ? "Running…" : "Run query (with header scope)"}
          </button>
          <button
            type="button"
            onClick={() => void execute("project_wide")}
            disabled={loading}
            className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-800 shadow-sm hover:bg-slate-50 disabled:opacity-60 dark:border-neutral-600 dark:bg-neutral-900 dark:text-neutral-100 dark:hover:bg-neutral-800"
          >
            {loading && loadingKind === "project_wide" ? "Running…" : "Run on full DuckDB (ignore scope)"}
          </button>
        </div>
      </div>
      {error ? (
        <p className="mt-4 rounded-lg border border-rose-300 bg-rose-50 px-3 py-2 text-sm text-rose-700 dark:border-rose-900/50 dark:bg-rose-950/30 dark:text-rose-200">
          {error}
        </p>
      ) : null}
      {data ? (
        <div className="mt-5">
          <p className="mb-2 text-xs text-slate-500 dark:text-neutral-400">
            Returned {data.rows.length} row(s){data.truncated ? " (truncated)." : "."}
          </p>
          <div className="overflow-x-auto rounded-xl border border-slate-200 dark:border-neutral-700">
            <table className="min-w-full text-left text-xs">
              <thead className="bg-slate-50 dark:bg-neutral-800">
                <tr>
                  {data.columns.map((column) => (
                    <th key={column} className="px-3 py-2 font-semibold text-slate-700 dark:text-neutral-200">
                      {column}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-neutral-800">
                {data.rows.map((row, idx) => (
                  <tr key={`${idx}-${row.length}`}>
                    {row.map((cell, cellIdx) => (
                      <td key={`${idx}-${cellIdx}`} className="px-3 py-2 text-slate-700 dark:text-neutral-300">
                        {cell === null ? "null" : String(cell)}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}
    </section>
  );
}
