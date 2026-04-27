"use client";

import { useDashboardData } from "./DashboardDataContext";

export function ServerQueryToolbar() {
  const d = useDashboardData();
  return (
    <div className="flex flex-wrap items-end gap-3">
      <p className="mr-1 hidden text-xs font-medium text-slate-500 dark:text-neutral-400 lg:block">
        Server query
      </p>
      <label className="flex flex-col gap-1 text-xs font-medium text-slate-600 dark:text-neutral-300">
        Time window
        <select
          value={d.windowMinutes}
          onChange={(e) => d.onServerWindowChange(Number(e.target.value))}
          className="min-w-[132px] rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm outline-none ring-sky-500/30 focus:ring-2 dark:border-neutral-700 dark:bg-neutral-800 dark:text-neutral-100 dark:ring-neutral-600/40 dark:focus:ring-neutral-500/50"
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
          className="min-w-[108px] rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm shadow-sm outline-none ring-sky-500/30 focus:ring-2 dark:border-neutral-700 dark:bg-neutral-800 dark:text-neutral-100 dark:ring-neutral-600/40 dark:focus:ring-neutral-500/50"
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
          className="min-w-[108px] rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm shadow-sm outline-none ring-sky-500/30 focus:ring-2 dark:border-neutral-700 dark:bg-neutral-800 dark:text-neutral-100 dark:ring-neutral-600/40 dark:focus:ring-neutral-500/50"
        >
          {d.STATUS_CLASS_OPTIONS.map((value) => (
            <option key={value} value={value}>
              {value === "ALL" ? value : `${value}xx`}
            </option>
          ))}
        </select>
      </label>
      <label className="flex flex-col gap-1 text-xs font-medium text-slate-600 dark:text-neutral-300">
        Request page size
        <select
          value={d.requestLimit}
          onChange={(e) => {
            d.setRequestLimit(Number(e.target.value));
            d.setRequestPage(0);
          }}
          className="min-w-[108px] rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm shadow-sm outline-none ring-sky-500/30 focus:ring-2 dark:border-neutral-700 dark:bg-neutral-800 dark:text-neutral-100 dark:ring-neutral-600/40 dark:focus:ring-neutral-500/50"
        >
          {d.REQUEST_LIMIT_OPTIONS.map((value) => (
            <option key={value} value={value}>
              {value} / page
            </option>
          ))}
        </select>
      </label>
      <label className="flex flex-col gap-1 text-xs font-medium text-slate-600 dark:text-neutral-300">
        Error groups / page
        <select
          value={d.errorGroupLimit}
          onChange={(e) => {
            d.setErrorGroupLimit(Number(e.target.value));
            d.setErrorGroupPage(0);
          }}
          className="min-w-[132px] rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm shadow-sm outline-none ring-sky-500/30 focus:ring-2 dark:border-neutral-700 dark:bg-neutral-800 dark:text-neutral-100 dark:ring-neutral-600/40 dark:focus:ring-neutral-500/50"
        >
          {d.ERROR_GROUP_LIMIT_OPTIONS.map((value) => (
            <option key={value} value={value}>
              {value} / page
            </option>
          ))}
        </select>
      </label>
    </div>
  );
}
