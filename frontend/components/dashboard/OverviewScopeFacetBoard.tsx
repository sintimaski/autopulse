"use client";

import { useCallback, useMemo, useState } from "react";

import { useDashboardData } from "./DashboardDataContext";
import { TagSelector } from "./TagSelector";
import { METHOD_OPTIONS, STATUS_CLASS_OPTIONS } from "./dashboardTypes";

const selectClass =
  "mt-1 w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm outline-none ring-sky-500/30 focus:ring-2 dark:border-neutral-700 dark:bg-neutral-800 dark:text-neutral-100 dark:ring-neutral-600/40 dark:focus:ring-neutral-500/50";

const labelClass = "flex flex-col gap-0.5 text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-neutral-400";

export function OverviewScopeFacetBoard() {
  const d = useDashboardData();
  const [dirty, setDirty] = useState(false);
  const [draftMethod, setDraftMethod] = useState(d.method);
  const [draftStatusClass, setDraftStatusClass] = useState(d.statusClass);
  const [draftEnvTags, setDraftEnvTags] = useState(() => new Set(d.serverEnvironmentTags));
  const [draftServiceTags, setDraftServiceTags] = useState(() => new Set(d.serverServiceTags));

  const environmentOptions = useMemo(
    () => [...new Set([...d.availableEnvironments, ...d.serverEnvironmentTags])].sort(),
    [d.availableEnvironments, d.serverEnvironmentTags],
  );
  const serviceOptions = useMemo(
    () => [...new Set([...d.availableServices, ...d.serverServiceTags])].sort(),
    [d.availableServices, d.serverServiceTags],
  );

  const applyScope = useCallback(() => {
    d.onServerMethodChange(draftMethod);
    d.onServerStatusClassChange(draftStatusClass);
    d.setServerEnvironmentTags([...draftEnvTags]);
    d.setServerServiceTags([...draftServiceTags]);
    d.setRequestPage(0);
    d.setErrorGroupPage(0);
    setDirty(false);
  }, [
    d,
    draftMethod,
    draftStatusClass,
    draftEnvTags,
    draftServiceTags,
  ]);

  const resetDraft = useCallback(() => {
    setDraftMethod(d.method);
    setDraftStatusClass(d.statusClass);
    setDraftEnvTags(new Set(d.serverEnvironmentTags));
    setDraftServiceTags(new Set(d.serverServiceTags));
    setDirty(false);
  }, [d.method, d.statusClass, d.serverEnvironmentTags, d.serverServiceTags]);

  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-2">
        <label className={labelClass}>
          Method
          <select
            value={draftMethod}
            onChange={(e) => {
              setDraftMethod(e.target.value);
              setDirty(true);
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
        <label className={labelClass}>
          Status
          <select
            value={draftStatusClass}
            onChange={(e) => {
              setDraftStatusClass(e.target.value);
              setDirty(true);
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
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <TagSelector
          id="overview-env"
          label="Environment"
          options={environmentOptions}
          selected={draftEnvTags}
          onToggle={(value) => {
            setDraftEnvTags((prev) => {
              const next = new Set(prev);
              if (next.has(value)) {
                next.delete(value);
              } else {
                next.add(value);
              }
              return next;
            });
            setDirty(true);
          }}
          emptyText="No environment values in the current sample yet."
          helperText="Choose one or more; leave none for all."
          accent="sky"
        />
        <TagSelector
          id="overview-service"
          label="Service"
          options={serviceOptions}
          selected={draftServiceTags}
          onToggle={(value) => {
            setDraftServiceTags((prev) => {
              const next = new Set(prev);
              if (next.has(value)) {
                next.delete(value);
              } else {
                next.add(value);
              }
              return next;
            });
            setDirty(true);
          }}
          emptyText="No service names in the current sample yet."
          helperText="Choose one or more; leave none for all."
          accent="violet"
        />
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3 border-t border-slate-200/80 pt-3 dark:border-neutral-700">
        <p className="text-xs text-slate-500 dark:text-neutral-400">
          {dirty ? (
            <span className="font-medium text-amber-700 dark:text-amber-300">
              Unsaved changes — apply to refresh data.
            </span>
          ) : (
            <span>In sync with live scope</span>
          )}
        </p>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={resetDraft}
            className="rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 transition-colors hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500/40 dark:border-neutral-700 dark:bg-neutral-800 dark:text-neutral-200 dark:hover:bg-neutral-700 dark:focus-visible:ring-neutral-500/50"
          >
            Reset
          </button>
          <button
            type="button"
            onClick={applyScope}
            disabled={!dirty}
            className="rounded-lg border border-sky-300 bg-sky-50 px-3 py-1.5 text-sm font-medium text-sky-900 transition-colors hover:bg-sky-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500/40 disabled:cursor-not-allowed disabled:opacity-50 dark:border-sky-800 dark:bg-sky-950/50 dark:text-sky-100 dark:hover:bg-sky-900/40 dark:focus-visible:ring-neutral-500/50"
          >
            Apply scope
          </button>
        </div>
      </div>
    </div>
  );
}
