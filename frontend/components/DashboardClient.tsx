"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

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

const apiBaseUrl = process.env.NEXT_PUBLIC_AUTOPULSE_API_BASE_URL ?? "http://localhost:8000";
const apiKey = process.env.NEXT_PUBLIC_AUTOPULSE_API_KEY;

const WINDOW_OPTIONS = [15, 60, 240, 1440];
const METHOD_OPTIONS = ["ALL", "GET", "POST", "PUT", "PATCH", "DELETE"];
const STATUS_CLASS_OPTIONS = ["ALL", "2", "4", "5"];
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
  const max = Math.max(...series.map((b) => b.request_count), 1);
  return (
    <div
      className="flex h-14 items-end gap-px rounded-xl border border-slate-200/80 bg-gradient-to-b from-white to-slate-50 px-2 py-2"
      role="img"
      aria-label="Requests per minute buckets"
    >
      {series.map((bucket) => {
        const h = Math.round((bucket.request_count / max) * 100);
        const errRatio = bucket.request_count ? bucket.error_count / bucket.request_count : 0;
        const barColor =
          errRatio > 0.25 ? "bg-rose-500/80" : errRatio > 0 ? "bg-amber-400/90" : "bg-sky-500/80";
        return (
          <div
            key={bucket.minute}
            className="group relative min-w-[3px] flex-1"
            title={`${bucket.request_count} req, ${bucket.error_count} err`}
          >
            <div
              className={`w-full rounded-sm ${barColor} transition-all group-hover:opacity-90`}
              style={{ height: `${Math.max(h, 8)}%` }}
            />
          </div>
        );
      })}
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
  const [pathQuery, setPathQuery] = useState("");
  const [groupBy, setGroupBy] = useState<GroupBy>("none");
  const [sortKey, setSortKey] = useState<SortKey>("timestamp");
  const [sortDir, setSortDir] = useState<SortDir>("desc");
  const [envTags, setEnvTags] = useState<Set<string>>(new Set());
  const [serviceTags, setServiceTags] = useState<Set<string>>(new Set());
  const [overview, setOverview] = useState<OverviewResponse | null>(null);
  const [requests, setRequests] = useState<RequestsResponse | null>(null);
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
          limit: "200",
        });
        if (method !== "ALL") {
          requestsParams.set("method", method);
        }
        if (statusClass !== "ALL") {
          requestsParams.set("status_class", statusClass);
        }

        const [overviewResponse, requestsResponse] = await Promise.all([
          fetch(`${apiBaseUrl}/dashboard/overview?${overviewParams.toString()}`, { headers }),
          fetch(`${apiBaseUrl}/dashboard/requests?${requestsParams.toString()}`, { headers }),
        ]);
        if (!overviewResponse.ok || !requestsResponse.ok) {
          throw new Error("Dashboard API request failed. Check API URL/key and backend status.");
        }
        const overviewData = (await overviewResponse.json()) as OverviewResponse;
        const requestsData = (await requestsResponse.json()) as RequestsResponse;
        setOverview(overviewData);
        setRequests(requestsData);
      } catch (error) {
        const message =
          error instanceof Error ? error.message : "Unexpected dashboard loading failure.";
        setErrorMessage(message);
      } finally {
        setLoading(false);
      }
    };

    void run();
  }, [method, statusClass, toIsoWindow, refreshToken]);

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
              Scan rate, errors, and latency in seconds. Tune server filters, then slice client-side
              by path, service, and environment.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
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

        {!loading && !errorMessage && overview && requests && (
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
                <Sparkline series={overview.series} />
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
            </section>
          </>
        )}
      </div>
    </main>
  );
}
