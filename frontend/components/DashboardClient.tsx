"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import {
  computeOperationalSignals,
  M5_ALERT_DEFAULTS,
  resolveSparklineSeries,
} from "../utils/dashboardData";

type OverviewBucket = {
  minute: string;
  request_count: number;
  error_count: number;
  avg_latency_ms: number;
};

type OverviewResponse = {
  from_timestamp: string;
  to_timestamp: string;
  request_count: number;
  error_count: number;
  error_rate: number;
  avg_latency_ms: number;
  requests_per_minute: number;
  series: OverviewBucket[];
};

type RequestItem = {
  timestamp: string;
  method: string;
  path: string;
  status_code: number;
  latency_ms: number;
  service_name: string;
  environment: string;
  request_id: string | null;
};

type RequestsResponse = {
  from_timestamp: string;
  to_timestamp: string;
  total: number;
  limit: number;
  offset: number;
  items: RequestItem[];
};

type ErrorGroupItem = {
  group_key: string;
  exception_type: string | null;
  message: string | null;
  path: string;
  count: number;
  first_seen: string;
  last_seen: string;
  sample_stack_trace: string | null;
};

type ErrorGroupsResponse = {
  from_timestamp: string;
  to_timestamp: string;
  total: number;
  limit: number;
  offset: number;
  items: ErrorGroupItem[];
};

const apiBaseUrl = process.env.NEXT_PUBLIC_AUTOPULSE_API_BASE_URL ?? "http://localhost:8000";
const apiKey = process.env.NEXT_PUBLIC_AUTOPULSE_API_KEY;

const WINDOW_OPTIONS = [15, 60, 240, 1440];
const METHOD_OPTIONS = ["ALL", "GET", "POST", "PUT", "PATCH", "DELETE"];
const STATUS_CLASS_OPTIONS = ["ALL", "2", "4", "5"];
const REQUEST_LIMIT_OPTIONS = [50, 100, 200];
const ERROR_GROUP_LIMIT_OPTIONS = [10, 25, 50];
const GROUP_OPTIONS = [
  { value: "none", label: "No grouping" },
  { value: "path", label: "Path" },
  { value: "service_name", label: "Service" },
  { value: "environment", label: "Environment" },
] as const;

type GroupBy = (typeof GROUP_OPTIONS)[number]["value"];
type SortKey = keyof Pick<
  RequestItem,
  "timestamp" | "method" | "path" | "status_code" | "latency_ms" | "service_name" | "environment"
>;
type SortDir = "asc" | "desc";

function formatTimestamp(value: string): string {
  return new Date(value).toLocaleString();
}

function statusTone(code: number): string {
  if (code >= 500) {
    return "bg-rose-500/15 text-rose-800 ring-rose-500/25";
  }
  if (code >= 400) {
    return "bg-amber-500/15 text-amber-900 ring-amber-500/25";
  }
  return "bg-emerald-500/15 text-emerald-900 ring-emerald-500/25";
}

function Sparkline({ series }: { series: OverviewBucket[] }) {
  if (!series.length) {
    return (
      <div className="flex h-14 items-center rounded-xl border border-slate-200/80 bg-white/60 px-3 text-sm text-slate-500">
        No series data in this window.
      </div>
    );
  }
  const max = Math.max(...series.map((b) => Number(b.request_count || 0)), 0);
  if (max <= 0) {
    return (
      <div className="flex h-14 items-center rounded-xl border border-slate-200/80 bg-white/60 px-3 text-sm text-slate-500">
        No request volume buckets in this window.
      </div>
    );
  }
  const barWidth = 6;
  const barGap = 2;
  const chartHeight = 44;
  const plotWidth = Math.max(series.length * (barWidth + barGap), 120);

  return (
    <div
      className="overflow-x-auto rounded-xl border border-slate-200/80 bg-gradient-to-b from-white to-slate-50 px-2 py-2"
      role="img"
      aria-label="Requests per minute buckets"
    >
      <svg width={plotWidth} height={chartHeight} className="block">
        {series.map((bucket, index) => {
          const requestCount = Number(bucket.request_count || 0);
          const errorCount = Number(bucket.error_count || 0);
          const errRatio = requestCount ? errorCount / requestCount : 0;
          const barColor = errRatio > 0.25 ? "#e11d48" : errRatio > 0 ? "#f59e0b" : "#0284c7";
          const barHeight = Math.max(Math.round((requestCount / max) * chartHeight), 2);
          const x = index * (barWidth + barGap);
          const y = chartHeight - barHeight;
          return (
            <rect
              key={bucket.minute}
              x={x}
              y={y}
              width={barWidth}
              height={barHeight}
              rx={1}
              fill={barColor}
            >
              <title>{`${requestCount} req, ${errorCount} err`}</title>
            </rect>
          );
        })}
      </svg>
    </div>
  );
}

