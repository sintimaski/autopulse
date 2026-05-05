"use client";

import { useMemo } from "react";

import { SlidersHorizontal } from "../../lib/icons";
import { useDashboardData } from "./DashboardDataContext";
import { METHOD_OPTIONS, STATUS_CLASS_OPTIONS, WINDOW_OPTIONS } from "./dashboardTypes";

const selectClass =
  "rounded-md border border-slate-200 bg-white py-2 pl-2 pr-8 text-sm text-slate-900 shadow-sm outline-none focus:ring-1 focus:ring-sky-500/50 dark:border-neutral-600 dark:bg-neutral-800 dark:text-neutral-100 dark:focus:ring-neutral-500/40";

const labelClass = "text-sm text-slate-600 dark:text-neutral-400";

export function OverviewScopeFacetBoard() {
  const d = useDashboardData();

  const envOptions = useMemo(
    () => [...new Set([...d.availableEnvironments, ...d.serverEnvironmentTags])].sort(),
    [d.availableEnvironments, d.serverEnvironmentTags],
  );
  const serviceOptions = useMemo(
    () => [...new Set([...d.availableServices, ...d.serverServiceTags])].sort(),
    [d.availableServices, d.serverServiceTags],
  );

  const envValue = d.serverEnvironmentTags.length === 1 ? d.serverEnvironmentTags[0] : "";
  const serviceValue = d.serverServiceTags.length === 1 ? d.serverServiceTags[0] : "";

  return (
    <div className="flex min-w-0 flex-wrap items-center gap-x-6 gap-y-4">
      <div
        className="flex min-w-0 shrink-0 items-center gap-2 border-r border-slate-200 pr-4 dark:border-neutral-600"
        title="Window, method, status, env, and service use the same URL query keys as Diagnosis and Requests. Open those pages for path, latency, or SQL-scoped filters."
      >
        <SlidersHorizontal className="size-4 shrink-0 text-slate-500 dark:text-neutral-400" aria-hidden />
        <span className="text-sm font-semibold text-slate-700 dark:text-neutral-200">Overview scope</span>
      </div>
      <label
        className={`flex items-center gap-1.5 ${labelClass}`}
        title="Applies to every chart and number below"
      >
        <span className="shrink-0">Window</span>
        <select
          value={d.windowMinutes}
          onChange={(e) => {
            d.onServerWindowChange(Number(e.target.value));
          }}
          className={selectClass}
          aria-label="Time window for all dashboard metrics"
        >
          {WINDOW_OPTIONS.map((minutes) => (
            <option key={minutes} value={minutes}>
              {minutes >= 60 ? `${Math.round(minutes / 60)}h` : `${minutes}m`}
            </option>
          ))}
        </select>
      </label>
      <label className={`flex items-center gap-1.5 ${labelClass}`}>
        <span className="shrink-0">Method</span>
        <select
          value={d.method}
          onChange={(e) => {
            d.onServerMethodChange(e.target.value);
            d.setRequestPage(0);
            d.setErrorGroupPage(0);
          }}
          className={selectClass}
        >
          {METHOD_OPTIONS.map((m) => (
            <option key={m} value={m}>
              {m}
            </option>
          ))}
        </select>
      </label>
      <label className={`flex items-center gap-1.5 ${labelClass}`}>
        <span className="shrink-0">Status</span>
        <select
          value={d.statusClass}
          onChange={(e) => {
            d.onServerStatusClassChange(e.target.value);
            d.setRequestPage(0);
            d.setErrorGroupPage(0);
          }}
          className={selectClass}
        >
          {STATUS_CLASS_OPTIONS.map((s) => (
            <option key={s} value={s}>
              {s === "ALL" ? "All" : `${s}xx`}
            </option>
          ))}
        </select>
      </label>
      <label className={`flex items-center gap-1.5 ${labelClass}`}>
        <span className="shrink-0">Env</span>
        <select
          value={envValue}
          onChange={(e) => {
            const v = e.target.value;
            d.setServerEnvironmentTags(v ? [v] : []);
            d.setRequestPage(0);
            d.setErrorGroupPage(0);
          }}
          className={selectClass}
        >
          <option value="">All</option>
          {envOptions.map((name) => (
            <option key={name} value={name}>
              {name}
            </option>
          ))}
        </select>
      </label>
      <label className={`flex items-center gap-1.5 ${labelClass}`}>
        <span className="shrink-0">Service</span>
        <select
          value={serviceValue}
          onChange={(e) => {
            const v = e.target.value;
            d.setServerServiceTags(v ? [v] : []);
            d.setRequestPage(0);
            d.setErrorGroupPage(0);
          }}
          className={selectClass}
        >
          <option value="">All</option>
          {serviceOptions.map((name) => (
            <option key={name} value={name}>
              {name}
            </option>
          ))}
        </select>
      </label>
    </div>
  );
}
