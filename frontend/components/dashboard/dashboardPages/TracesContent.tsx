"use client";

import { useCallback, useEffect, useState } from "react";

import { CardSpinner } from "../../ui/CardSpinner";
import { buildDashboardNetworkError } from "../../../utils/dashboardFetchErrors";
import { parseTraceDetailResponse, parseTraceSearchResponse } from "../../../utils/dashboardResponseGuards";
import { useDashboardData } from "../DashboardDataContext";
import { dashboardSessionFetch } from "../dashboardSessionFetch";
import { METHOD_OPTIONS, formatTimestamp, type TraceDetailResponse, type TraceSearchResponse } from "../dashboardTypes";
import { ChevronLeft, ChevronRight, Crosshair, Globe, Network, Search, Server } from "lucide-react";
import {
  Banner,
  Chip,
  ConsoleButton,
  Panel,
  SeverityDot,
  StatusCode,
  Toggle,
} from "../../ui/console";

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
  const [searchLoading, setSearchLoading] = useState(false);
  const [detailLoading, setDetailLoading] = useState(false);
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
      setSearchLoading(true);
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
        const response = await dashboardSessionFetch(`/dashboard/traces/search?${params.toString()}`);
        const raw: unknown = await response.json();
        if (!response.ok) {
          const detail =
            typeof raw === "object" && raw !== null && "detail" in raw && typeof (raw as { detail: unknown }).detail === "string"
              ? (raw as { detail: string }).detail
              : `Trace search failed (${response.status})`;
          setError(detail);
          setSearchData(null);
          return;
        }
        const parsedSearch = parseTraceSearchResponse(raw);
        if (!parsedSearch) {
          setError("Dashboard returned an unexpected trace search shape.");
          setSearchData(null);
          return;
        }
        setSearchData(parsedSearch);
        if (timeOverride?.kind === "absolute") {
          setAbsoluteFrom(timeOverride.from);
          setAbsoluteTo(timeOverride.to);
        } else if (timeOverride?.kind === "rolling") {
          setAbsoluteFrom(null);
          setAbsoluteTo(null);
          setWindowMinutes(timeOverride.windowMinutes);
        }
      } catch (err) {
        setError(buildDashboardNetworkError(err));
        setSearchData(null);
      } finally {
        setSearchLoading(false);
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
    setDetailData(null);
    setDetailLoading(true);
    setError(null);
    const scope = resolveTimeScope();
    const timeParams = buildDetailTimeParams(scope);
    const qs = timeParams.toString();
    try {
      const response = await dashboardSessionFetch(
        `/dashboard/traces/${encodeURIComponent(traceId)}${qs ? `?${qs}` : ""}`,
      );
      const raw: unknown = await response.json();
      if (!response.ok) {
        const detail =
          typeof raw === "object" && raw !== null && "detail" in raw && typeof (raw as { detail: unknown }).detail === "string"
            ? (raw as { detail: string }).detail
            : `Trace load failed (${response.status})`;
        setError(detail);
        setDetailData(null);
        return;
      }
      const parsedDetail = parseTraceDetailResponse(raw);
      if (!parsedDetail) {
        setError("Dashboard returned an unexpected trace detail shape.");
        setDetailData(null);
        return;
      }
      setDetailData(parsedDetail);
    } catch (err) {
      setError(buildDashboardNetworkError(err));
      setDetailData(null);
    } finally {
      setDetailLoading(false);
    }
  };

  const timeModeLabel =
    absoluteFrom && absoluteTo ? "Custom time range (UTC)" : `Rolling window (${windowMinutes} min)`;
  const detailMaxLatency = detailData
    ? Math.max(1, ...detailData.items.map((item) => item.latency_ms))
    : 1;

  return (
    <div className="flex flex-col gap-4">
      <Banner tone="info" icon={Network}>
        Full tracing searches correlated OTLP spans by span <span className="font-mono">timestamp</span> or
        ingest <span className="font-mono">received_at</span> within the window. OTLP has no built-in
        &quot;session&quot; — pick a preset or shift the window to browse history.
      </Banner>

      {error ? (
        <Banner tone="danger" icon={Crosshair} title="Trace request failed">
          {error}
        </Banner>
      ) : null}

      <div className="grid items-start gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(0,1.3fr)]">
        {/* Trace search */}
        <Panel
          icon={Search}
          title="Trace search"
          subtitle={timeModeLabel}
          bodyClassName="flex flex-col"
        >
          <div className="flex flex-col gap-3 border-b border-slate-200/80 p-3.5 dark:border-neutral-800">
            <div>
              <p className="mb-1.5 text-[11px] font-medium uppercase tracking-wide text-slate-400 dark:text-neutral-500">
                Time range
              </p>
              <div className="flex flex-wrap gap-1.5">
                {TRACE_WINDOW_PRESETS.map((preset) => {
                  const active = !absoluteFrom && !absoluteTo && windowMinutes === preset.minutes;
                  return (
                    <ConsoleButton
                      key={preset.minutes}
                      size="xs"
                      variant={active ? "primary" : "secondary"}
                      disabled={searchLoading}
                      onClick={() => applyPreset(preset.minutes)}
                    >
                      {preset.label}
                    </ConsoleButton>
                  );
                })}
              </div>
              <div className="mt-2 flex flex-wrap items-center gap-1.5">
                <ConsoleButton
                  size="xs"
                  icon={ChevronLeft}
                  disabled={searchLoading || !searchData}
                  onClick={shiftWindowEarlier}
                >
                  Older
                </ConsoleButton>
                <ConsoleButton
                  size="xs"
                  iconRight={ChevronRight}
                  disabled={searchLoading || !searchData}
                  onClick={shiftWindowLater}
                >
                  Newer
                </ConsoleButton>
              </div>
            </div>
            <div className="grid gap-2 sm:grid-cols-2">
              <label className="flex flex-col gap-1 text-[11px] font-medium uppercase tracking-wide text-slate-400 dark:text-neutral-500">
                Services
                <input
                  value={servicesFilter}
                  onChange={(event) => setServicesFilter(event.target.value)}
                  placeholder="api, worker"
                  className="ap-input px-2 py-1 text-[13px] font-normal normal-case tracking-normal text-slate-700 dark:text-neutral-200"
                />
              </label>
              <label className="flex flex-col gap-1 text-[11px] font-medium uppercase tracking-wide text-slate-400 dark:text-neutral-500">
                Environments
                <input
                  value={environmentsFilter}
                  onChange={(event) => setEnvironmentsFilter(event.target.value)}
                  placeholder="prod, staging"
                  className="ap-input px-2 py-1 text-[13px] font-normal normal-case tracking-normal text-slate-700 dark:text-neutral-200"
                />
              </label>
              <label className="flex flex-col gap-1 text-[11px] font-medium uppercase tracking-wide text-slate-400 dark:text-neutral-500">
                Path contains
                <input
                  value={pathContains}
                  onChange={(event) => setPathContains(event.target.value)}
                  placeholder="/checkout"
                  className="ap-input px-2 py-1 text-[13px] font-normal normal-case tracking-normal text-slate-700 dark:text-neutral-200"
                />
              </label>
              <label className="flex flex-col gap-1 text-[11px] font-medium uppercase tracking-wide text-slate-400 dark:text-neutral-500">
                HTTP method
                <select
                  value={methodFilter || "ALL"}
                  onChange={(event) => setMethodFilter(event.target.value === "ALL" ? "" : event.target.value)}
                  className="ap-select px-2 py-1 text-[13px] font-normal normal-case tracking-normal text-slate-700 dark:text-neutral-200"
                >
                  {METHOD_OPTIONS.map((method) => (
                    <option key={method} value={method}>
                      {method}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <div className="flex flex-wrap items-center justify-between gap-2">
              <Toggle
                checked={errorsOnly}
                onChange={setErrorsOnly}
                label="5xx spans only"
              />
            </div>
            <div className="flex items-center gap-2">
              <input
                type="search"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Search trace id, service, path, span…"
                aria-label="Search traces by id, service, path, or span name"
                className="ap-input min-w-0 flex-1 px-2.5 py-1.5 text-[13px]"
              />
              <ConsoleButton
                variant="primary"
                icon={Search}
                disabled={searchLoading}
                onClick={() => void searchTraces()}
              >
                {searchLoading ? "Searching…" : "Search"}
              </ConsoleButton>
            </div>
          </div>

          {searchLoading && !searchData ? (
            <CardSpinner className="m-3.5" label="Searching traces…" description="Applying filters and time window." />
          ) : null}
          {searchData ? (
            <div className="flex flex-col">
              {searchLoading ? (
                <div className="border-b border-slate-200/80 px-3.5 py-1.5 dark:border-neutral-800">
                  <CardSpinner size="compact" label="Refreshing trace list…" />
                </div>
              ) : null}
              {searchData.items.length === 0 ? (
                <div className="p-3.5 text-[12px] text-slate-600 dark:text-neutral-300">
                  <p className="font-medium text-slate-900 dark:text-neutral-100">No traces in this window.</p>
                  <p className="mt-1 text-slate-500 dark:text-neutral-400">
                    Window (UTC): {formatTimestamp(searchData.from_timestamp)} → {formatTimestamp(searchData.to_timestamp)}
                  </p>
                  {searchData.project_id ? (
                    <p className="mt-1 text-slate-500 dark:text-neutral-400">
                      Scoped to project{" "}
                      <code className="rounded bg-slate-100 px-1 font-mono dark:bg-neutral-800">
                        {searchData.project_id}
                      </code>
                      {sessionProjectId && sessionProjectId !== searchData.project_id ? (
                        <span className="mt-1 block text-amber-700 dark:text-amber-300">
                          Session active project ({sessionProjectId}) differs from API — reload or switch project
                          in Settings.
                        </span>
                      ) : null}
                    </p>
                  ) : null}
                  <ul className="mt-2 list-disc space-y-1 pl-4 text-[11px] text-slate-500 dark:text-neutral-400">
                    <li>Try a longer preset or the Older button to move back in time.</li>
                    <li>
                      The OTLP ingest key must belong to <strong>this same project</strong> and hit the same backend
                      / event store.
                    </li>
                    <li>
                      Tracing needs <code className="font-mono">LUMONOX_EVENT_STORE=duckdb</code>.
                    </li>
                  </ul>
                </div>
              ) : (
                <ul className="divide-y divide-slate-100 dark:divide-neutral-800">
                  {searchData.items.map((item) => {
                    const selected = selectedTraceId === item.trace_id;
                    return (
                      <li key={item.trace_id}>
                        <button
                          type="button"
                          onClick={() => void openTrace(item.trace_id)}
                          className={`flex w-full items-center gap-3 px-3.5 py-2 text-left transition-colors ${
                            selected
                              ? "bg-orange-50 dark:bg-orange-950/30"
                              : "hover:bg-slate-50/70 dark:hover:bg-neutral-800/40"
                          }`}
                        >
                          <SeverityDot tone={item.error_count > 0 ? "danger" : "healthy"} />
                          <div className="min-w-0 flex-1">
                            <p className="truncate font-mono text-[12px] text-slate-700 dark:text-neutral-200">
                              {item.trace_id}
                            </p>
                            <p className="truncate text-[11px] text-slate-400 dark:text-neutral-500">
                              {item.span_count} spans · {item.error_count} errors ·{" "}
                              {item.services.join(", ") || "—"}
                            </p>
                          </div>
                          <ChevronRight className="size-3.5 shrink-0 text-slate-300 dark:text-neutral-600" aria-hidden />
                        </button>
                      </li>
                    );
                  })}
                </ul>
              )}
            </div>
          ) : null}
        </Panel>

        {/* Trace detail */}
        <Panel
          icon={Network}
          title={selectedTraceId ? `Trace · ${selectedTraceId}` : "Trace detail"}
          subtitle={
            detailData
              ? `${detailData.items.length} spans`
              : "Select a trace to inspect its span waterfall"
          }
          bodyClassName="p-3.5"
        >
          {detailLoading ? (
            <CardSpinner
              label="Loading span details…"
              description={selectedTraceId ? `Trace ${selectedTraceId}` : undefined}
            />
          ) : detailData && detailData.items.length > 0 ? (
            <div className="flex flex-col gap-1">
              <div className="grid grid-cols-[minmax(0,1fr)_minmax(0,1.4fr)_4.5rem] gap-2 px-1 pb-1 text-[10px] uppercase tracking-wide text-slate-400 dark:text-neutral-500">
                <span>Span</span>
                <span>Duration</span>
                <span className="text-right">Latency</span>
              </div>
              {detailData.items.map((item) => {
                const widthPct = Math.max(1.5, (item.latency_ms / detailMaxLatency) * 100);
                const isError = item.status_code >= 500;
                return (
                  <div
                    key={`${item.trace_id}-${item.span_id ?? item.timestamp}`}
                    className="grid grid-cols-[minmax(0,1fr)_minmax(0,1.4fr)_4.5rem] items-center gap-2 rounded-md px-1 py-1 hover:bg-slate-50/70 dark:hover:bg-neutral-800/40"
                  >
                    <div className="min-w-0">
                      <p className="flex items-center gap-1.5 truncate font-mono text-[12px] text-slate-700 dark:text-neutral-200">
                        {isError ? <SeverityDot tone="danger" size={6} /> : null}
                        {item.span_name}
                      </p>
                      <p className="truncate text-[10px] text-slate-400 dark:text-neutral-500">
                        {item.service_name} · {item.path}
                      </p>
                    </div>
                    <div className="h-4 rounded bg-slate-100 dark:bg-neutral-800">
                      <div
                        className={`h-full rounded ${
                          isError
                            ? "bg-rose-500"
                            : item.status_code >= 400
                              ? "bg-amber-500"
                              : "bg-orange-400"
                        }`}
                        style={{ width: `${widthPct}%` }}
                      />
                    </div>
                    <div className="flex items-center justify-end gap-1.5">
                      <StatusCode code={item.status_code} />
                      <span className="font-mono text-[11px] tabular-nums text-slate-500 dark:text-neutral-400">
                        {item.latency_ms.toFixed(0)}
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center gap-2 py-12 text-center">
              <span className="flex size-11 items-center justify-center rounded-full bg-slate-100 text-slate-400 dark:bg-neutral-800 dark:text-neutral-500">
                <Network className="size-5" aria-hidden />
              </span>
              <p className="text-[13px] font-medium text-slate-700 dark:text-neutral-200">
                {selectedTraceId ? "No spans for this trace" : "No trace selected"}
              </p>
              <p className="max-w-xs text-[12px] text-slate-400 dark:text-neutral-500">
                Pick a trace from the search results to see its span-by-span latency waterfall.
              </p>
            </div>
          )}
        </Panel>
      </div>

      {searchData ? (
        <div className="flex flex-wrap items-center gap-2 text-[11px] text-slate-400 dark:text-neutral-500">
          <Chip tone="muted" icon={Server}>
            Window {formatTimestamp(searchData.from_timestamp)} → {formatTimestamp(searchData.to_timestamp)}
          </Chip>
          {searchData.project_id ? (
            <Chip tone="muted" icon={Globe}>
              {searchData.project_id}
            </Chip>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
