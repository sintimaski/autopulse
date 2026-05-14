"use client";

import { useSearchParams } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";

import { CardSpinner } from "../../ui/CardSpinner";
import { buildDashboardNetworkError } from "../../../utils/dashboardFetchErrors";
import { buildQueryExplorerExecutePayload } from "../../../utils/queryExplorerExecute";
import { parseQueryExplorerResponse } from "../../../utils/dashboardResponseGuards";
import { copyTextToClipboard } from "../clipboard";
import { useDashboardData } from "../DashboardDataContext";
import { dashboardSessionJsonPost } from "../dashboardSessionFetch";
import type { QueryExplorerResponse } from "../dashboardTypes";
import {
  isJobTypedQuery,
  JOB_FAILURES_STARTER_SQL,
  QUERY_EXPLORER_JOB_FAILURES_PRESET,
  QUERY_EXPLORER_TEMPLATES,
} from "../queryExplorerPresets";
import { ChartColumn, Copy, Layers, Play, Terminal } from "lucide-react";
import { Banner, Chip, ConsoleButton, Kbd, Panel, Toggle } from "../../ui/console";

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
  const [lastRunQuery, setLastRunQuery] = useState<string | null>(null);
  const [copyStatus, setCopyStatus] = useState<string | null>(null);
  const [templateId, setTemplateId] = useState("");
  const jobFailuresPresetAppliedRef = useRef(false);
  const gutterRef = useRef<HTMLPreElement>(null);
  const activeTemplate = useMemo(
    () => QUERY_EXPLORER_TEMPLATES.find((item) => item.id === templateId),
    [templateId],
  );
  const lineCount = useMemo(() => query.split("\n").length, [query]);
  const showJobTypeHint = useMemo(
    () => Boolean(data) && data?.rows.length === 0 && lastRunQuery !== null && isJobTypedQuery(lastRunQuery),
    [data, lastRunQuery],
  );

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

  const execute = async () => {
    setLoading(true);
    setError(null);
    setCopyStatus(null);
    const submittedQuery = query;
    try {
      const body = buildQueryExplorerExecutePayload({
        query,
        rowLimit,
        applyTimeWindow,
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
      });
      const response = await dashboardSessionJsonPost("/dashboard/query-explorer/execute", body);
      const raw: unknown = await response.json();
      if (!response.ok) {
        const detail =
          typeof raw === "object" && raw !== null && "detail" in raw && typeof (raw as { detail: unknown }).detail === "string"
            ? (raw as { detail: string }).detail
            : `Query failed (${response.status})`;
        setError(detail);
        setData(null);
        setLastRunQuery(null);
        return;
      }
      const parsed = parseQueryExplorerResponse(raw);
      if (!parsed) {
        setError("Dashboard returned an unexpected query result shape.");
        setData(null);
        setLastRunQuery(null);
        return;
      }
      setData(parsed);
      setLastRunQuery(submittedQuery);
    } catch (err) {
      setError(buildDashboardNetworkError(err));
      setData(null);
      setLastRunQuery(null);
    } finally {
      setLoading(false);
    }
  };

  const applyTemplate = (id: string) => {
    setTemplateId(id);
    const picked = QUERY_EXPLORER_TEMPLATES.find((item) => item.id === id);
    if (picked) {
      setQuery(picked.sql);
    }
  };

  const copyResults = async (format: "json" | "csv") => {
    if (!data) {
      return;
    }
    let payload: string;
    if (format === "json") {
      const objects = data.rows.map((row) =>
        Object.fromEntries(data.columns.map((column, index) => [column, row[index] ?? null])),
      );
      payload = JSON.stringify(objects, null, 2);
    } else {
      const escapeCsv = (value: unknown): string => {
        const text = value === null || value === undefined ? "" : String(value);
        return /[",\n\r]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
      };
      const lines = [
        data.columns.map(escapeCsv).join(","),
        ...data.rows.map((row) => row.map(escapeCsv).join(",")),
      ];
      payload = lines.join("\n");
    }
    const ok = await copyTextToClipboard(payload);
    setCopyStatus(
      ok ? `Copied ${data.rows.length} row${data.rows.length === 1 ? "" : "s"} as ${format.toUpperCase()}` : "Copy failed",
    );
  };

  return (
    <div className="flex flex-col gap-4">
      <Banner tone="warning" icon={Terminal} title="Power-user surface">
        Read-only DuckDB <span className="font-mono">SELECT</span> / CTE over{" "}
        <span className="font-mono">scoped_events</span> — the same view every panel uses. Use the header
        time-scope panel for the rolling or custom window; add other filters in SQL. If routine work brings
        you here, the scope bar can probably express it.
      </Banner>

      <div className="grid items-start gap-4 lg:grid-cols-[15rem_minmax(0,1fr)]">
        {/* Templates */}
        <Panel icon={Layers} title="Templates" subtitle="Curated read-only queries">
          <ul className="divide-y divide-slate-100 dark:divide-neutral-800">
            <li>
              <button
                type="button"
                onClick={() => setTemplateId("")}
                className={`flex w-full flex-col gap-0.5 px-3 py-2 text-left transition-colors ${
                  templateId === ""
                    ? "bg-orange-50 dark:bg-orange-950/30"
                    : "hover:bg-slate-50/70 dark:hover:bg-neutral-800/40"
                }`}
              >
                <span className="text-[12px] font-medium text-slate-700 dark:text-neutral-200">
                  Custom SQL
                </span>
                <span className="text-[11px] text-slate-400 dark:text-neutral-500">
                  Start from the current editor
                </span>
              </button>
            </li>
            {QUERY_EXPLORER_TEMPLATES.map((item) => {
              const active = templateId === item.id;
              return (
                <li key={item.id}>
                  <button
                    type="button"
                    onClick={() => applyTemplate(item.id)}
                    className={`flex w-full flex-col gap-0.5 px-3 py-2 text-left transition-colors ${
                      active
                        ? "bg-orange-50 dark:bg-orange-950/30"
                        : "hover:bg-slate-50/70 dark:hover:bg-neutral-800/40"
                    }`}
                  >
                    <span className="text-[12px] font-medium text-slate-700 dark:text-neutral-200">
                      {item.title}
                    </span>
                    <span className="truncate font-mono text-[11px] text-slate-400 dark:text-neutral-500">
                      {item.sql.split("\n")[0]}
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
        </Panel>

        <div className="flex min-w-0 flex-col gap-4">
          {/* SQL editor */}
          <Panel
            icon={Terminal}
            title="SQL editor"
            subtitle={activeTemplate ? activeTemplate.description : "scoped_events"}
            actions={
              <>
                <Toggle
                  checked={applyTimeWindow}
                  onChange={setApplyTimeWindow}
                  label="Apply time window"
                />
                <label className="flex items-center gap-1.5 text-[12px] text-slate-500 dark:text-neutral-400">
                  Limit
                  <input
                    type="number"
                    min={1}
                    max={500}
                    value={rowLimit}
                    onChange={(event) =>
                      setRowLimit(Math.max(1, Math.min(500, Number(event.target.value) || 1)))
                    }
                    className="ap-input w-20 px-2 py-1 text-[12px]"
                  />
                </label>
                <ConsoleButton
                  variant="primary"
                  size="sm"
                  icon={Play}
                  disabled={loading}
                  onClick={() => void execute()}
                >
                  {loading ? "Running…" : "Run"}
                </ConsoleButton>
              </>
            }
            footer={
              <>
                <span>
                  Row limit {rowLimit} · {applyTimeWindow ? "header time window applied" : "full project scan"}
                </span>
                <span className="flex items-center gap-1">
                  <Kbd>⌘</Kbd>
                  <Kbd>⏎</Kbd>
                  to run
                </span>
              </>
            }
          >
            <div className="relative overflow-hidden font-mono text-[13px] leading-[1.7]">
              <pre
                ref={gutterRef}
                aria-hidden
                className="pointer-events-none absolute left-0 top-0 h-full select-none overflow-hidden border-r border-slate-200/80 bg-slate-50/70 py-3 text-right text-slate-400 dark:border-neutral-800 dark:bg-neutral-950/60 dark:text-neutral-600"
                style={{ width: "3rem" }}
              >
                {Array.from({ length: lineCount }, (_, index) => (
                  <div key={index} className="px-2">
                    {index + 1}
                  </div>
                ))}
              </pre>
              <textarea
                id="query-explorer-sql"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                onScroll={(event) => {
                  if (gutterRef.current) {
                    gutterRef.current.scrollTop = event.currentTarget.scrollTop;
                  }
                }}
                onKeyDown={(event) => {
                  if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
                    event.preventDefault();
                    void execute();
                  }
                }}
                aria-label="SQL query for Query Explorer"
                spellCheck={false}
                className="relative block min-h-[13rem] w-full resize-y bg-transparent py-3 pl-14 pr-3 text-slate-900 outline-none dark:text-neutral-100"
              />
            </div>
          </Panel>

          {error ? (
            <Banner tone="danger" icon={Terminal} title="Query failed">
              {error}
            </Banner>
          ) : null}

          {/* Results */}
          <Panel
            icon={ChartColumn}
            title="Results"
            subtitle={
              loading
                ? "Querying…"
                : data
                  ? `${data.rows.length} row${data.rows.length === 1 ? "" : "s"}${data.truncated ? " (truncated)" : ""}`
                  : "Run a query to see results"
            }
            actions={
              <>
                {data && data.truncated ? <Chip tone="accent">truncated</Chip> : null}
                {data && data.rows.length > 0 ? (
                  <>
                    <ConsoleButton
                      variant="secondary"
                      size="xs"
                      icon={Copy}
                      onClick={() => void copyResults("json")}
                    >
                      Copy JSON
                    </ConsoleButton>
                    <ConsoleButton
                      variant="secondary"
                      size="xs"
                      icon={Copy}
                      onClick={() => void copyResults("csv")}
                    >
                      Copy CSV
                    </ConsoleButton>
                  </>
                ) : null}
              </>
            }
          >
            <div aria-live="polite" className="sr-only">
              {loading
                ? "Running query."
                : copyStatus
                  ? copyStatus
                  : data
                    ? `Query returned ${data.rows.length} row${data.rows.length === 1 ? "" : "s"}${data.truncated ? ", truncated" : ""}.`
                    : ""}
            </div>
            {loading ? (
              <CardSpinner className="m-3.5" label="Running query…" description="Waiting for DuckDB results." />
            ) : data && data.rows.length > 0 ? (
              <>
                {copyStatus ? (
                  <p className="border-b border-slate-200/80 px-3 py-1.5 text-[11px] text-slate-500 dark:border-neutral-800 dark:text-neutral-400">
                    {copyStatus}
                  </p>
                ) : null}
                <div className="overflow-x-auto">
                  <table className="min-w-full text-left text-[12px]">
                    <caption className="sr-only">
                      Query results — {data.rows.length} row{data.rows.length === 1 ? "" : "s"}
                      {data.truncated ? " (truncated)" : ""}, {data.columns.length} column
                      {data.columns.length === 1 ? "" : "s"}.
                    </caption>
                    <thead className="border-b border-slate-200/80 bg-slate-50/70 text-[10px] uppercase tracking-wide text-slate-400 dark:border-neutral-800 dark:bg-neutral-950/40 dark:text-neutral-500">
                      <tr>
                        {data.columns.map((column) => (
                          <th key={column} scope="col" className="px-3 py-1.5 font-semibold">
                            {column}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 dark:divide-neutral-800">
                      {data.rows.map((row, rowIdx) => (
                        <tr key={`${rowIdx}-${row.length}`} className="hover:bg-slate-50/70 dark:hover:bg-neutral-800/40">
                          {row.map((cell, cellIdx) => (
                            <td
                              key={`${rowIdx}-${cellIdx}`}
                              className="px-3 py-1.5 font-mono text-slate-600 dark:text-neutral-300"
                            >
                              {cell === null ? (
                                <span className="text-slate-300 dark:text-neutral-600">null</span>
                              ) : (
                                String(cell)
                              )}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            ) : data ? (
              <div className="flex flex-col items-center justify-center gap-2 py-12 text-center">
                <span className="flex size-11 items-center justify-center rounded-full bg-slate-100 text-slate-400 dark:bg-neutral-800 dark:text-neutral-500">
                  <ChartColumn className="size-5" aria-hidden />
                </span>
                <p className="text-[13px] font-medium text-slate-700 dark:text-neutral-200">No rows returned</p>
                {showJobTypeHint ? (
                  <p className="max-w-sm text-[12px] text-slate-400 dark:text-neutral-500">
                    This query filters on <span className="font-mono">type = &apos;job&apos;</span> rows, which
                    only exist when your app uses background-job instrumentation. A request-only project will
                    return zero rows here — wire up job tracking in the SDK to populate it.
                  </p>
                ) : (
                  <p className="max-w-xs text-[12px] text-slate-400 dark:text-neutral-500">
                    The query ran successfully but matched no rows in the scoped window.
                  </p>
                )}
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center gap-2 py-12 text-center">
                <span className="flex size-11 items-center justify-center rounded-full bg-slate-100 text-slate-400 dark:bg-neutral-800 dark:text-neutral-500">
                  <ChartColumn className="size-5" aria-hidden />
                </span>
                <p className="text-[13px] font-medium text-slate-700 dark:text-neutral-200">No results yet</p>
                <p className="max-w-xs text-[12px] text-slate-400 dark:text-neutral-500">
                  Pick a template or write SQL above, then run the query.
                </p>
              </div>
            )}
          </Panel>
        </div>
      </div>
    </div>
  );
}
