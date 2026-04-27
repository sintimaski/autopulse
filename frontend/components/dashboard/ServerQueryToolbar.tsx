"use client";

import { useDashboardData } from "./DashboardDataContext";

export function ServerQueryToolbar() {
  const d = useDashboardData();
  const activeServerFilterCount = [
    d.method !== "ALL",
    d.statusClass !== "ALL",
    d.pathQuery.trim() !== "",
    d.minLatencyMs.trim() !== "",
    d.maxLatencyMs.trim() !== "",
    d.serverEnvironmentQuery.trim() !== "",
    d.serverServiceQuery.trim() !== "",
  ].filter(Boolean).length;

  return (
    <div className="rounded-xl border border-slate-200 bg-slate-50/80 p-3 dark:border-neutral-700 dark:bg-neutral-900/80">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-600 dark:text-neutral-300">
            Server scope
          </p>
          <span className="rounded-full bg-slate-200 px-2 py-0.5 text-[11px] font-medium text-slate-700 dark:bg-neutral-800 dark:text-neutral-300">
            {activeServerFilterCount} active
          </span>
        </div>
      </div>

      <div className="grid gap-3 md:grid-cols-3 xl:grid-cols-5">
        <label className="flex flex-col gap-1 text-xs font-medium text-slate-600 dark:text-neutral-300">
          Time window
          <select
            value={d.windowMinutes}
            onChange={(e) => d.onServerWindowChange(Number(e.target.value))}
            className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm outline-none ring-sky-500/30 focus:ring-2 dark:border-neutral-700 dark:bg-neutral-800 dark:text-neutral-100 dark:ring-neutral-600/40 dark:focus:ring-neutral-500/50"
          >
            {d.WINDOW_OPTIONS.map((minutes) => (
              <option key={minutes} value={minutes}>
                Last {minutes}m
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-xs font-medium text-slate-600 dark:text-neutral-300">
          Method
          <select
            value={d.method}
            onChange={(e) => d.onServerMethodChange(e.target.value)}
            className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm shadow-sm outline-none ring-sky-500/30 focus:ring-2 dark:border-neutral-700 dark:bg-neutral-800 dark:text-neutral-100 dark:ring-neutral-600/40 dark:focus:ring-neutral-500/50"
          >
            {d.METHOD_OPTIONS.map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-xs font-medium text-slate-600 dark:text-neutral-300">
          Status class
          <select
            value={d.statusClass}
            onChange={(e) => d.onServerStatusClassChange(e.target.value)}
            className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm shadow-sm outline-none ring-sky-500/30 focus:ring-2 dark:border-neutral-700 dark:bg-neutral-800 dark:text-neutral-100 dark:ring-neutral-600/40 dark:focus:ring-neutral-500/50"
          >
            {d.STATUS_CLASS_OPTIONS.map((value) => (
              <option key={value} value={value}>
                {value === "ALL" ? value : `${value}xx`}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-xs font-medium text-slate-600 dark:text-neutral-300">
          Min latency (ms)
          <input
            type="number"
            min={0}
            step="1"
            value={d.minLatencyMs}
            onChange={(e) => {
              d.setMinLatencyMs(e.target.value);
              d.setRequestPage(0);
            }}
            placeholder="0"
            className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm shadow-sm outline-none ring-sky-500/30 focus:ring-2 dark:border-neutral-700 dark:bg-neutral-800 dark:text-neutral-100 dark:ring-neutral-600/40 dark:focus:ring-neutral-500/50"
          />
        </label>
        <label className="flex flex-col gap-1 text-xs font-medium text-slate-600 dark:text-neutral-300">
          Max latency (ms)
          <input
            type="number"
            min={0}
            step="1"
            value={d.maxLatencyMs}
            onChange={(e) => {
              d.setMaxLatencyMs(e.target.value);
              d.setRequestPage(0);
            }}
            placeholder="5000"
            className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm shadow-sm outline-none ring-sky-500/30 focus:ring-2 dark:border-neutral-700 dark:bg-neutral-800 dark:text-neutral-100 dark:ring-neutral-600/40 dark:focus:ring-neutral-500/50"
          />
        </label>
      </div>

      <div className="mt-3 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        <label className="xl:col-span-2 flex flex-col gap-1 text-xs font-medium text-slate-600 dark:text-neutral-300">
          Path contains
          <input
            type="search"
            value={d.pathQuery}
            onChange={(e) => {
              d.setPathQuery(e.target.value);
              d.setRequestPage(0);
            }}
            placeholder="/orders, /health, ..."
            className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm shadow-sm outline-none ring-sky-500/30 focus:ring-2 dark:border-neutral-700 dark:bg-neutral-800 dark:text-neutral-100 dark:ring-neutral-600/40 dark:focus:ring-neutral-500/50"
          />
        </label>
        <label className="flex flex-col gap-1 text-xs font-medium text-slate-600 dark:text-neutral-300">
          Environment tags
          <input
            type="text"
            value={d.serverEnvironmentQuery}
            onChange={(e) => {
              d.setServerEnvironmentQuery(e.target.value);
              d.setRequestPage(0);
            }}
            placeholder="prod, staging"
            className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm shadow-sm outline-none ring-sky-500/30 focus:ring-2 dark:border-neutral-700 dark:bg-neutral-800 dark:text-neutral-100 dark:ring-neutral-600/40 dark:focus:ring-neutral-500/50"
          />
        </label>
        <label className="flex flex-col gap-1 text-xs font-medium text-slate-600 dark:text-neutral-300">
          Service tags
          <input
            type="text"
            value={d.serverServiceQuery}
            onChange={(e) => {
              d.setServerServiceQuery(e.target.value);
              d.setRequestPage(0);
            }}
            placeholder="api, worker"
            className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm shadow-sm outline-none ring-sky-500/30 focus:ring-2 dark:border-neutral-700 dark:bg-neutral-800 dark:text-neutral-100 dark:ring-neutral-600/40 dark:focus:ring-neutral-500/50"
          />
        </label>
      </div>

      <div className="mt-3 grid gap-3 md:max-w-[380px] md:grid-cols-2">
        <label className="flex flex-col gap-1 text-xs font-medium text-slate-600 dark:text-neutral-300">
          Request rows per page
          <select
            value={d.requestLimit}
            onChange={(e) => {
              d.setRequestLimit(Number(e.target.value));
              d.setRequestPage(0);
            }}
            className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm shadow-sm outline-none ring-sky-500/30 focus:ring-2 dark:border-neutral-700 dark:bg-neutral-800 dark:text-neutral-100 dark:ring-neutral-600/40 dark:focus:ring-neutral-500/50"
          >
            {d.REQUEST_LIMIT_OPTIONS.map((value) => (
              <option key={value} value={value}>
                {value} / page
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-xs font-medium text-slate-600 dark:text-neutral-300">
          Error groups per page
          <select
            value={d.errorGroupLimit}
            onChange={(e) => {
              d.setErrorGroupLimit(Number(e.target.value));
              d.setErrorGroupPage(0);
            }}
            className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm shadow-sm outline-none ring-sky-500/30 focus:ring-2 dark:border-neutral-700 dark:bg-neutral-800 dark:text-neutral-100 dark:ring-neutral-600/40 dark:focus:ring-neutral-500/50"
          >
            {d.ERROR_GROUP_LIMIT_OPTIONS.map((value) => (
              <option key={value} value={value}>
                {value} / page
              </option>
            ))}
          </select>
        </label>
      </div>
    </div>
  );
}
