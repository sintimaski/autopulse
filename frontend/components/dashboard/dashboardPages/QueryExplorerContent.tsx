"use client";

import { useSearchParams } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";

import { CardSpinner } from "../../ui/CardSpinner";
import { buildDashboardNetworkError } from "../../../utils/dashboardFetchErrors";
import { parseQueryExplorerResponse } from "../../../utils/dashboardResponseGuards";
import { useDashboardData } from "../DashboardDataContext";
import { dashboardSessionJsonPost } from "../dashboardSessionFetch";
import type { QueryExplorerResponse } from "../dashboardTypes";
import {
  JOB_FAILURES_STARTER_SQL,
  QUERY_EXPLORER_JOB_FAILURES_PRESET,
} from "../queryExplorerPresets";

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

export function QueryExplorerContent() {
  const d = useDashboardData();
  const searchParams = useSearchParams();
  const [query, setQuery] = useState(DEFAULT_QUERY);
  const [rowLimit, setRowLimit] = useState(200);
  const [applyTimeWindow, setApplyTimeWindow] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<QueryExplorerResponse | null>(null);
  const jobFailuresPresetAppliedRef = useRef(false);

  useEffect(() => {
    const preset = (searchParams.get("preset") ?? "").trim().toLowerCase();
    if (preset !== QUERY_EXPLORER_JOB_FAILURES_PRESET) {
      jobFailuresPresetAppliedRef.current = false;
      return;
    }
    if (jobFailuresPresetAppliedRef.current) {
      return;
    }
    setQuery(JOB_FAILURES_STARTER_SQL);
    jobFailuresPresetAppliedRef.current = true;
  }, [searchParams]);

  const payloadWindow = useMemo(
    () => ({
      window_minutes: d.windowMinutes,
      from_timestamp: d.isAbsoluteWindow ? d.windowFromTimestamp : undefined,
      to_timestamp: d.isAbsoluteWindow ? d.windowToTimestamp : undefined,
    }),
    [d.isAbsoluteWindow, d.windowFromTimestamp, d.windowToTimestamp, d.windowMinutes],
  );

  const execute = async () => {
    setLoading(true);
    setError(null);
    try {
      const scoped = applyTimeWindow;
      const body = scoped
        ? {
            query,
            row_limit: rowLimit,
            scope_mode: "time_window" as const,
            ...payloadWindow,
          }
        : {
            query,
            row_limit: rowLimit,
            scope_mode: "project_wide" as const,
          };
      const response = await dashboardSessionJsonPost("/dashboard/query-explorer/execute", body);
      const raw: unknown = await response.json();
      if (!response.ok) {
        const detail =
          typeof raw === "object" && raw !== null && "detail" in raw && typeof (raw as { detail: unknown }).detail === "string"
            ? (raw as { detail: string }).detail
            : `Query failed (${response.status})`;
        setError(detail);
        setData(null);
        return;
      }
      const parsed = parseQueryExplorerResponse(raw);
      if (!parsed) {
        setError("Dashboard returned an unexpected query result shape.");
        setData(null);
        return;
      }
      setData(parsed);
    } catch (err) {
      setError(buildDashboardNetworkError(err));
      setData(null);
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="rounded-2xl bg-white/95 p-6 shadow-sm ring-1 ring-slate-900/[0.06] dark:bg-neutral-900 dark:ring-white/[0.08]">
      <h2 className="text-base font-semibold text-slate-900 dark:text-neutral-100">Query Explorer</h2>
      <p className="mt-1 text-sm text-slate-500 dark:text-neutral-400">
        Read-only DuckDB <code className="rounded bg-slate-100 px-1 py-0.5 dark:bg-neutral-800">SELECT</code> / CTE
        against <code className="rounded bg-slate-100 px-1 py-0.5 dark:bg-neutral-800">scoped_events</code>. Use the
        header <span className="text-slate-600 dark:text-neutral-300">Time scope</span> panel for the rolling or custom
        window only. Add any other filters in your SQL. Turn off the time limit to scan the full live project table
        (same as <code className="rounded bg-slate-100 px-1 py-0.5 dark:bg-neutral-800">project_wide</code> on the
        server).
      </p>
      <div className="mt-4 grid gap-3">
        <textarea
          id="query-explorer-sql"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          aria-label="SQL query for Query Explorer"
          className="min-h-[220px] w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 font-mono text-xs text-slate-900 dark:border-neutral-700 dark:bg-neutral-950 dark:text-neutral-100"
          spellCheck={false}
        />
        <div className="flex flex-wrap items-center gap-3">
          <label className="flex cursor-pointer items-center gap-2 text-sm text-slate-700 dark:text-neutral-200">
            <input
              type="checkbox"
              className="size-4 rounded border-slate-300 text-sky-600 focus:ring-sky-500 dark:border-neutral-600 dark:bg-neutral-900"
              checked={applyTimeWindow}
              onChange={(event) => setApplyTimeWindow(event.target.checked)}
            />
            Limit to header time window
          </label>
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
          <button type="button" onClick={() => void execute()} disabled={loading} className="ap-btn">
            {loading ? "Running…" : "Run query"}
          </button>
        </div>
      </div>
      {error ? (
        <p className="mt-4 rounded-lg border border-rose-300 bg-rose-50 px-3 py-2 text-sm text-rose-700 dark:border-rose-900/50 dark:bg-rose-950/30 dark:text-rose-200">
          {error}
        </p>
      ) : null}
      {loading ? (
        <CardSpinner className="mt-5" label="Running query…" description="Waiting for DuckDB results." />
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
