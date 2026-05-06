"use client";

import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type KeyboardEventHandler,
  type RefObject,
} from "react";

import {
  Ban,
  CalendarClock,
  Check,
  ChevronDown,
  FilterX,
  ListChecks,
  SlidersHorizontal,
  Undo2,
} from "../../lib/icons";
import { useDashboardData } from "./DashboardDataContext";
import type { SavedScopePresetSaveDraft } from "./dashboardDataContextTypes";
import { resetServerScope } from "./dashboardScopeReset";
import {
  formatRelativeToUserTime,
  formatWindowMinutes,
  isoToLocalInputValue,
  parseLocalDateTimeInput,
} from "./serverQueryToolbarUtils";
import { TagSelector } from "./TagSelector";

export type ServerScopeToolbarVariant = "diagnosis" | "logs" | "requests";

function gatherToolbarScopeSaveDraft(
  d: ReturnType<typeof useDashboardData>,
  refs: {
    fromInputRef: RefObject<HTMLInputElement | null>;
    toInputRef: RefObject<HTMLInputElement | null>;
    methodRef: RefObject<HTMLSelectElement | null>;
    statusClassRef: RefObject<HTMLSelectElement | null>;
    minLatencyRef: RefObject<HTMLInputElement | null>;
    maxLatencyRef: RefObject<HTMLInputElement | null>;
    pathRef: RefObject<HTMLInputElement | null>;
    errorGroupSortRef: RefObject<HTMLSelectElement | null>;
  },
  variant: ServerScopeToolbarVariant,
): SavedScopePresetSaveDraft {
  const draft: SavedScopePresetSaveDraft = {
    method: refs.methodRef.current?.value ?? d.method,
    statusClass: refs.statusClassRef.current?.value ?? d.statusClass,
    minLatencyMs: refs.minLatencyRef.current?.value ?? d.minLatencyMs,
    maxLatencyMs: refs.maxLatencyRef.current?.value ?? d.maxLatencyMs,
    pathQuery: refs.pathRef.current?.value ?? d.pathQuery,
    windowMinutes: d.windowMinutes,
  };
  if (variant === "diagnosis") {
    const eg = refs.errorGroupSortRef.current?.value;
    draft.errorGroupSort = eg === "count" || eg === "last_seen" ? eg : d.errorGroupSort;
  }
  const syncedFrom = isoToLocalInputValue(d.windowFromTimestamp);
  const syncedTo = isoToLocalInputValue(d.windowToTimestamp);
  const fromRaw = refs.fromInputRef.current?.value ?? "";
  const toRaw = refs.toInputRef.current?.value ?? "";
  const inputsChanged =
    d.isAbsoluteWindow ||
    (fromRaw.length > 0 && toRaw.length > 0 && (fromRaw !== syncedFrom || toRaw !== syncedTo));
  if (inputsChanged) {
    const fd = parseLocalDateTimeInput(fromRaw);
    const td = parseLocalDateTimeInput(toRaw);
    if (fd && td && fd.getTime() < td.getTime()) {
      draft.isAbsoluteWindow = true;
      draft.windowFromTimestamp = fd.toISOString();
      draft.windowToTimestamp = td.toISOString();
    }
  }
  return draft;
}

