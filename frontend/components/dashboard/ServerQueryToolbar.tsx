"use client";

import { useRef, useState, type KeyboardEventHandler } from "react";

import { useDashboardData } from "./DashboardDataContext";

function isoToLocalInputValue(iso: string): string {
  const date = new Date(iso);
  if (!Number.isFinite(date.getTime())) {
    return "";
  }
  const pad = (n: number) => String(n).padStart(2, "0");
  const yyyy = date.getFullYear();
  const mm = pad(date.getMonth() + 1);
  const dd = pad(date.getDate());
  const hh = pad(date.getHours());
  const min = pad(date.getMinutes());
  return `${yyyy}-${mm}-${dd}T${hh}:${min}`;
}

function parseLocalDateTimeInput(value: string): Date | null {
  const match = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})$/.exec(value);
  if (!match) {
    return null;
  }
  const [, y, mo, d, h, mi] = match;
  const year = Number(y);
  const monthIndex = Number(mo) - 1;
  const day = Number(d);
  const hour = Number(h);
  const minute = Number(mi);
  const date = new Date(year, monthIndex, day, hour, minute, 0, 0);
  if (!Number.isFinite(date.getTime())) {
    return null;
  }
  return date;
}

function formatRelativeToUserTime(serverIso: string): string {
  const serverMs = new Date(serverIso).getTime();
  const userMs = Date.now();
  if (!Number.isFinite(serverMs)) {
    return "";
  }
  const diffMinutes = Math.round((serverMs - userMs) / (60 * 1000));
  if (diffMinutes === 0) {
    return "same as your local time";
  }
  if (diffMinutes > 0) {
    return `${diffMinutes}m ahead of your local time`;
  }
  return `${Math.abs(diffMinutes)}m behind your local time`;
}

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
  const fromInputRef = useRef<HTMLInputElement>(null);
  const toInputRef = useRef<HTMLInputElement>(null);
  const methodRef = useRef<HTMLSelectElement>(null);
  const statusClassRef = useRef<HTMLSelectElement>(null);
  const minLatencyRef = useRef<HTMLInputElement>(null);
  const maxLatencyRef = useRef<HTMLInputElement>(null);
  const pathRef = useRef<HTMLInputElement>(null);
  const envRef = useRef<HTMLInputElement>(null);
  const serviceRef = useRef<HTMLInputElement>(null);
  const errorGroupSortRef = useRef<HTMLSelectElement>(null);
  const [windowError, setWindowError] = useState<string | null>(null);

  const resetServerFilters = () => {
    d.onServerMethodChange("ALL");
    d.onServerStatusClassChange("ALL");
    d.setPathQuery("");
    d.setMinLatencyMs("");
    d.setMaxLatencyMs("");
    d.setServerEnvironmentQuery("");
    d.setServerServiceQuery("");
    d.setErrorGroupSort("last_seen");
    d.setRequestPage(0);
    d.setErrorGroupPage(0);
    if (methodRef.current) methodRef.current.value = "ALL";
    if (statusClassRef.current) statusClassRef.current.value = "ALL";
    if (minLatencyRef.current) minLatencyRef.current.value = "";
    if (maxLatencyRef.current) maxLatencyRef.current.value = "";
    if (pathRef.current) pathRef.current.value = "";
    if (envRef.current) envRef.current.value = "";
    if (serviceRef.current) serviceRef.current.value = "";
    if (errorGroupSortRef.current) errorGroupSortRef.current.value = "last_seen";
  };
  const applyFilters = () => {
    const currentScrollY = window.scrollY;
    d.onServerMethodChange(methodRef.current?.value ?? "ALL");
    d.onServerStatusClassChange(statusClassRef.current?.value ?? "ALL");
    d.setMinLatencyMs(minLatencyRef.current?.value ?? "");
    d.setMaxLatencyMs(maxLatencyRef.current?.value ?? "");
    d.setPathQuery(pathRef.current?.value ?? "");
    d.setServerEnvironmentQuery(envRef.current?.value ?? "");
    d.setServerServiceQuery(serviceRef.current?.value ?? "");
    d.setErrorGroupSort((errorGroupSortRef.current?.value as "last_seen" | "count") ?? "last_seen");
    d.setRequestPage(0);
    d.setErrorGroupPage(0);
    window.requestAnimationFrame(() => {
      window.scrollTo({ top: currentScrollY, behavior: "auto" });
    });
  };
  const applyAbsoluteWindow = () => {
    const fromRaw = fromInputRef.current?.value ?? "";
    const toRaw = toInputRef.current?.value ?? "";
    const fromDate = parseLocalDateTimeInput(fromRaw);
    const toDate = parseLocalDateTimeInput(toRaw);
    if (!fromDate || !toDate) {
      setWindowError("Choose valid start and end date/time.");
      return;
    }
    if (fromDate.getTime() >= toDate.getTime()) {
      setWindowError("Start must be earlier than end.");
      return;
    }
    d.setAbsoluteWindow(fromDate.toISOString(), toDate.toISOString());
    setWindowError(null);
  };
  const onToolbarKeyDown: KeyboardEventHandler<HTMLDivElement> = (event) => {
    if (event.key !== "Enter") {
      return;
    }
    const target = event.target as HTMLElement;
    const tag = target.tagName;
    if (tag === "BUTTON" || tag === "TEXTAREA") {
      return;
    }
    event.preventDefault();
    applyFilters();
  };

  return (
    <div
      className="rounded-xl border border-slate-200 bg-slate-50/80 p-3 dark:border-neutral-700 dark:bg-neutral-900/80"
      onKeyDown={onToolbarKeyDown}
    >
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-600 dark:text-neutral-300">
            Server scope
          </p>
          <span className="rounded-full bg-slate-200 px-2 py-0.5 text-[11px] font-medium text-slate-700 dark:bg-neutral-800 dark:text-neutral-300">
            {activeServerFilterCount} active
          </span>
        </div>
        <button
          type="button"
          onClick={resetServerFilters}
          className="rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-100 dark:border-neutral-700 dark:bg-neutral-800 dark:text-neutral-200 dark:hover:bg-neutral-700"
        >
          Reset filters
        </button>
        <button
          type="button"
          onClick={applyFilters}
          className="rounded-lg border border-sky-300 bg-sky-50 px-2.5 py-1.5 text-xs font-medium text-sky-900 hover:bg-sky-100 dark:border-neutral-600 dark:bg-neutral-800 dark:text-neutral-100 dark:hover:bg-neutral-700"
        >
          Apply filters
        </button>
      </div>

      <div className="grid gap-3 md:grid-cols-3 xl:grid-cols-5">
        <label className="flex flex-col gap-1 text-xs font-medium text-slate-600 dark:text-neutral-300">
          Quick range
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
          From
          <input
            key={`from-${d.windowFromTimestamp}`}
            ref={fromInputRef}
            type="datetime-local"
            defaultValue={isoToLocalInputValue(d.windowFromTimestamp)}
            className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm shadow-sm outline-none ring-sky-500/30 focus:ring-2 dark:border-neutral-700 dark:bg-neutral-800 dark:text-neutral-100 dark:ring-neutral-600/40 dark:focus:ring-neutral-500/50"
          />
        </label>
        <label className="flex flex-col gap-1 text-xs font-medium text-slate-600 dark:text-neutral-300">
          To
          <input
            key={`to-${d.windowToTimestamp}`}
            ref={toInputRef}
            type="datetime-local"
            defaultValue={isoToLocalInputValue(d.windowToTimestamp)}
            className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm shadow-sm outline-none ring-sky-500/30 focus:ring-2 dark:border-neutral-700 dark:bg-neutral-800 dark:text-neutral-100 dark:ring-neutral-600/40 dark:focus:ring-neutral-500/50"
          />
        </label>
        <div className="flex items-end gap-2">
          <button
            type="button"
            onClick={applyAbsoluteWindow}
            className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-medium text-slate-700 hover:bg-slate-100 dark:border-neutral-700 dark:bg-neutral-800 dark:text-neutral-200 dark:hover:bg-neutral-700"
          >
            Apply window
          </button>
          {d.isAbsoluteWindow ? (
            <button
              type="button"
              onClick={d.clearAbsoluteWindow}
              className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-medium text-slate-700 hover:bg-slate-100 dark:border-neutral-700 dark:bg-neutral-800 dark:text-neutral-200 dark:hover:bg-neutral-700"
            >
              Use quick range
            </button>
          ) : null}
        </div>
        <label className="flex flex-col gap-1 text-xs font-medium text-slate-600 dark:text-neutral-300">
          Method
          <select
            key={`method-${d.method}`}
            ref={methodRef}
            defaultValue={d.method}
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
            key={`status-${d.statusClass}`}
            ref={statusClassRef}
            defaultValue={d.statusClass}
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
            key={`min-${d.minLatencyMs}`}
            ref={minLatencyRef}
            type="number"
            min={0}
            step="1"
            defaultValue={d.minLatencyMs}
            placeholder="0"
            className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm shadow-sm outline-none ring-sky-500/30 focus:ring-2 dark:border-neutral-700 dark:bg-neutral-800 dark:text-neutral-100 dark:ring-neutral-600/40 dark:focus:ring-neutral-500/50"
          />
        </label>
        <label className="flex flex-col gap-1 text-xs font-medium text-slate-600 dark:text-neutral-300">
          Max latency (ms)
          <input
            key={`max-${d.maxLatencyMs}`}
            ref={maxLatencyRef}
            type="number"
            min={0}
            step="1"
            defaultValue={d.maxLatencyMs}
            placeholder="5000"
            className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm shadow-sm outline-none ring-sky-500/30 focus:ring-2 dark:border-neutral-700 dark:bg-neutral-800 dark:text-neutral-100 dark:ring-neutral-600/40 dark:focus:ring-neutral-500/50"
          />
        </label>
      </div>
      {windowError ? (
        <p className="mt-2 text-xs text-rose-700 dark:text-rose-400">{windowError}</p>
      ) : null}
      {d.isAbsoluteWindow ? (
        <p className="mt-2 text-xs text-slate-500 dark:text-neutral-400">
          Custom window active: {new Date(d.windowFromTimestamp).toLocaleString()} {" -> "}{" "}
          {new Date(d.windowToTimestamp).toLocaleString()}
        </p>
      ) : null}
      {d.serverNowTimestamp ? (
        <p className="mt-1 text-xs text-slate-500 dark:text-neutral-400">
          Server now: {new Date(d.serverNowTimestamp).toLocaleString()} ({formatRelativeToUserTime(d.serverNowTimestamp)})
        </p>
      ) : null}

      <div className="mt-3 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        <label className="xl:col-span-2 flex flex-col gap-1 text-xs font-medium text-slate-600 dark:text-neutral-300">
          Path contains
          <input
            key={`path-${d.pathQuery}`}
            ref={pathRef}
            type="search"
            defaultValue={d.pathQuery}
            placeholder="/orders, /health, ..."
            className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm shadow-sm outline-none ring-sky-500/30 focus:ring-2 dark:border-neutral-700 dark:bg-neutral-800 dark:text-neutral-100 dark:ring-neutral-600/40 dark:focus:ring-neutral-500/50"
          />
        </label>
        <label className="flex flex-col gap-1 text-xs font-medium text-slate-600 dark:text-neutral-300">
          Environment tags
          <input
            key={`env-${d.serverEnvironmentQuery}`}
            ref={envRef}
            type="text"
            defaultValue={d.serverEnvironmentQuery}
            placeholder="prod, staging"
            className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm shadow-sm outline-none ring-sky-500/30 focus:ring-2 dark:border-neutral-700 dark:bg-neutral-800 dark:text-neutral-100 dark:ring-neutral-600/40 dark:focus:ring-neutral-500/50"
          />
        </label>
        <label className="flex flex-col gap-1 text-xs font-medium text-slate-600 dark:text-neutral-300">
          Service tags
          <input
            key={`service-${d.serverServiceQuery}`}
            ref={serviceRef}
            type="text"
            defaultValue={d.serverServiceQuery}
            placeholder="api, worker"
            className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm shadow-sm outline-none ring-sky-500/30 focus:ring-2 dark:border-neutral-700 dark:bg-neutral-800 dark:text-neutral-100 dark:ring-neutral-600/40 dark:focus:ring-neutral-500/50"
          />
        </label>
        <label className="flex flex-col gap-1 text-xs font-medium text-slate-600 dark:text-neutral-300">
          Error groups sort
          <select
            key={`error-group-sort-${d.errorGroupSort}`}
            ref={errorGroupSortRef}
            defaultValue={d.errorGroupSort}
            className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm shadow-sm outline-none ring-sky-500/30 focus:ring-2 dark:border-neutral-700 dark:bg-neutral-800 dark:text-neutral-100 dark:ring-neutral-600/40 dark:focus:ring-neutral-500/50"
          >
            <option value="last_seen">Last seen</option>
            <option value="count">Count</option>
          </select>
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