function compareValues(a: string | number, b: string | number, dir: SortDir): number {
  const mul = dir === "asc" ? 1 : -1;
  if (typeof a === "number" && typeof b === "number") {
    return (a - b) * mul;
  }
  return String(a).localeCompare(String(b), undefined, { sensitivity: "base" }) * mul;
}

export default function DashboardClient() {
  const [windowMinutes, setWindowMinutes] = useState(60);
  const [method, setMethod] = useState("ALL");
  const [statusClass, setStatusClass] = useState("ALL");
  const [requestLimit, setRequestLimit] = useState(100);
  const [requestPage, setRequestPage] = useState(0);
  const [errorGroupLimit, setErrorGroupLimit] = useState(25);
  const [errorGroupPage, setErrorGroupPage] = useState(0);
  const [pathQuery, setPathQuery] = useState("");
  const [groupBy, setGroupBy] = useState<GroupBy>("none");
  const [sortKey, setSortKey] = useState<SortKey>("timestamp");
  const [sortDir, setSortDir] = useState<SortDir>("desc");
  const [envTags, setEnvTags] = useState<Set<string>>(new Set());
  const [serviceTags, setServiceTags] = useState<Set<string>>(new Set());
  const [overview, setOverview] = useState<OverviewResponse | null>(null);
  const [requests, setRequests] = useState<RequestsResponse | null>(null);
  const [errorGroups, setErrorGroups] = useState<ErrorGroupsResponse | null>(null);
  const [errorGroupSort, setErrorGroupSort] = useState<"last_seen" | "count">("last_seen");
  const [loading, setLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [refreshToken, setRefreshToken] = useState(0);

  const toIsoWindow = useMemo(() => {
    const to = new Date();
    const from = new Date(to.getTime() - windowMinutes * 60 * 1000);
    return { from: from.toISOString(), to: to.toISOString() };
  }, [windowMinutes]);

  useEffect(() => {
    if (!apiKey) {
      return;
    }

    const run = async () => {
      setLoading(true);
      setErrorMessage(null);
      try {
        const headers = { Authorization: `Bearer ${apiKey}` };
        const overviewParams = new URLSearchParams({
          from_timestamp: toIsoWindow.from,
          to_timestamp: toIsoWindow.to,
        });

        const requestsParams = new URLSearchParams({
          from_timestamp: toIsoWindow.from,
          to_timestamp: toIsoWindow.to,
          limit: String(requestLimit),
          offset: String(requestPage * requestLimit),
        });
        if (method !== "ALL") {
          requestsParams.set("method", method);
        }
        if (statusClass !== "ALL") {
          requestsParams.set("status_class", statusClass);
        }

        const errorGroupsParams = new URLSearchParams({
          from_timestamp: toIsoWindow.from,
          to_timestamp: toIsoWindow.to,
          limit: String(errorGroupLimit),
          offset: String(errorGroupPage * errorGroupLimit),
        });

        const [overviewResponse, requestsResponse, errorGroupsResponse] = await Promise.all([
          fetch(`${apiBaseUrl}/dashboard/overview?${overviewParams.toString()}`, { headers }),
          fetch(`${apiBaseUrl}/dashboard/requests?${requestsParams.toString()}`, { headers }),
          fetch(`${apiBaseUrl}/dashboard/error-groups?${errorGroupsParams.toString()}`, {
            headers,
          }),
        ]);
        if (!overviewResponse.ok || !requestsResponse.ok || !errorGroupsResponse.ok) {
          throw new Error("Dashboard API request failed. Check API URL/key and backend status.");
        }
        const overviewData = (await overviewResponse.json()) as OverviewResponse;
        const requestsData = (await requestsResponse.json()) as RequestsResponse;
        const errorGroupsData = (await errorGroupsResponse.json()) as ErrorGroupsResponse;
        setOverview(overviewData);
        setRequests(requestsData);
        setErrorGroups(errorGroupsData);
      } catch (error) {
        const message =
          error instanceof Error ? error.message : "Unexpected dashboard loading failure.";
        setErrorMessage(message);
      } finally {
        setLoading(false);
      }
    };

    void run();
  }, [
    method,
    statusClass,
    toIsoWindow,
    refreshToken,
    requestLimit,
    requestPage,
    errorGroupLimit,
    errorGroupPage,
  ]);

  useEffect(() => {
    setRequestPage(0);
    setErrorGroupPage(0);
  }, [windowMinutes, method, statusClass]);

  const rawItems = requests?.items ?? [];

  const availableEnvironments = useMemo(
    () => [...new Set(rawItems.map((i) => i.environment))].sort(),
    [rawItems],
  );
  const availableServices = useMemo(
    () => [...new Set(rawItems.map((i) => i.service_name))].sort(),
    [rawItems],
  );

  const toggleEnv = useCallback((value: string) => {
    setEnvTags((prev) => {
      const next = new Set(prev);
      if (next.has(value)) {
        next.delete(value);
      } else {
        next.add(value);
      }
      return next;
    });
  }, []);

  const toggleService = useCallback((value: string) => {
    setServiceTags((prev) => {
      const next = new Set(prev);
      if (next.has(value)) {
        next.delete(value);
      } else {
        next.add(value);
      }
      return next;
    });
  }, []);

  const clearClientFilters = useCallback(() => {
    setPathQuery("");
    setEnvTags(new Set());
    setServiceTags(new Set());
    setGroupBy("none");
    setSortKey("timestamp");
    setSortDir("desc");
  }, []);

  const onSortHeader = useCallback(
    (key: SortKey) => {
      if (sortKey === key) {
        setSortDir((d) => (d === "asc" ? "desc" : "asc"));
      } else {
        setSortKey(key);
        setSortDir(key === "timestamp" || key === "status_code" || key === "latency_ms" ? "desc" : "asc");
      }
    },
    [sortKey],
  );

  const filteredSorted = useMemo(() => {
    const q = pathQuery.trim().toLowerCase();
    let rows = rawItems.filter((item) => {
      if (q && !item.path.toLowerCase().includes(q)) {
        return false;
      }
      if (envTags.size > 0 && !envTags.has(item.environment)) {
        return false;
      }
      if (serviceTags.size > 0 && !serviceTags.has(item.service_name)) {
        return false;
      }
      return true;
    });

    rows = [...rows].sort((a, b) => {
      const va = a[sortKey];
      const vb = b[sortKey];
      if (sortKey === "timestamp") {
        const ta = new Date(va as string).getTime();
        const tb = new Date(vb as string).getTime();
        return sortDir === "asc" ? ta - tb : tb - ta;
      }
      return compareValues(va as string | number, vb as string | number, sortDir);
    });

    return rows;
  }, [rawItems, pathQuery, envTags, serviceTags, sortKey, sortDir]);

  const topFailingRoutes = useMemo(() => {
    const counts = new Map<string, number>();
    for (const item of rawItems) {
      if (item.status_code >= 500) {
        counts.set(item.path, (counts.get(item.path) ?? 0) + 1);
      }
    }
    return [...counts.entries()]
      .sort((a, b) => b[1] - a[1])
      .slice(0, 5);
  }, [rawItems]);

  const recentErrorsPreview = useMemo(() => {
    const items = errorGroups?.items;
    if (!items?.length) {
      return [];
    }
    return [...items]
      .sort(
        (a, b) =>
          new Date(b.last_seen).getTime() -
          new Date(a.last_seen).getTime(),
      )
      .slice(0, 5);
  }, [errorGroups]);

  const displayedErrorGroups = useMemo(() => {
    const source = errorGroups?.items;
    if (!source?.length) {
      return [];
    }
    const items = [...source];
    if (errorGroupSort === "count") {
      items.sort((a, b) => {
        if (b.count !== a.count) {
          return b.count - a.count;
        }
        return new Date(b.last_seen).getTime() - new Date(a.last_seen).getTime();
      });
    } else {
      items.sort((a, b) => {
        const t = new Date(b.last_seen).getTime() - new Date(a.last_seen).getTime();
        if (t !== 0) {
          return t;
        }
        return b.count - a.count;
      });
    }
    return items;
  }, [errorGroups, errorGroupSort]);

  const grouped = useMemo(() => {
    if (groupBy === "none") {
      return [{ key: "all", label: "All traffic", items: filteredSorted }];
    }
    const map = new Map<string, RequestItem[]>();
    for (const item of filteredSorted) {
      const k = String(item[groupBy as keyof RequestItem] ?? "");
      if (!map.has(k)) {
        map.set(k, []);
      }
      map.get(k)!.push(item);
    }
    const keys = [...map.keys()].sort((a, b) => a.localeCompare(b));
    return keys.map((key) => ({
      key,
      label: key || "(empty)",
      items: map.get(key)!,
    }));
  }, [filteredSorted, groupBy]);

  const sparklineSeries = useMemo(
    () => resolveSparklineSeries(overview, requests),
    [overview, requests],
  );

  const operationalSignals = useMemo(
    () => computeOperationalSignals(overview, M5_ALERT_DEFAULTS),
    [overview],
  );

  if (!apiKey) {
    return (
      <main className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-800 px-4 py-14 text-slate-100">
        <div className="mx-auto max-w-lg rounded-2xl border border-white/10 bg-white/5 p-8 shadow-2xl shadow-slate-950/50 backdrop-blur">
          <p className="text-sm font-medium uppercase tracking-widest text-sky-300/90">AutoPulse</p>
          <h1 className="mt-2 text-2xl font-semibold tracking-tight">Dashboard</h1>
          <p className="mt-3 text-sm leading-relaxed text-slate-300">
            Set <code className="rounded bg-black/30 px-1.5 py-0.5">NEXT_PUBLIC_AUTOPULSE_API_KEY</code>{" "}
            and{" "}
            <code className="rounded bg-black/30 px-1.5 py-0.5">NEXT_PUBLIC_AUTOPULSE_API_BASE_URL</code>{" "}
            in <code className="rounded bg-black/30 px-1.5 py-0.5">frontend/.env.local</code>, then
            restart <code className="rounded bg-black/30 px-1.5 py-0.5">npm run dev</code>.
          </p>
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-gradient-to-br from-slate-100 via-slate-50 to-sky-50/40 text-slate-900">
      <div className="border-b border-slate-200/80 bg-gradient-to-r from-slate-900 via-slate-800 to-slate-900 text-white shadow-lg">
        <div className="mx-auto flex max-w-6xl flex-col gap-6 px-4 py-10 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-sky-300/90">
              AutoPulse
            </p>
            <h1 className="mt-1 text-3xl font-bold tracking-tight sm:text-4xl">Traffic overview</h1>
            <p className="mt-2 max-w-xl text-sm text-slate-300">
              Scan rate, errors, latency, and grouped failures in seconds. Tune server filters, then
              slice requests client-side by path, service, and environment.
            </p>
            <p className="mt-3 text-xs text-slate-400">
              <a
                href="#grouped-errors"
                className="font-medium text-sky-300 underline-offset-2 hover:text-sky-200 hover:underline"
              >
                Jump to grouped errors
              </a>
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <a
              href="#grouped-errors"
              className="rounded-xl border border-white/20 bg-white/10 px-4 py-2 text-sm font-medium text-white backdrop-blur transition hover:bg-white/20"
            >
              Grouped errors
            </a>
            <button
              type="button"
              onClick={() => setRefreshToken((n) => n + 1)}
              className="rounded-xl border border-white/20 bg-white/10 px-4 py-2 text-sm font-medium text-white backdrop-blur transition hover:bg-white/20"
            >
              Refresh
            </button>
          </div>
        </div>
      </div>

      <div className="mx-auto max-w-6xl space-y-6 px-4 py-8">
        <section className="rounded-2xl border border-slate-200/80 bg-white/90 p-5 shadow-sm shadow-slate-200/50 backdrop-blur">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
            <div>
              <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">
                Server filters
              </h2>
              <p className="mt-1 text-xs text-slate-500">Applied on fetch (backend query).</p>
            </div>
            <div className="flex flex-wrap gap-3">
              <label className="flex flex-col gap-1 text-xs font-medium text-slate-600">
                Time window
                <select
                  value={windowMinutes}
                  onChange={(e) => setWindowMinutes(Number(e.target.value))}
                  className="min-w-[140px] rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm outline-none ring-sky-500/30 focus:ring-2"
                >
                  {WINDOW_OPTIONS.map((minutes) => (
                    <option key={minutes} value={minutes}>
                      Last {minutes}m
                    </option>
                  ))}
                </select>
              </label>
              <label className="flex flex-col gap-1 text-xs font-medium text-slate-600">
                Method
                <select
                  value={method}
                  onChange={(e) => setMethod(e.target.value)}
                  className="min-w-[120px] rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm shadow-sm outline-none ring-sky-500/30 focus:ring-2"
                >
                  {METHOD_OPTIONS.map((value) => (
                    <option key={value} value={value}>
                      {value}
                    </option>
                  ))}
                </select>
              </label>
              <label className="flex flex-col gap-1 text-xs font-medium text-slate-600">
                Status class
                <select
                  value={statusClass}
                  onChange={(e) => setStatusClass(e.target.value)}
                  className="min-w-[120px] rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm shadow-sm outline-none ring-sky-500/30 focus:ring-2"
                >
                  {STATUS_CLASS_OPTIONS.map((value) => (
                    <option key={value} value={value}>
                      {value === "ALL" ? value : `${value}xx`}
                    </option>
                  ))}
                </select>
              </label>
              <label className="flex flex-col gap-1 text-xs font-medium text-slate-600">
                Request limit
                <select
                  value={requestLimit}
                  onChange={(e) => {
                    setRequestLimit(Number(e.target.value));
                    setRequestPage(0);
                  }}
                  className="min-w-[120px] rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm shadow-sm outline-none ring-sky-500/30 focus:ring-2"
                >
                  {REQUEST_LIMIT_OPTIONS.map((value) => (
                    <option key={value} value={value}>
                      {value}
                    </option>
                  ))}
                </select>
              </label>
              <label className="flex flex-col gap-1 text-xs font-medium text-slate-600">
                Error group limit
                <select
                  value={errorGroupLimit}
                  onChange={(e) => {
                    setErrorGroupLimit(Number(e.target.value));
                    setErrorGroupPage(0);
                  }}
                  className="min-w-[140px] rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm shadow-sm outline-none ring-sky-500/30 focus:ring-2"
                >
                  {ERROR_GROUP_LIMIT_OPTIONS.map((value) => (
                    <option key={value} value={value}>
                      {value}
                    </option>
                  ))}
                </select>
              </label>
            </div>
          </div>
        </section>

        {loading && (
          <section className="rounded-2xl border border-slate-200 bg-white p-8 text-center text-slate-600 shadow-sm">
            <p className="animate-pulse text-sm font-medium">Loading dashboard…</p>
          </section>
        )}

        {!loading && errorMessage && (
          <section
            className="rounded-2xl border border-rose-200 bg-rose-50/90 p-6 text-rose-900 shadow-sm"
            role="alert"
          >
            <h2 className="text-lg font-semibold">Unable to load data</h2>
            <p className="mt-2 text-sm">{errorMessage}</p>
          </section>
        )}

        {!loading && !errorMessage && overview && requests && errorGroups && (
          <>
            <section className="grid gap-4 sm:grid-cols-3">
              <article className="rounded-2xl border border-slate-200/80 bg-white p-5 shadow-sm">
                <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Requests / min
                </h3>
                <p className="mt-2 text-3xl font-bold tabular-nums text-slate-900">
                  {overview.requests_per_minute.toFixed(2)}
                </p>
              </article>
              <article className="rounded-2xl border border-slate-200/80 bg-white p-5 shadow-sm">
                <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Error rate
                </h3>
                <p className="mt-2 text-3xl font-bold tabular-nums text-rose-600">
                  {(overview.error_rate * 100).toFixed(1)}%
                </p>
                <p className="mt-1 text-xs text-slate-500">5xx + ingested error events</p>
              </article>
              <article className="rounded-2xl border border-slate-200/80 bg-white p-5 shadow-sm">
                <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Avg latency
                </h3>
                <p className="mt-2 text-3xl font-bold tabular-nums text-slate-900">
                  {overview.avg_latency_ms.toFixed(1)}{" "}
                  <span className="text-lg font-semibold text-slate-500">ms</span>
                </p>
              </article>
            </section>

            <section className="rounded-2xl border border-slate-200/80 bg-white/95 p-5 shadow-sm">
              <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                <h2 className="text-sm font-semibold text-slate-800">Volume (by minute)</h2>
                <p className="text-xs text-slate-500">
                  Window {formatTimestamp(overview.from_timestamp)} →{" "}
                  {formatTimestamp(overview.to_timestamp)}
                </p>
              </div>
              <div className="mt-3">
                <Sparkline series={sparklineSeries} />
              </div>
              {overview.series.length === 0 && sparklineSeries.length > 0 && (
                <p className="mt-2 text-xs text-amber-700">
                  Backend minute series is empty for this range; showing a fallback sparkline from the
                  loaded request page.
                </p>
              )}
            </section>

            <section className="rounded-2xl border border-slate-200/80 bg-white/95 p-5 shadow-sm">
              <h2 className="text-sm font-semibold text-slate-800">Quick diagnosis</h2>
              <p className="mt-1 text-xs text-slate-500">
                Recent errors from grouped API; top routes from 5xx rows in the loaded request
                sample (up to {requests.limit} rows).
              </p>
              <div className="mt-4 grid gap-4 lg:grid-cols-2">
                <div className="rounded-xl border border-slate-200/90 bg-slate-50/50 p-4">
                  <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-600">
                    Recent errors
                  </h3>
                  {recentErrorsPreview.length === 0 ? (
                    <p className="mt-2 text-sm text-slate-600">None in this window.</p>
                  ) : (
                    <ul className="mt-2 space-y-2">
                      {recentErrorsPreview.map((item) => (
                        <li key={item.group_key}>
                          <a
                            href="#grouped-errors"
                            className="block rounded-lg border border-transparent px-1 py-1 text-sm transition hover:border-slate-200 hover:bg-white"
                          >
                            <span className="font-medium text-slate-900">
                              {item.exception_type ?? "Error"}
                            </span>
                            <span className="text-slate-500"> · </span>
                            <span className="font-mono text-xs text-slate-700">{item.path}</span>
                            <span className="mt-0.5 block text-xs text-slate-500">
                              {item.message ? `${item.message.slice(0, 80)}${item.message.length > 80 ? "…" : ""}` : "—"}{" "}
                              <span className="tabular-nums text-rose-700">×{item.count}</span>
                            </span>
                          </a>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
                <div className="rounded-xl border border-slate-200/90 bg-slate-50/50 p-4">
                  <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-600">
                    Top failing routes
                  </h3>
                  {topFailingRoutes.length === 0 ? (
                    <p className="mt-2 text-sm text-slate-600">No 5xx in loaded requests.</p>
                  ) : (
                    <ul className="mt-2 space-y-2">
                      {topFailingRoutes.map(([path, count]) => (
                        <li
                          key={path}
                          className="flex items-start justify-between gap-2 text-sm text-slate-800"
                        >
                          <span className="min-w-0 truncate font-mono text-xs">{path}</span>
                          <span className="shrink-0 tabular-nums font-semibold text-rose-700">
                            {count}
                          </span>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              </div>
            </section>

            <section className="rounded-2xl border border-slate-200/80 bg-white/95 p-5 shadow-sm">
              <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <h2 className="text-sm font-semibold text-slate-800">Operations (M5)</h2>
                  <p className="mt-1 text-xs text-slate-500">
                    Frontend preview of backend alert heuristics and retention defaults.
                  </p>
                </div>
                <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-700">
                  Stub delivery mode
                </span>
              </div>
              <div className="mt-4 grid gap-4 lg:grid-cols-2">
                <div className="rounded-xl border border-slate-200/90 bg-slate-50/50 p-4">
                  <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-600">
                    Alert heuristic preview
                  </h3>
                  <ul className="mt-3 space-y-2 text-sm text-slate-700">
                    <li className="flex items-start justify-between gap-3">
                      <span>Error spike candidate</span>
                      <span
                        className={`rounded-full px-2 py-0.5 text-xs font-semibold ${
                          operationalSignals.errorSpikeCandidate
                            ? "bg-rose-500/15 text-rose-800"
                            : "bg-emerald-500/15 text-emerald-800"
                        }`}
                      >
                        {operationalSignals.errorSpikeCandidate ? "Likely trigger" : "Within threshold"}
                      </span>
                    </li>
                    <li className="flex items-start justify-between gap-3">
                      <span>Possible outage candidate</span>
                      <span
                        className={`rounded-full px-2 py-0.5 text-xs font-semibold ${
                          operationalSignals.outageCandidate
                            ? "bg-rose-500/15 text-rose-800"
                            : "bg-emerald-500/15 text-emerald-800"
                        }`}
                      >
                        {operationalSignals.outageCandidate ? "Likely trigger" : "No outage signal"}
                      </span>
                    </li>
                  </ul>
                  <p className="mt-3 text-xs text-slate-500">
                    Based on current window: {overview.request_count} requests,{" "}
                    {operationalSignals.successfulRequests} successful, {(overview.error_rate * 100).toFixed(1)}%
                    error rate.
                  </p>
                </div>
                <div className="rounded-xl border border-slate-200/90 bg-slate-50/50 p-4">
                  <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-600">
                    Runbook shortcuts
                  </h3>
                  <ul className="mt-3 space-y-2 text-xs text-slate-700">
                    <li>
                      <code className="rounded bg-slate-200/70 px-1.5 py-0.5">
                        uv run python -m autopulse_backend.jobs alerts-once
                      </code>
                    </li>
                    <li>
                      <code className="rounded bg-slate-200/70 px-1.5 py-0.5">
                        uv run python -m autopulse_backend.jobs retention-once
                      </code>
                    </li>
                    <li>
                      Raw events retention target: {M5_ALERT_DEFAULTS.retentionRawDays} days.
                    </li>
                  </ul>
                </div>
              </div>
            </section>

            <section
              id="grouped-errors"
              className="scroll-mt-24 rounded-2xl border border-slate-200/80 bg-white/95 p-5 shadow-sm"
            >
              <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
                <div>
                  <h2 className="text-sm font-semibold text-slate-800">Grouped errors</h2>
                  <p className="mt-1 text-xs text-slate-500">
                    Same time window as overview. Full stack traces may contain sensitive data;
                    scrub at the SDK.
                  </p>
                </div>
                <div className="flex flex-wrap items-center gap-3">
                  <label className="flex flex-col gap-1 text-xs font-medium text-slate-600">
                    Sort by
                    <select
                      value={errorGroupSort}
                      onChange={(e) =>
                        setErrorGroupSort(e.target.value as "last_seen" | "count")
                      }
                      className="min-w-[140px] rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm shadow-sm outline-none ring-sky-500/30 focus:ring-2"
                    >
                      <option value="last_seen">Last seen</option>
                      <option value="count">Count</option>
                    </select>
                  </label>
                  <p className="text-xs text-slate-500 sm:pb-2">
                    Showing {displayedErrorGroups.length} of {errorGroups.total} groups
                  </p>
                </div>
              </div>
              {errorGroups.items.length === 0 ? (
                <p className="mt-4 text-sm text-slate-600">
                  No grouped errors in this time window.
                </p>
              ) : (
                <div className="mt-4 overflow-x-auto rounded-xl border border-slate-200">
                  <table className="min-w-full text-left text-sm">
                    <thead className="bg-slate-50 text-xs font-semibold uppercase tracking-wide text-slate-500">
                      <tr>
                        <th className="px-3 py-2">Exception</th>
                        <th className="px-3 py-2">Message</th>
                        <th className="px-3 py-2">Route</th>
                        <th className="px-3 py-2">Count</th>
                        <th className="px-3 py-2">First seen</th>
                        <th className="px-3 py-2">Last seen</th>
                        <th className="px-3 py-2">Sample stack</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 bg-white">
                      {displayedErrorGroups.map((item) => (
                        <tr key={item.group_key} className="align-top hover:bg-slate-50/80">
                          <td className="px-3 py-2 font-medium text-slate-900">
                            {item.exception_type ?? "(unknown)"}
                          </td>
                          <td className="max-w-[220px] truncate px-3 py-2 text-slate-700 sm:max-w-md">
                            {item.message ?? "(no message)"}
                          </td>
                          <td className="max-w-[220px] truncate px-3 py-2 font-mono text-xs text-slate-800 sm:max-w-md">
                            {item.path}
                          </td>
                          <td className="px-3 py-2 tabular-nums text-slate-700">{item.count}</td>
                          <td className="whitespace-nowrap px-3 py-2 text-slate-600">
                            {formatTimestamp(item.first_seen)}
                          </td>
                          <td className="whitespace-nowrap px-3 py-2 text-slate-600">
                            {formatTimestamp(item.last_seen)}
                          </td>
                          <td className="px-3 py-2">
                            {item.sample_stack_trace ? (
                              <details className="max-w-[420px]">
                                <summary className="cursor-pointer text-xs font-medium text-sky-700">
                                  View stack
                                </summary>
                                <pre className="mt-2 max-h-40 overflow-auto rounded-md bg-slate-950 p-2 text-[11px] leading-5 text-slate-100">
                                  {item.sample_stack_trace}
                                </pre>
                              </details>
                            ) : (
                              <span className="text-xs text-slate-500">
                                No stack trace (event had no exception payload).
                              </span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
              <div className="mt-4 flex items-center justify-between gap-3 border-t border-slate-100 pt-3 text-xs text-slate-600">
                <p>
                  Page {errorGroupPage + 1} · Offset {errorGroupPage * errorGroupLimit}
                </p>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    disabled={errorGroupPage === 0}
                    onClick={() => setErrorGroupPage((p) => Math.max(0, p - 1))}
                    className="rounded-lg border border-slate-200 bg-white px-2.5 py-1 font-medium text-slate-700 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    Prev
                  </button>
                  <button
                    type="button"
                    disabled={(errorGroupPage + 1) * errorGroupLimit >= errorGroups.total}
                    onClick={() => setErrorGroupPage((p) => p + 1)}
                    className="rounded-lg border border-slate-200 bg-white px-2.5 py-1 font-medium text-slate-700 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    Next
                  </button>
                </div>
              </div>
            </section>

            <section className="rounded-2xl border border-slate-200/80 bg-white/95 p-5 shadow-sm">
              <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                <div>
                  <h2 className="text-sm font-semibold text-slate-800">Client filters & grouping</h2>
                  <p className="mt-1 text-xs text-slate-500">
                    Applies to the last {requests.limit} rows returned for this window (server
                    filters above affect what is loaded).
                  </p>
                </div>
                <button
                  type="button"
                  onClick={clearClientFilters}
                  className="self-start rounded-lg border border-slate-200 bg-slate-50 px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-100"
                >
                  Clear client filters
                </button>
              </div>

              <div className="mt-4 grid gap-4 lg:grid-cols-2">
                <label className="flex flex-col gap-1 text-xs font-medium text-slate-600">
                  Path contains
                  <input
                    type="search"
                    value={pathQuery}
                    onChange={(e) => setPathQuery(e.target.value)}
                    placeholder="/users, /health, …"
                    className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm shadow-sm outline-none ring-sky-500/30 focus:ring-2"
                  />
                </label>
                <label className="flex flex-col gap-1 text-xs font-medium text-slate-600">
                  Group rows by
                  <select
                    value={groupBy}
                    onChange={(e) => setGroupBy(e.target.value as GroupBy)}
                    className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm shadow-sm outline-none ring-sky-500/30 focus:ring-2"
                  >
                    {GROUP_OPTIONS.map((opt) => (
                      <option key={opt.value} value={opt.value}>
                        {opt.label}
                      </option>
                    ))}
                  </select>
                </label>
              </div>

              {availableEnvironments.length > 0 && (
                <div className="mt-4">
                  <p className="text-xs font-medium text-slate-600">Environment tags</p>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {availableEnvironments.map((env) => {
                      const on = envTags.has(env);
                      return (
                        <button
                          key={env}
                          type="button"
                          onClick={() => toggleEnv(env)}
                          className={`rounded-full border px-3 py-1 text-xs font-medium transition ${
                            on
                              ? "border-sky-500 bg-sky-500 text-white shadow-sm"
                              : "border-slate-200 bg-slate-50 text-slate-700 hover:border-slate-300"
                          }`}
                        >
                          {env}
                        </button>
                      );
                    })}
                  </div>
                </div>
              )}

              {availableServices.length > 0 && (
                <div className="mt-4">
                  <p className="text-xs font-medium text-slate-600">Service tags</p>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {availableServices.map((svc) => {
                      const on = serviceTags.has(svc);
                      return (
                        <button
                          key={svc}
                          type="button"
                          onClick={() => toggleService(svc)}
                          className={`rounded-full border px-3 py-1 text-xs font-medium transition ${
                            on
                              ? "border-violet-500 bg-violet-600 text-white shadow-sm"
                              : "border-slate-200 bg-slate-50 text-slate-700 hover:border-slate-300"
                          }`}
                        >
                          {svc}
                        </button>
                      );
                    })}
                  </div>
                </div>
              )}
            </section>

            <section className="rounded-2xl border border-slate-200/80 bg-white/95 p-5 shadow-sm">
              <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                <h2 className="text-sm font-semibold text-slate-800">Requests</h2>
                <p className="text-xs text-slate-500">
                  Showing <span className="font-semibold text-slate-800">{filteredSorted.length}</span>{" "}
                  of {rawItems.length} loaded (total in window: {requests.total})
                </p>
              </div>

              {rawItems.length === 0 ? (
                <p className="mt-6 text-sm text-slate-600">
                  No requests in this time window yet. Send traffic to{" "}
                  <code className="rounded bg-slate-100 px-1">POST /ingest</code> or run the manual
                  test script, then refresh.
                </p>
              ) : filteredSorted.length === 0 ? (
                <p className="mt-6 text-sm text-slate-600">
                  No rows match your client filters. Clear filters or widen the time window.
                </p>
              ) : (
                <div className="mt-4 space-y-6">
                  {grouped.map((group) => (
                    <div key={group.key}>
                      {groupBy !== "none" && (
                        <h3 className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
                          <span className="rounded-md bg-slate-100 px-2 py-0.5 text-[10px] text-slate-600">
                            {GROUP_OPTIONS.find((g) => g.value === groupBy)?.label}
                          </span>
                          <span className="text-slate-800">{group.label}</span>
                          <span className="font-normal normal-case text-slate-400">
                            ({group.items.length})
                          </span>
                        </h3>
                      )}
                      <div className="overflow-x-auto rounded-xl border border-slate-200">
                        <table className="min-w-full text-left text-sm">
                          <thead className="bg-slate-50 text-xs font-semibold uppercase tracking-wide text-slate-500">
                            <tr>
                              {(
                                [
                                  ["timestamp", "Time"],
                                  ["method", "Method"],
                                  ["path", "Path"],
                                  ["status_code", "Status"],
                                  ["latency_ms", "Latency"],
                                  ["service_name", "Service"],
                                  ["environment", "Env"],
                                ] as const
                              ).map(([key, label]) => (
                                <th key={key} className="px-3 py-2">
                                  <button
                                    type="button"
                                    onClick={() => onSortHeader(key)}
                                    className="inline-flex items-center gap-1 rounded-md px-1 py-0.5 hover:bg-slate-200/60"
                                  >
                                    {label}
                                    {sortKey === key && (
                                      <span className="text-sky-600" aria-hidden>
                                        {sortDir === "asc" ? "↑" : "↓"}
                                      </span>
                                    )}
                                  </button>
                                </th>
                              ))}
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-slate-100 bg-white">
                            {group.items.map((item) => (
                              <tr key={`${item.timestamp}-${item.request_id ?? item.path}`} className="hover:bg-slate-50/80">
                                <td className="whitespace-nowrap px-3 py-2 text-slate-600">
                                  {formatTimestamp(item.timestamp)}
                                </td>
                                <td className="px-3 py-2">
                                  <span className="rounded-md bg-slate-100 px-2 py-0.5 text-xs font-semibold text-slate-800">
                                    {item.method}
                                  </span>
                                </td>
                                <td className="max-w-[220px] truncate px-3 py-2 font-mono text-xs text-slate-800 sm:max-w-md">
                                  {item.path}
                                </td>
                                <td className="px-3 py-2">
                                  <span
                                    className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-semibold ring-1 ring-inset ${statusTone(item.status_code)}`}
                                  >
                                    {item.status_code}
                                  </span>
                                </td>
                                <td className="whitespace-nowrap px-3 py-2 tabular-nums text-slate-700">
                                  {item.latency_ms.toFixed(1)} ms
                                </td>
                                <td className="px-3 py-2 text-slate-700">{item.service_name}</td>
                                <td className="px-3 py-2">
                                  <span className="rounded-full bg-emerald-500/10 px-2 py-0.5 text-xs font-medium text-emerald-900 ring-1 ring-emerald-500/20">
                                    {item.environment}
                                  </span>
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  ))}
                </div>
              )}
              <div className="mt-4 flex items-center justify-between gap-3 border-t border-slate-100 pt-3 text-xs text-slate-600">
                <p>
                  Page {requestPage + 1} · Offset {requestPage * requestLimit}
                </p>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    disabled={requestPage === 0}
                    onClick={() => setRequestPage((p) => Math.max(0, p - 1))}
                    className="rounded-lg border border-slate-200 bg-white px-2.5 py-1 font-medium text-slate-700 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    Prev
                  </button>
                  <button
                    type="button"
                    disabled={(requestPage + 1) * requestLimit >= requests.total}
                    onClick={() => setRequestPage((p) => p + 1)}
                    className="rounded-lg border border-slate-200 bg-white px-2.5 py-1 font-medium text-slate-700 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    Next
                  </button>
                </div>
              </div>
            </section>
          </>
        )}
      </div>
    </main>
  );
}
