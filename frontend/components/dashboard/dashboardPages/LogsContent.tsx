"use client";

import { Fragment } from "react";

import { formatTimestamp, GROUP_OPTIONS, statusTone, type GroupBy } from "../dashboardTypes";
import { useDashboardData } from "../DashboardDataContext";

export function LogsContent() {
  const d = useDashboardData();
  const requests = d.requests;
  if (!requests) {
    return null;
  }

  return (
    <>
      <section className="rounded-2xl border border-slate-200/80 bg-white/95 p-5 shadow-sm">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <h2 className="text-sm font-semibold text-slate-800">Client filters & grouping</h2>
            <p className="mt-1 text-xs text-slate-500">
              Applies only to the {requests.limit} rows loaded for this page. Path, environment, and
              service filters are client-side until backend query params are added.
            </p>
          </div>
          <button
            type="button"
            onClick={d.clearClientFilters}
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
              value={d.pathQuery}
              onChange={(e) => d.setPathQuery(e.target.value)}
              placeholder="/users, /health, …"
              className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm shadow-sm outline-none ring-sky-500/30 focus:ring-2"
            />
          </label>
          <label className="flex flex-col gap-1 text-xs font-medium text-slate-600">
            Group rows by
            <select
              value={d.groupBy}
              onChange={(e) => d.setGroupBy(e.target.value as GroupBy)}
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

        {d.availableEnvironments.length > 0 && (
          <div className="mt-4">
            <p className="text-xs font-medium text-slate-600">Environment tags</p>
            <div className="mt-2 flex flex-wrap gap-2">
              {d.availableEnvironments.map((env) => {
                const on = d.envTags.has(env);
                return (
                  <button
                    key={env}
                    type="button"
                    onClick={() => d.toggleEnv(env)}
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

        {d.availableServices.length > 0 && (
          <div className="mt-4">
            <p className="text-xs font-medium text-slate-600">Service tags</p>
            <div className="mt-2 flex flex-wrap gap-2">
              {d.availableServices.map((svc) => {
                const on = d.serviceTags.has(svc);
                return (
                  <button
                    key={svc}
                    type="button"
                    onClick={() => d.toggleService(svc)}
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
            Showing <span className="font-semibold text-slate-800">{d.filteredSorted.length}</span> of{" "}
            {d.rawItems.length} loaded (total in window: {requests.total})
          </p>
        </div>

        <div className="mt-4 rounded-xl border border-slate-200/90 bg-slate-50/80 p-4">
          <p className="text-xs font-medium text-slate-600">Server query (same as header bar)</p>
          <p className="mt-0.5 text-[11px] text-slate-500">
            Backend supports time range, HTTP method, status class, limit, and offset (pagination below).
            Path, service, and environment are filtered client-side after load.
          </p>
          <div className="mt-3 flex flex-wrap items-end gap-3">
            <label className="flex flex-col gap-1 text-xs font-medium text-slate-600">
              Time window
              <select
                value={d.windowMinutes}
                onChange={(e) => d.onServerWindowChange(Number(e.target.value))}
                className="min-w-[120px] rounded-lg border border-slate-200 bg-white px-2.5 py-2 text-sm shadow-sm outline-none ring-sky-500/30 focus:ring-2"
              >
                {d.WINDOW_OPTIONS.map((minutes) => (
                  <option key={minutes} value={minutes}>
                    Last {minutes}m
                  </option>
                ))}
              </select>
            </label>
            <label className="flex flex-col gap-1 text-xs font-medium text-slate-600">
              Method
              <select
                value={d.method}
                onChange={(e) => d.onServerMethodChange(e.target.value)}
                className="min-w-[100px] rounded-lg border border-slate-200 bg-white px-2.5 py-2 text-sm shadow-sm outline-none ring-sky-500/30 focus:ring-2"
              >
                {d.METHOD_OPTIONS.map((value) => (
                  <option key={value} value={value}>
                    {value}
                  </option>
                ))}
              </select>
            </label>
            <label className="flex flex-col gap-1 text-xs font-medium text-slate-600">
              Status class
              <select
                value={d.statusClass}
                onChange={(e) => d.onServerStatusClassChange(e.target.value)}
                className="min-w-[100px] rounded-lg border border-slate-200 bg-white px-2.5 py-2 text-sm shadow-sm outline-none ring-sky-500/30 focus:ring-2"
              >
                {d.STATUS_CLASS_OPTIONS.map((value) => (
                  <option key={value} value={value}>
                    {value === "ALL" ? value : `${value}xx`}
                  </option>
                ))}
              </select>
            </label>
            <label className="flex flex-col gap-1 text-xs font-medium text-slate-600">
              Page size
              <select
                value={d.requestLimit}
                onChange={(e) => {
                  d.setRequestLimit(Number(e.target.value));
                  d.setRequestPage(0);
                }}
                className="min-w-[100px] rounded-lg border border-slate-200 bg-white px-2.5 py-2 text-sm shadow-sm outline-none ring-sky-500/30 focus:ring-2"
              >
                {d.REQUEST_LIMIT_OPTIONS.map((value) => (
                  <option key={value} value={value}>
                    {value}
                  </option>
                ))}
              </select>
            </label>
          </div>
        </div>

        {d.rawItems.length === 0 ? (
          <p className="mt-6 text-sm text-slate-600">
            No requests in this time window yet. Send traffic to{" "}
            <code className="rounded bg-slate-100 px-1">POST /ingest</code> or run the manual test script,
            then refresh.
          </p>
        ) : d.filteredSorted.length === 0 ? (
          <p className="mt-6 text-sm text-slate-600">
            No rows match your client filters. Clear filters or widen the time window.
          </p>
        ) : (
          <div className="mt-4 space-y-6">
            {d.grouped.map((group) => (
              <div key={group.key}>
                {d.groupBy !== "none" && (
                  <h3 className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
                    <span className="rounded-md bg-slate-100 px-2 py-0.5 text-[10px] text-slate-600">
                      {GROUP_OPTIONS.find((g) => g.value === d.groupBy)?.label}
                    </span>
                    <span className="text-slate-800">{group.label}</span>
                    <span className="font-normal normal-case text-slate-400">({group.items.length})</span>
                  </h3>
                )}
                <div className="overflow-x-auto rounded-xl border border-slate-200">
                  <table className="min-w-full text-left text-sm">
                    <thead className="bg-slate-50 text-xs font-semibold uppercase tracking-wide text-slate-500">
                      <tr>
                        <th className="w-10 px-2 py-2" aria-label="Expand row" />
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
                              onClick={() => d.onSortHeader(key)}
                              className="inline-flex items-center gap-1 rounded-md px-1 py-0.5 hover:bg-slate-200/60"
                            >
                              {label}
                              {d.sortKey === key && (
                                <span className="text-sky-600" aria-hidden>
                                  {d.sortDir === "asc" ? "↑" : "↓"}
                                </span>
                              )}
                            </button>
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 bg-white">
                      {group.items.map((item, rowIndex) => {
                        const rowId = [
                          group.key,
                          String(rowIndex),
                          item.timestamp,
                          item.method,
                          item.path,
                          String(item.status_code),
                          String(item.latency_ms),
                          item.service_name,
                          item.environment,
                        ].join("|");
                        const open = d.expandedRequestIds.has(rowId);
                        return (
                          <Fragment key={rowId}>
                            <tr
                              role="button"
                              tabIndex={0}
                              aria-expanded={open}
                              onClick={() => d.toggleRequestRow(rowId)}
                              onKeyDown={(e) => {
                                if (e.key === "Enter" || e.key === " ") {
                                  e.preventDefault();
                                  d.toggleRequestRow(rowId);
                                }
                              }}
                              className="cursor-pointer border-l-2 border-transparent hover:border-sky-500/80 hover:bg-slate-50/90"
                            >
                              <td className="px-2 py-2 text-center text-xs text-slate-400" aria-hidden>
                                {open ? "▼" : "▶"}
                              </td>
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
                            {open ? (
                              <tr className="bg-slate-50/95">
                                <td
                                  colSpan={8}
                                  className="px-4 py-3 text-xs text-slate-700"
                                  onClick={(e) => e.stopPropagation()}
                                >
                                  <dl className="grid gap-3 sm:grid-cols-2">
                                    <div>
                                      <dt className="font-semibold text-slate-500">Request id</dt>
                                      <dd className="mt-0.5 break-all font-mono text-slate-900">
                                        {item.request_id ?? "— (not reported by SDK)"}
                                      </dd>
                                    </div>
                                    <div>
                                      <dt className="font-semibold text-slate-500">Timestamp (ISO)</dt>
                                      <dd className="mt-0.5 break-all font-mono text-slate-900">
                                        {item.timestamp}
                                      </dd>
                                    </div>
                                    <div className="sm:col-span-2">
                                      <dt className="font-semibold text-slate-500">Path</dt>
                                      <dd className="mt-0.5 break-all font-mono text-[13px] text-slate-900">
                                        {item.path}
                                      </dd>
                                    </div>
                                    <div>
                                      <dt className="font-semibold text-slate-500">Status</dt>
                                      <dd className="mt-0.5 tabular-nums text-slate-900">{item.status_code}</dd>
                                    </div>
                                    <div>
                                      <dt className="font-semibold text-slate-500">Latency</dt>
                                      <dd className="mt-0.5 tabular-nums text-slate-900">
                                        {item.latency_ms.toFixed(3)} ms
                                      </dd>
                                    </div>
                                    <div>
                                      <dt className="font-semibold text-slate-500">Service</dt>
                                      <dd className="mt-0.5 text-slate-900">{item.service_name}</dd>
                                    </div>
                                    <div>
                                      <dt className="font-semibold text-slate-500">Environment</dt>
                                      <dd className="mt-0.5 text-slate-900">{item.environment}</dd>
                                    </div>
                                  </dl>
                                  <p className="mt-3 text-[11px] text-slate-500">
                                    Click the row again to collapse. Sorting uses the client-side slice after
                                    server filters.
                                  </p>
                                </td>
                              </tr>
                            ) : null}
                          </Fragment>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            ))}
          </div>
        )}
        <div className="mt-4 flex items-center justify-between gap-3 border-t border-slate-100 pt-3 text-xs text-slate-600">
          <p>
            Page {d.requestPage + 1} · Offset {d.requestPage * d.requestLimit}
          </p>
          <div className="flex items-center gap-2">
            <button
              type="button"
              disabled={d.requestPage === 0}
              onClick={() => d.setRequestPage((p) => Math.max(0, p - 1))}
              className="rounded-lg border border-slate-200 bg-white px-2.5 py-1 font-medium text-slate-700 disabled:cursor-not-allowed disabled:opacity-50"
            >
              Prev
            </button>
            <button
              type="button"
              disabled={(d.requestPage + 1) * d.requestLimit >= requests.total}
              onClick={() => d.setRequestPage((p) => p + 1)}
              className="rounded-lg border border-slate-200 bg-white px-2.5 py-1 font-medium text-slate-700 disabled:cursor-not-allowed disabled:opacity-50"
            >
              Next
            </button>
          </div>
        </div>
      </section>
    </>
  );
}