export function ServerQueryToolbar({ variant }: { variant: ServerScopeToolbarVariant }) {
  const d = useDashboardData();
  const advancedQueryUiEnabled = process.env.NEXT_PUBLIC_AUTOPULSE_ADVANCED_QUERY_UI === "1";
  const scopeTitle =
    variant === "diagnosis" ? "Diagnosis scope" : "Requests scope";
  const selectedEnvironmentTags = useMemo(
    () => new Set(d.serverEnvironmentTags),
    [d.serverEnvironmentTags],
  );
  const selectedServiceTags = useMemo(() => new Set(d.serverServiceTags), [d.serverServiceTags]);
  const environmentOptions = useMemo(
    () => [...new Set([...d.availableEnvironments, ...d.serverEnvironmentTags])].sort(),
    [d.availableEnvironments, d.serverEnvironmentTags],
  );
  const serviceOptions = useMemo(
    () => [...new Set([...d.availableServices, ...d.serverServiceTags])].sort(),
    [d.availableServices, d.serverServiceTags],
  );
  const sqlScopeActive = d.sqlFilterEnabled && d.sqlFilterApplied.trim() !== "";
  const activeServerFilterCount = [
    d.method !== "ALL",
    d.statusClass !== "ALL",
    d.pathQuery.trim() !== "",
    d.minLatencyMs.trim() !== "",
    d.maxLatencyMs.trim() !== "",
    d.serverEnvironmentTags.length > 0,
    d.serverServiceTags.length > 0,
    advancedQueryUiEnabled && sqlScopeActive,
  ].filter(Boolean).length;
  const fromInputRef = useRef<HTMLInputElement>(null);
  const toInputRef = useRef<HTMLInputElement>(null);
  const methodRef = useRef<HTMLSelectElement>(null);
  const statusClassRef = useRef<HTMLSelectElement>(null);
  const minLatencyRef = useRef<HTMLInputElement>(null);
  const maxLatencyRef = useRef<HTMLInputElement>(null);
  const pathRef = useRef<HTMLInputElement>(null);
  const errorGroupSortRef = useRef<HTMLSelectElement>(null);
  const [windowError, setWindowError] = useState<string | null>(null);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [scopePresetNameDraft, setScopePresetNameDraft] = useState("");
  const [scopePresetFeedback, setScopePresetFeedback] = useState<string | null>(null);
  const [selectedScopePresetId, setSelectedScopePresetId] = useState("");
  const [presetNameDraft, setPresetNameDraft] = useState("");
  const [presetFeedback, setPresetFeedback] = useState<string | null>(null);
  const [selectedPresetId, setSelectedPresetId] = useState("");

  /** Rolling-window API timestamps change on every refresh; keys must not, or inputs remount and layout jumps while scrolled. */
  const dateTimeFieldResetKey = useMemo(
    () =>
      d.isAbsoluteWindow
        ? `abs:${d.windowFromTimestamp}|${d.windowToTimestamp}`
        : `roll:${d.windowMinutes}`,
    [d.isAbsoluteWindow, d.windowFromTimestamp, d.windowToTimestamp, d.windowMinutes],
  );

  useEffect(() => {
    const from = fromInputRef.current;
    const to = toInputRef.current;
    if (!from || !to) {
      return;
    }
    const nextFrom = isoToLocalInputValue(d.windowFromTimestamp);
    const nextTo = isoToLocalInputValue(d.windowToTimestamp);
    if (document.activeElement !== from && from.value !== nextFrom) {
      from.value = nextFrom;
    }
    if (document.activeElement !== to && to.value !== nextTo) {
      to.value = nextTo;
    }
  }, [d.windowFromTimestamp, d.windowToTimestamp]);

  /** Keep uncontrolled fields aligned when scope changes from URL, saved views, or other pages — avoids Apply overwriting with stale ref values. */
  useEffect(() => {
    const m = methodRef.current;
    if (m && m.value !== d.method) {
      m.value = d.method;
    }
    const s = statusClassRef.current;
    if (s && s.value !== d.statusClass) {
      s.value = d.statusClass;
    }
    const minEl = minLatencyRef.current;
    if (minEl && minEl.value !== d.minLatencyMs) {
      minEl.value = d.minLatencyMs;
    }
    const maxEl = maxLatencyRef.current;
    if (maxEl && maxEl.value !== d.maxLatencyMs) {
      maxEl.value = d.maxLatencyMs;
    }
    const p = pathRef.current;
    if (p && p.value !== d.pathQuery && document.activeElement !== p) {
      p.value = d.pathQuery;
    }
    const eg = errorGroupSortRef.current;
    if (eg && eg.value !== d.errorGroupSort) {
      eg.value = d.errorGroupSort;
    }
  }, [d.method, d.statusClass, d.minLatencyMs, d.maxLatencyMs, d.pathQuery, d.errorGroupSort]);

  const resetServerFilters = () => {
    resetServerScope(
      {
        onServerMethodChange: d.onServerMethodChange,
        onServerStatusClassChange: d.onServerStatusClassChange,
        setPathQuery: d.setPathQuery,
        setMinLatencyMs: d.setMinLatencyMs,
        setMaxLatencyMs: d.setMaxLatencyMs,
        setServerEnvironmentTags: d.setServerEnvironmentTags,
        setServerServiceTags: d.setServerServiceTags,
        setRequestLimit: d.setRequestLimit,
        setRequestPage: d.setRequestPage,
        setErrorGroupLimit: d.setErrorGroupLimit,
        setErrorGroupPage: d.setErrorGroupPage,
        setErrorGroupSort: d.setErrorGroupSort,
        setSqlFilterDraft: d.setSqlFilterDraft,
        setSqlFilterApplied: d.setSqlFilterApplied,
        setSqlFilterEnabled: d.setSqlFilterEnabled,
      },
      variant,
    );
    if (methodRef.current) methodRef.current.value = "ALL";
    if (statusClassRef.current) statusClassRef.current.value = "ALL";
    if (minLatencyRef.current) minLatencyRef.current.value = "";
    if (maxLatencyRef.current) maxLatencyRef.current.value = "";
    if (pathRef.current) pathRef.current.value = "";
    if (variant === "diagnosis") {
      d.setErrorGroupSort("last_seen");
      d.setRequestPage(0);
      d.setErrorGroupPage(0);
      if (errorGroupSortRef.current) errorGroupSortRef.current.value = "last_seen";
    } else {
      d.setRequestLimit(100);
      d.setRequestPage(0);
    }
  };
  const applyFilters = () => {
    const currentScrollY = window.scrollY;
    d.onServerMethodChange(methodRef.current?.value ?? "ALL");
    d.onServerStatusClassChange(statusClassRef.current?.value ?? "ALL");
    d.setMinLatencyMs(minLatencyRef.current?.value ?? "");
    d.setMaxLatencyMs(maxLatencyRef.current?.value ?? "");
    d.setPathQuery(pathRef.current?.value ?? "");
    if (variant === "diagnosis") {
      d.setErrorGroupSort((errorGroupSortRef.current?.value as "last_seen" | "count") ?? "last_seen");
      d.setRequestPage(0);
      d.setErrorGroupPage(0);
    } else {
      d.setRequestPage(0);
    }
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
    if (tag === "BUTTON" || tag === "TEXTAREA" || tag === "SELECT") {
      return;
    }
    event.preventDefault();
    applyFilters();
  };

  return (
    <div
      className="rounded-xl border border-slate-200 bg-slate-50/80 p-2 dark:border-neutral-700 dark:bg-neutral-900/80"
      onKeyDown={onToolbarKeyDown}
    >
      <div className="mb-1.5 flex flex-wrap items-center justify-between gap-2">
        <div className="flex min-w-0 flex-1 flex-col gap-0">
          <div className="flex flex-wrap items-center gap-2">
            <SlidersHorizontal className="size-4 shrink-0 text-slate-500 dark:text-neutral-400" aria-hidden />
            <p className="text-sm font-semibold text-slate-700 dark:text-neutral-200">{scopeTitle}</p>
            <span className="rounded-full bg-slate-200 px-2 py-0.5 text-xs font-medium text-slate-700 dark:bg-neutral-800 dark:text-neutral-300">
              {activeServerFilterCount} active
            </span>
          </div>
          <p className="text-[11px] leading-tight text-slate-500 dark:text-neutral-400">
            {variant === "diagnosis"
              ? "Applies to grouped errors, diagnosis timeline, and the loaded request slice."
              : variant === "requests"
                ? "Applies to the request evidence explorer and related drill-down panels."
              : "Applies to the request evidence table and server-backed query results."}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={resetServerFilters}
            title="Reset filters"
            aria-label="Reset filters"
            className="ap-btn p-2"
          >
            <FilterX className="size-4" aria-hidden />
          </button>
          <button
            type="button"
            onClick={applyFilters}
            title="Apply filters"
            aria-label="Apply filters"
            className="ap-btn-primary p-2"
          >
            <Check className="size-4" aria-hidden />
          </button>
        </div>
      </div>
      <details className="group mb-2 rounded-lg border border-slate-200 bg-white/90 dark:border-neutral-700 dark:bg-neutral-950/40">
        <summary className="flex cursor-pointer list-none items-center justify-between gap-2 px-2 py-2 text-xs font-medium text-slate-700 dark:text-neutral-200 [&::-webkit-details-marker]:hidden">
          <span className="flex min-w-0 items-center gap-2">
            <ChevronDown
              className="size-3.5 shrink-0 text-slate-500 transition-transform group-open:rotate-180 dark:text-neutral-400"
              aria-hidden
            />
            <span>
              Saved views{d.savedScopePresets.length > 0 ? ` (${d.savedScopePresets.length})` : ""}
            </span>
          </span>
        </summary>
        <div className="border-t border-slate-200 p-2 dark:border-neutral-700">
          <div className="flex flex-wrap items-center gap-2">
            <input
              value={scopePresetNameDraft}
              onChange={(event) => setScopePresetNameDraft(event.target.value)}
              placeholder="Saved view name (e.g. Prod 5xx spikes)"
              className="min-w-[200px] flex-1 rounded-lg border border-neutral-700 bg-neutral-950 px-2.5 py-1.5 text-xs text-neutral-100 shadow-sm outline-none ring-sky-500/25 focus:ring-2"
            />
            <button
              type="button"
              onClick={() => {
                const draft = gatherToolbarScopeSaveDraft(
                  d,
                  {
                    fromInputRef,
                    toInputRef,
                    methodRef,
                    statusClassRef,
                    minLatencyRef,
                    maxLatencyRef,
                    pathRef,
                    errorGroupSortRef,
                  },
                  variant,
                );
                const saved = d.saveScopePreset(scopePresetNameDraft, draft);
                if (!saved.ok) {
                  setScopePresetFeedback(saved.error ?? "Unable to save view.");
                  return;
                }
                setScopePresetNameDraft("");
                setScopePresetFeedback("Saved view stored.");
              }}
              className="ap-btn px-2.5 py-1.5 text-xs"
            >
              Save view
            </button>
          </div>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <select
              value={selectedScopePresetId}
              onChange={(event) => setSelectedScopePresetId(event.target.value)}
              className="min-w-[240px] flex-1 rounded-lg border border-neutral-700 bg-neutral-950 px-2.5 py-1.5 text-xs text-neutral-100 shadow-sm outline-none ring-sky-500/25 focus:ring-2"
            >
              <option value="">Choose a saved view…</option>
              {d.savedScopePresets.map((preset) => (
                <option key={preset.id} value={preset.id}>
                  {preset.name}
                </option>
              ))}
            </select>
            <button
              type="button"
              disabled={!selectedScopePresetId}
              onClick={() => {
                const applied = d.applySavedScopePreset(selectedScopePresetId);
                if (!applied.ok) {
                  setScopePresetFeedback(applied.error ?? "Unable to apply saved view.");
                  return;
                }
                setScopePresetFeedback("Saved view applied.");
              }}
              className="ap-btn-primary px-2.5 py-1.5 text-xs"
            >
              Apply view
            </button>
            <button
              type="button"
              disabled={!selectedScopePresetId}
              onClick={() => {
                d.removeScopePreset(selectedScopePresetId);
                setSelectedScopePresetId("");
                setScopePresetFeedback("Saved view removed.");
              }}
              className="ap-btn px-2.5 py-1.5 text-xs"
            >
              Remove
            </button>
          </div>
          <p className="mt-2 text-[11px] text-slate-500 dark:text-neutral-400">
            Saved views are scoped to your active project and signed-in user.
          </p>
          {scopePresetFeedback ? (
            <p className="mt-1 text-xs text-sky-700 dark:text-sky-300">{scopePresetFeedback}</p>
          ) : null}
        </div>
      </details>

      <div className="grid gap-2 md:grid-cols-2 lg:grid-cols-4 xl:grid-cols-8">
        <label className="flex flex-col gap-0.5 text-xs font-medium text-slate-600 dark:text-neutral-300">
          Quick range
          <select
            value={d.windowMinutes}
            onChange={(e) => {
              const next = Number(e.target.value);
              if (!Number.isFinite(next)) {
                return;
              }
              d.onServerWindowChange(next);
              queueMicrotask(() => {
                e.currentTarget.blur();
              });
            }}
            className="ap-select"
          >
            {d.WINDOW_OPTIONS.map((minutes) => (
              <option key={minutes} value={minutes}>
                Last {formatWindowMinutes(minutes)}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-0.5 text-xs font-medium text-slate-600 dark:text-neutral-300">
          From
          <input
            key={`from-${dateTimeFieldResetKey}`}
            ref={fromInputRef}
            type="datetime-local"
            defaultValue={isoToLocalInputValue(d.windowFromTimestamp)}
            className="ap-input"
          />
        </label>
        <label className="flex flex-col gap-0.5 text-xs font-medium text-slate-600 dark:text-neutral-300">
          To
          <input
            key={`to-${dateTimeFieldResetKey}`}
            ref={toInputRef}
            type="datetime-local"
            defaultValue={isoToLocalInputValue(d.windowToTimestamp)}
            className="ap-input"
          />
        </label>
        <div className="flex items-end gap-2 lg:col-span-1 xl:col-span-1">
          {d.isAbsoluteWindow ? (
            <button
              type="button"
              onClick={d.clearAbsoluteWindow}
              title={`Drop custom window and use last ${d.windowMinutes} minutes`}
              aria-label={`Drop custom window and use last ${d.windowMinutes} minutes`}
              className="ap-btn flex max-w-full min-w-0 items-center gap-1.5 px-2 py-1.5 text-xs"
            >
              <Undo2 className="size-4 shrink-0" aria-hidden />
              <span className="min-w-0 truncate">Last {d.windowMinutes}m</span>
            </button>
          ) : (
            <button
              type="button"
              onClick={applyAbsoluteWindow}
              title="Apply custom time window"
              aria-label="Apply custom time window"
              className="ap-btn p-2"
            >
              <CalendarClock className="size-4" aria-hidden />
            </button>
          )}
        </div>
        <label className="flex flex-col gap-0.5 text-xs font-medium text-slate-600 dark:text-neutral-300">
          Method
          <select
            key={`method-${d.method}`}
            ref={methodRef}
            defaultValue={d.method}
            className="ap-select"
          >
            {d.METHOD_OPTIONS.map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-0.5 text-xs font-medium text-slate-600 dark:text-neutral-300">
          Status class
          <select
            key={`status-${d.statusClass}`}
            ref={statusClassRef}
            defaultValue={d.statusClass}
            className="ap-select"
          >
            {d.STATUS_CLASS_OPTIONS.map((value) => (
              <option key={value} value={value}>
                {value === "ALL" ? value : `${value}xx`}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-0.5 text-xs font-medium text-slate-600 dark:text-neutral-300">
          Min latency (ms)
          <input
            key={`min-${d.minLatencyMs}`}
            ref={minLatencyRef}
            type="number"
            min={0}
            step="1"
            defaultValue={d.minLatencyMs}
            placeholder="0"
            className="ap-input"
          />
        </label>
        <label className="flex flex-col gap-0.5 text-xs font-medium text-slate-600 dark:text-neutral-300">
          Max latency (ms)
          <input
            key={`max-${d.maxLatencyMs}`}
            ref={maxLatencyRef}
            type="number"
            min={0}
            step="1"
            defaultValue={d.maxLatencyMs}
            placeholder="5000"
            className="ap-input"
          />
        </label>
      </div>
      {windowError ? (
        <p className="mt-2 text-xs text-rose-700 dark:text-rose-400">{windowError}</p>
      ) : null}
      {d.isAbsoluteWindow ? (
        <p className="mt-2 text-sm text-slate-500 dark:text-neutral-400">
          Custom window active: {new Date(d.windowFromTimestamp).toLocaleString()} {" -> "}{" "}
          {new Date(d.windowToTimestamp).toLocaleString()}
        </p>
      ) : null}
      {d.serverNowTimestamp ? (
        <p className="mt-1 text-sm text-slate-500 dark:text-neutral-400">
          Server now: {new Date(d.serverNowTimestamp).toLocaleString()} ({formatRelativeToUserTime(d.serverNowTimestamp)})
        </p>
      ) : null}

      <div className="mt-2 grid gap-2 md:grid-cols-2 lg:grid-cols-4 xl:grid-cols-8">
        <label className="md:col-span-2 lg:col-span-2 xl:col-span-4 flex flex-col gap-0.5 text-xs font-medium text-slate-600 dark:text-neutral-300">
          Path contains
          <input
            key={`path-${d.pathQuery}`}
            ref={pathRef}
            type="search"
            defaultValue={d.pathQuery}
            placeholder="/orders, /health, ..."
            className="ap-input"
          />
        </label>
        {variant === "diagnosis" ? (
          <label className="flex flex-col gap-0.5 text-xs font-medium text-slate-600 dark:text-neutral-300">
            Grouped errors sort
            <select
              key={`error-group-sort-${d.errorGroupSort}`}
              ref={errorGroupSortRef}
              defaultValue={d.errorGroupSort}
              className="ap-select"
            >
              <option value="last_seen">Last seen</option>
              <option value="count">Count</option>
            </select>
          </label>
        ) : (
          <label className="flex flex-col gap-0.5 text-xs font-medium text-slate-600 dark:text-neutral-300">
            Request rows per page
            <select
              value={d.requestLimit}
              onChange={(e) => {
                d.setRequestLimit(Number(e.target.value));
                d.setRequestPage(0);
              }}
              className="ap-select"
            >
              {d.REQUEST_LIMIT_OPTIONS.map((value) => (
                <option key={value} value={value}>
                  {value} / page
                </option>
              ))}
            </select>
          </label>
        )}
        {variant === "diagnosis" ? (
          <label className="flex flex-col gap-0.5 text-xs font-medium text-slate-600 dark:text-neutral-300">
            Grouped errors per page
            <select
              value={d.errorGroupLimit}
              onChange={(e) => {
                d.setErrorGroupLimit(Number(e.target.value));
                d.setErrorGroupPage(0);
              }}
              className="rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-sm shadow-sm outline-none ring-sky-500/30 focus:ring-2 dark:border-neutral-700 dark:bg-neutral-800 dark:text-neutral-100 dark:ring-neutral-600/40 dark:focus:ring-neutral-500/50"
            >
              {d.ERROR_GROUP_LIMIT_OPTIONS.map((value) => (
                <option key={value} value={value}>
                  {value} / page
                </option>
              ))}
            </select>
          </label>
        ) : null}
      </div>

      <div className="mt-3 grid gap-3 xl:grid-cols-2">
        <TagSelector
          id="server-environment-tags"
          label="Environment tags"
          options={environmentOptions}
          selected={selectedEnvironmentTags}
          onToggle={(value) => {
            const next = new Set(selectedEnvironmentTags);
            if (next.has(value)) {
              next.delete(value);
            } else {
              next.add(value);
            }
            d.setServerEnvironmentTags([...next]);
          }}
          emptyText="No environment tags available for this loaded slice."
          helperText="Use these options to scope server-side fetches."
          accent="sky"
        />
        <TagSelector
          id="server-service-tags"
          label="Service tags"
          options={serviceOptions}
          selected={selectedServiceTags}
          onToggle={(value) => {
            const next = new Set(selectedServiceTags);
            if (next.has(value)) {
              next.delete(value);
            } else {
              next.add(value);
            }
            d.setServerServiceTags([...next]);
          }}
          emptyText="No service tags available for this loaded slice."
          helperText="Selections persist in the URL for shareable scope."
          accent="violet"
        />
      </div>

      {advancedQueryUiEnabled ? (
        <div className="mt-2.5 rounded-lg border border-slate-200 bg-white/90 p-2 dark:border-neutral-700 dark:bg-neutral-950/40">
          <div className="mb-1.5 flex flex-wrap items-center justify-between gap-2">
            <button
              type="button"
              onClick={() => setShowAdvanced((prev) => !prev)}
              className="ap-btn px-2 py-1 text-xs"
            >
              {showAdvanced ? "Hide advanced" : "Show advanced"}
            </button>
            <span className="text-xs text-slate-500 dark:text-neutral-400">SQL WHERE filter controls</span>
          </div>
          {showAdvanced ? (
            <>
              <textarea
                value={d.sqlFilterDraft}
                onChange={(event) => d.setSqlFilterDraft(event.target.value)}
                placeholder="e.g. status_code >= 500 AND method = 'GET'"
                className="h-16 w-full rounded-lg border border-neutral-700 bg-neutral-950 px-3 py-2 text-xs font-mono text-neutral-100 shadow-sm outline-none ring-sky-500/25 focus:ring-2"
              />
              <div className="mt-2 rounded-lg border border-slate-200 bg-slate-50/80 p-2 dark:border-neutral-700 dark:bg-neutral-900/60">
                <div className="flex flex-wrap items-center gap-2">
                  <input
                    value={presetNameDraft}
                    onChange={(event) => setPresetNameDraft(event.target.value)}
                    placeholder="Preset name (e.g. Critical 5xx routes)"
                    className="min-w-[190px] flex-1 rounded-lg border border-neutral-700 bg-neutral-950 px-2.5 py-1.5 text-xs text-neutral-100 shadow-sm outline-none ring-sky-500/25 focus:ring-2"
                  />
                  <button
                    type="button"
                    onClick={() => {
                      const saved = d.saveSqlFilterPreset(presetNameDraft, d.sqlFilterDraft);
                      if (!saved.ok) {
                        setPresetFeedback(saved.error ?? "Unable to save preset.");
                        return;
                      }
                      setPresetNameDraft("");
                      setPresetFeedback("Preset saved.");
                    }}
                    className="ap-btn px-2.5 py-1.5 text-xs"
                  >
                    Save preset
                  </button>
                </div>
                <div className="mt-2 flex flex-wrap items-center gap-2">
                  <select
                    value={selectedPresetId}
                    onChange={(event) => setSelectedPresetId(event.target.value)}
                    className="min-w-[230px] flex-1 rounded-lg border border-neutral-700 bg-neutral-950 px-2.5 py-1.5 text-xs text-neutral-100 shadow-sm outline-none ring-sky-500/25 focus:ring-2"
                  >
                    <option value="">Saved presets ({d.savedSqlFilterPresets.length})</option>
                    {d.savedSqlFilterPresets.map((preset) => (
                      <option key={preset.id} value={preset.id}>
                        {preset.name}
                      </option>
                    ))}
                  </select>
                  <button
                    type="button"
                    disabled={!selectedPresetId}
                    onClick={() => {
                      d.applySavedSqlFilterPreset(selectedPresetId);
                      setPresetFeedback("Preset applied.");
                    }}
                    className="ap-btn-primary px-2.5 py-1.5 text-xs"
                  >
                    Apply preset
                  </button>
                  <button
                    type="button"
                    disabled={!selectedPresetId}
                    onClick={() => {
                      d.removeSqlFilterPreset(selectedPresetId);
                      setSelectedPresetId("");
                      setPresetFeedback("Preset removed.");
                    }}
                    className="ap-btn px-2.5 py-1.5 text-xs"
                  >
                    Remove
                  </button>
                </div>
                <p className="mt-2 text-[11px] text-slate-500 dark:text-neutral-400">
                  Presets are stored per signed-in user ({d.sessionEmail ?? "anonymous"}).
                </p>
                {presetFeedback ? (
                  <p className="mt-1 text-xs text-sky-700 dark:text-sky-300">{presetFeedback}</p>
                ) : null}
              </div>
              <div className="mt-2 flex flex-wrap items-center gap-2">
                <button
                  type="button"
                  disabled={d.sqlFilterValidating}
                  onClick={() => void d.validateSqlFilterDraft()}
                  title="Validate SQL filter"
                  aria-label="Validate SQL filter"
                  className="ap-btn p-1.5"
                >
                  <ListChecks className="size-3.5" aria-hidden />
                </button>
                <button
                  type="button"
                  disabled={d.sqlFilterValidating}
                  onClick={() => void d.applySqlFilter()}
                  title="Apply SQL filter to scope"
                  aria-label="Apply SQL filter to scope"
                  className="ap-btn-primary p-1.5"
                >
                  <Check className="size-3.5" aria-hidden />
                </button>
                <button
                  type="button"
                  onClick={() => d.disableSqlFilter()}
                  disabled={!d.sqlFilterEnabled}
                  title="Disable SQL filter"
                  aria-label="Disable SQL filter"
                  className="ap-btn p-1.5"
                >
                  <Ban className="size-3.5" aria-hidden />
                </button>
                {d.sqlFilterValidation ? (
                  <span
                    className={`text-xs ${d.sqlFilterValidation.valid ? "text-emerald-700 dark:text-emerald-300" : "text-rose-700 dark:text-rose-300"}`}
                  >
                    {d.sqlFilterValidation.valid ? "Valid WHERE" : d.sqlFilterValidation.error ?? "Invalid"}
                  </span>
                ) : null}
              </div>
            </>
          ) : (
            <p className="text-xs text-slate-500 dark:text-neutral-400">
              Keep this hidden for quick triage. Expand when you need precise SQL-level scoping.
            </p>
          )}
          {d.sqlFilterEnabled ? (
            <p className="mt-2 text-xs font-medium text-sky-800 dark:text-sky-200">SQL filter enabled for current scope.</p>
          ) : null}
        </div>
      ) : (
        <div className="mt-2.5 rounded-lg border border-slate-200 bg-white/90 p-2 text-xs text-slate-500 dark:border-neutral-700 dark:bg-neutral-950/40 dark:text-neutral-400">
          Advanced SQL scope controls are disabled by default to keep the MVP focused on fast diagnosis.
        </div>
      )}
    </div>
  );
}
