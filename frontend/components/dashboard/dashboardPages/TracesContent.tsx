"use client";

import { useCallback, useEffect, useState } from "react";

import { useDashboardData } from "../DashboardDataContext";
import { METHOD_OPTIONS, buildApiUrl, formatTimestamp, type TraceDetailResponse, type TraceSearchResponse } from "../dashboardTypes";

const TRACE_WINDOW_PRESETS: { label: string; minutes: number }[] = [
  { label: "Last 1 hour", minutes: 60 },
  { label: "Last 6 hours", minutes: 360 },
  { label: "Last 24 hours", minutes: 1440 },
  { label: "Last 7 days", minutes: 10_080 },
];

type TraceTimeScope =
  | { kind: "rolling"; windowMinutes: number }
  | { kind: "absolute"; from: string; to: string };

export function TracesContent() {
  const { sessionProjectId } = useDashboardData();
  const [query, setQuery] = useState("");
  const [windowMinutes, setWindowMinutes] = useState(1440);
  const [absoluteFrom, setAbsoluteFrom] = useState<string | null>(null);
  const [absoluteTo, setAbsoluteTo] = useState<string | null>(null);
  const [servicesFilter, setServicesFilter] = useState("");
  const [environmentsFilter, setEnvironmentsFilter] = useState("");
  const [pathContains, setPathContains] = useState("");
  const [methodFilter, setMethodFilter] = useState("");
  const [errorsOnly, setErrorsOnly] = useState(false);
  const [selectedTraceId, setSelectedTraceId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searchData, setSearchData] = useState<TraceSearchResponse | null>(null);
  const [detailData, setDetailData] = useState<TraceDetailResponse | null>(null);

  const resolveTimeScope = useCallback(
    (override?: TraceTimeScope): TraceTimeScope => {
      if (override) {
        return override;
      }
      if (absoluteFrom && absoluteTo) {
        return { kind: "absolute", from: absoluteFrom, to: absoluteTo };
      }
      return { kind: "rolling", windowMinutes };
    },
    [absoluteFrom, absoluteTo, windowMinutes],
  );

  const appendFilterParams = useCallback((params: URLSearchParams) => {
    if (servicesFilter.trim()) {
      params.set("services", servicesFilter.trim());
    }
    if (environmentsFilter.trim()) {
      params.set("environments", environmentsFilter.trim());
    }
    if (pathContains.trim()) {
      params.set("path_contains", pathContains.trim());
    }
    if (methodFilter.trim() && methodFilter !== "ALL") {
      params.set("method", methodFilter.trim());
    }
    if (errorsOnly) {
      params.set("status_class", "5");
    }
  }, [servicesFilter, environmentsFilter, pathContains, methodFilter, errorsOnly]);

  const buildDetailTimeParams = useCallback(
    (scope: TraceTimeScope) => {
      const params = new URLSearchParams();
      if (scope.kind === "absolute") {
        params.set("from_timestamp", scope.from);
        params.set("to_timestamp", scope.to);
      } else {
        params.set("window_minutes", String(scope.windowMinutes));
      }
      return params;
    },
    [],
  );

  const searchTraces = useCallback(
    async (timeOverride?: TraceTimeScope) => {
      setLoading(true);
      setError(null);
      const scope = resolveTimeScope(timeOverride);
      try {
        const params = new URLSearchParams();
        if (query.trim()) {
          params.set("q", query.trim());
        }
        params.set("limit", "50");
        if (scope.kind === "absolute") {
          params.set("from_timestamp", scope.from);
          params.set("to_timestamp", scope.to);
        } else {
          params.set("window_minutes", String(scope.windowMinutes));
        }
        appendFilterParams(params);
        const response = await fetch(buildApiUrl(`/dashboard/traces/search?${params.toString()}`), {
          credentials: "include",
        });
        const raw = await response.json();
        if (!response.ok) {
          setError(typeof raw?.detail === "string" ? raw.detail : `Trace search failed (${response.status})`);
          setSearchData(null);
          return;
        }
        setSearchData(raw as TraceSearchResponse);
        if (timeOverride?.kind === "absolute") {
          setAbsoluteFrom(timeOverride.from);
          setAbsoluteTo(timeOverride.to);
        } else if (timeOverride?.kind === "rolling") {
          setAbsoluteFrom(null);
          setAbsoluteTo(null);
          setWindowMinutes(timeOverride.windowMinutes);
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "Trace search request failed");
        setSearchData(null);
      } finally {
        setLoading(false);
      }
    },
    [appendFilterParams, query, resolveTimeScope],
  );

  useEffect(() => {
    queueMicrotask(() => {
      void searchTraces({ kind: "rolling", windowMinutes: 1440 });
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps -- initial search only
  }, []);

  const applyPreset = (minutes: number) => {
    setWindowMinutes(minutes);
    setAbsoluteFrom(null);
    setAbsoluteTo(null);
    void searchTraces({ kind: "rolling", windowMinutes: minutes });
  };

  const shiftWindowEarlier = () => {
    if (!searchData) {
      return;
    }
    const spanMs =
      new Date(searchData.to_timestamp).getTime() - new Date(searchData.from_timestamp).getTime();
    if (spanMs <= 0) {
      return;
    }
    const toMs = new Date(searchData.from_timestamp).getTime();
    const fromMs = toMs - spanMs;
    const fromIso = new Date(fromMs).toISOString();
    const toIso = new Date(toMs).toISOString();
    void searchTraces({ kind: "absolute", from: fromIso, to: toIso });
  };

  const shiftWindowLater = () => {
    if (!searchData) {
      return;
    }
    const spanMs =
      new Date(searchData.to_timestamp).getTime() - new Date(searchData.from_timestamp).getTime();
    if (spanMs <= 0) {
      return;
    }
    const fromMs = new Date(searchData.to_timestamp).getTime();
    let toMs = fromMs + spanMs;
    const nowMs = new Date(searchData.server_now).getTime();
    if (toMs > nowMs) {
      toMs = nowMs;
    }
    if (fromMs >= toMs) {
      return;
    }
    const fromIso = new Date(fromMs).toISOString();
    const toIso = new Date(toMs).toISOString();
    void searchTraces({ kind: "absolute", from: fromIso, to: toIso });
  };

  const openTrace = async (traceId: string) => {
    setSelectedTraceId(traceId);
    setLoading(true);
    setError(null);
    const scope = resolveTimeScope();
    const timeParams = buildDetailTimeParams(scope);
    const qs = timeParams.toString();
    try {
      const response = await fetch(
        buildApiUrl(`/dashboard/traces/${encodeURIComponent(traceId)}${qs ? `?${qs}` : ""}`),
        { credentials: "include" },
      );
      const raw = await response.json();
      if (!response.ok) {
        setError(typeof raw?.detail === "string" ? raw.detail : `Trace load failed (${response.status})`);
        setDetailData(null);
        return;
      }
      setDetailData(raw as TraceDetailResponse);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Trace detail request failed");
      setDetailData(null);
    } finally {
      setLoading(false);
    }
  };

  const timeModeLabel =
    absoluteFrom && absoluteTo ? "Custom time range (UTC)" : `Rolling window (${windowMinutes} min)`;

  return (
    <section className="rounded-2xl bg-white/95 p-6 shadow-sm ring-1 ring-slate-900/[0.06] dark:bg-neutral-900 dark:ring-white/[0.08]">
      <h2 className="text-base font-semibold text-slate-900 dark:text-neutral-100">Full tracing (OTLP)</h2>
      <p className="mt-1 text-sm text-slate-500 dark:text-neutral-400">
        Search correlated traces ingested from OTLP spans. The list uses span <span className="font-mono text-[0.7rem]">timestamp</span>{" "}
        or ingest <span className="font-mono text-[0.7rem]">received_at</span> within the window below. Use presets or shift the window to
        browse history (OTLP has no built-in &quot;session&quot; — you choose the time range on each query).
      </p>

      <div className="mt-4 rounded-xl border border-slate-200 bg-slate-50/60 p-4 dark:border-neutral-700 dark:bg-neutral-950/40">
        <p className="text-xs font-medium uppercase tracking-wide text-slate-500 dark:text-neutral-500">Time range</p>
        <div className="mt-2 flex flex-wrap gap-2">
          {TRACE_WINDOW_PRESETS.map((preset) => (
            <button
              key={preset.minutes}
              type="button"
              onClick={() => applyPreset(preset.minutes)}
              disabled={loading}
              className={`rounded-lg border px-3 py-1.5 text-xs font-medium transition-colors ${
                !absoluteFrom && !absoluteTo && windowMinutes === preset.minutes
                  ? "border-sky-500 bg-sky-50 text-sky-900 dark:border-sky-500/60 dark:bg-sky-950/40 dark:text-sky-100"
                  : "border-slate-200 bg-white text-slate-700 hover:bg-slate-100 dark:border-neutral-600 dark:bg-neutral-900 dark:text-neutral-200 dark:hover:bg-neutral-800"
              }`}
            >
              {preset.label}
            </button>
          ))}
        </div>
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <button type="button" onClick={() => shiftWindowEarlier()} disabled={loading || !searchData} className="ap-btn text-xs">
            ← Older window
          </button>
          <button type="button" onClick={() => shiftWindowLater()} disabled={loading || !searchData} className="ap-btn text-xs">
            Newer window →
          </button>
          <span className="text-xs text-slate-500 dark:text-neutral-500">{timeModeLabel}</span>
        </div>
      </div>

      <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <label className="block text-xs text-slate-600 dark:text-neutral-400">
          Service names (comma-separated)
          <input
            value={servicesFilter}
            onChange={(e) => setServicesFilter(e.target.value)}
            placeholder="api, worker"
            className="mt-1 w-full rounded-lg border border-slate-200 bg-white px-2 py-1.5 text-sm dark:border-neutral-700 dark:bg-neutral-950"
          />
        </label>
        <label className="block text-xs text-slate-600 dark:text-neutral-400">
          Environments (comma-separated)
          <input
            value={environmentsFilter}
            onChange={(e) => setEnvironmentsFilter(e.target.value)}
            placeholder="prod, staging"
            className="mt-1 w-full rounded-lg border border-slate-200 bg-white px-2 py-1.5 text-sm dark:border-neutral-700 dark:bg-neutral-950"
          />
        </label>
        <label className="block text-xs text-slate-600 dark:text-neutral-400">
          Path contains
          <input
            value={pathContains}
            onChange={(e) => setPathContains(e.target.value)}
            placeholder="/checkout"
            className="mt-1 w-full rounded-lg border border-slate-200 bg-white px-2 py-1.5 text-sm dark:border-neutral-700 dark:bg-neutral-950"
          />
        </label>
        <label className="block text-xs text-slate-600 dark:text-neutral-400">
          HTTP method
          <select
            value={methodFilter || "ALL"}
            onChange={(e) => setMethodFilter(e.target.value === "ALL" ? "" : e.target.value)}
            className="mt-1 w-full rounded-lg border border-slate-200 bg-white px-2 py-1.5 text-sm dark:border-neutral-700 dark:bg-neutral-950"
          >
            {METHOD_OPTIONS.map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))}
          </select>
        </label>
      </div>
      <label className="mt-3 flex cursor-pointer items-center gap-2 text-sm text-slate-700 dark:text-neutral-300">
        <input
          type="checkbox"
          checked={errorsOnly}
          onChange={(e) => setErrorsOnly(e.target.checked)}
          className="rounded border-slate-300 dark:border-neutral-600"
        />
        5xx spans only (status class 5xx)
      </label>

      <div className="mt-4 flex flex-wrap items-center gap-3">
        <input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Search by trace id, service, path, span name..."
          className="min-w-[280px] flex-1 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm dark:border-neutral-700 dark:bg-neutral-950"
        />
        <button type="button" onClick={() => void searchTraces()} disabled={loading} className="ap-btn">
          {loading ? "Loading..." : "Search traces"}
        </button>
      </div>
      {error ? (
        <p className="mt-4 rounded-lg border border-rose-300 bg-rose-50 px-3 py-2 text-sm text-rose-700 dark:border-rose-900/50 dark:bg-rose-950/30 dark:text-rose-200">
          {error}
        </p>
      ) : null}
      {searchData ? (
        <div className="mt-5 grid gap-3">
          <p className="text-xs text-slate-500 dark:text-neutral-500">
            Window (UTC): {formatTimestamp(searchData.from_timestamp)} {"->"} {formatTimestamp(searchData.to_timestamp)}
          </p>
          {searchData.items.map((item) => (
            <button
              type="button"
              key={item.trace_id}
              onClick={() => void openTrace(item.trace_id)}
              className={`rounded-xl border px-4 py-3 text-left transition-colors ${
                selectedTraceId === item.trace_id
                  ? "border-sky-400 bg-sky-50 dark:border-sky-500/70 dark:bg-sky-950/30"
                  : "border-slate-200 bg-slate-50/70 hover:bg-slate-100 dark:border-neutral-700 dark:bg-neutral-800/60 dark:hover:bg-neutral-800"
              }`}
            >
              <p className="font-mono text-xs text-slate-700 dark:text-neutral-200">{item.trace_id}</p>
              <p className="mt-1 text-sm text-slate-700 dark:text-neutral-300">
                spans: {item.span_count} · errors: {item.error_count} · services: {item.services.join(", ") || "—"}
              </p>
              <p className="mt-1 text-xs text-slate-500 dark:text-neutral-400">
                {formatTimestamp(item.first_seen)} {"->"} {formatTimestamp(item.last_seen)}
              </p>
            </button>
          ))}
          {searchData.items.length === 0 ? (
            <div className="rounded-xl border border-slate-200 bg-slate-50/80 px-4 py-3 text-sm text-slate-700 dark:border-neutral-700 dark:bg-neutral-900/50 dark:text-neutral-200">
              <p className="font-medium text-slate-900 dark:text-neutral-100">No traces found in this window.</p>
              <p className="mt-2 text-xs text-slate-600 dark:text-neutral-400">
                Server window (UTC): {formatTimestamp(searchData.from_timestamp)} {"->"} {formatTimestamp(searchData.to_timestamp)}
              </p>
              {searchData.project_id ? (
                <p className="mt-1 text-xs text-slate-600 dark:text-neutral-400">
                  This search is scoped to project{" "}
                  <code className="rounded bg-white px-1 py-0.5 font-mono text-[0.7rem] dark:bg-neutral-950">
                    {searchData.project_id}
                  </code>
                  {sessionProjectId && sessionProjectId !== searchData.project_id ? (
                    <span className="block pt-1 text-amber-800 dark:text-amber-200">
                      Session active project ({sessionProjectId}) differs from API — reload or switch project in Settings.
                    </span>
                  ) : null}
                </p>
              ) : null}
              <ul className="mt-3 list-disc space-y-1 pl-5 text-xs text-slate-600 dark:text-neutral-400">
                <li>
                  Try a longer preset (e.g. Last 7 days) or <strong>Older window</strong> to move back in time.
                </li>
                <li>
                  The <code className="font-mono text-[0.7rem]">Authorization: Bearer</code> key on{" "}
                  <code className="font-mono text-[0.7rem]">POST /otlp/v1/traces</code> must belong to{" "}
                  <strong>this same project</strong> (Settings → Active project / API keys).
                </li>
                <li>
                  <code className="font-mono text-[0.7rem]">curl</code> and this dashboard must hit the{" "}
                  <strong>same backend</strong> and DuckDB file (same <code className="font-mono text-[0.7rem]">LUMONOX_DATA_DIR</code>{" "}
                  / event store path).
                </li>
                <li>
                  Tracing explorer needs <code className="font-mono text-[0.7rem]">LUMONOX_EVENT_STORE=duckdb</code>
                  . If search returns 400 mentioning DuckDB, the store is off.
                </li>
              </ul>
            </div>
          ) : null}
        </div>
      ) : null}
      {detailData ? (
        <div className="mt-6 overflow-x-auto rounded-xl border border-slate-200 dark:border-neutral-700">
          <table className="min-w-full text-left text-xs">
            <thead className="bg-slate-50 dark:bg-neutral-800">
              <tr>
                <th className="px-3 py-2">Time</th>
                <th className="px-3 py-2">Span</th>
                <th className="px-3 py-2">Service</th>
                <th className="px-3 py-2">Path</th>
                <th className="px-3 py-2">Status</th>
                <th className="px-3 py-2">Latency</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-neutral-800">
              {detailData.items.map((item) => (
                <tr key={`${item.trace_id}-${item.span_id ?? item.timestamp}`}>
                  <td className="px-3 py-2 text-slate-700 dark:text-neutral-300">{formatTimestamp(item.timestamp)}</td>
                  <td className="px-3 py-2 font-mono text-slate-700 dark:text-neutral-300">{item.span_name}</td>
                  <td className="px-3 py-2 text-slate-700 dark:text-neutral-300">{item.service_name}</td>
                  <td className="px-3 py-2 font-mono text-slate-700 dark:text-neutral-300">{item.path}</td>
                  <td className="px-3 py-2 text-slate-700 dark:text-neutral-300">{item.status_code}</td>
                  <td className="px-3 py-2 text-slate-700 dark:text-neutral-300">{item.latency_ms.toFixed(1)} ms</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </section>
  );
}
