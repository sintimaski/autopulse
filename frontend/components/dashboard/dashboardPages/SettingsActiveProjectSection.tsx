"use client";

import { InlineDataSpinner } from "../../ui/InlineDataSpinner";

type ProjectRow = { id: string; label: string };

type SettingsActiveProjectSectionProps = {
  organizationsLoadState: "loading" | "ready" | "error";
  accessibleProjects: ProjectRow[];
  currentProjectLabel: string | null;
  sessionProjectId: string | null;
  activeProjectBusy: boolean;
  activeProjectMessage: string | null;
  onActiveProjectChange: (nextId: string) => void | Promise<void>;
  /** Retry affordance for a failed organizations/projects fetch. */
  onReloadProjects?: () => void;
};

export function SettingsActiveProjectSection({
  organizationsLoadState,
  accessibleProjects,
  currentProjectLabel,
  sessionProjectId,
  activeProjectBusy,
  activeProjectMessage,
  onActiveProjectChange,
  onReloadProjects = () => {},
}: SettingsActiveProjectSectionProps) {
  return (
    <section className="rounded-2xl border border-slate-200/80 bg-white/95 p-5 shadow-sm dark:border-neutral-800 dark:bg-neutral-900">
      <div className="flex flex-col gap-1 border-b border-slate-200/80 pb-4 dark:border-neutral-800">
        <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-neutral-400">
          Dashboard scope
        </p>
        <h2 className="text-base font-semibold text-slate-800 dark:text-neutral-100">Active project</h2>
        <p className="mt-1 max-w-2xl text-sm text-slate-600 dark:text-neutral-400">
          Charts and API keys follow the project bound to your signed-in session (not the organization picker below). If
          you see empty traffic while your app is sending events, your ingest key may belong to another project in the
          same organization—select the matching project here.
        </p>
      </div>
      <div className="mt-6">
        {organizationsLoadState === "loading" ? (
          <InlineDataSpinner label="Loading projects..." />
        ) : organizationsLoadState === "error" ? (
          <div className="flex flex-col items-start gap-3">
            <p className="text-sm text-rose-700 dark:text-rose-300" role="alert">
              Could not load projects for this account. Check your connection and dashboard API availability, then
              retry.
            </p>
            <button type="button" onClick={onReloadProjects} className="ap-btn">
              Retry
            </button>
          </div>
        ) : accessibleProjects.length === 0 ? (
          <p className="text-sm text-slate-600 dark:text-neutral-400">No projects found.</p>
        ) : accessibleProjects.length === 1 ? (
          <p className="text-sm text-slate-700 dark:text-neutral-200">
            <span className="font-medium text-slate-900 dark:text-neutral-100">Current project:</span>{" "}
            {currentProjectLabel ?? "-"}
          </p>
        ) : (
          <label className="block max-w-xl text-sm font-medium text-slate-700 dark:text-neutral-200">
            Project for dashboard queries
            <select
              className="ap-select mt-1.5 w-full"
              value={sessionProjectId ?? ""}
              disabled={activeProjectBusy}
              onChange={(event) => void onActiveProjectChange(event.target.value)}
            >
              {accessibleProjects.map((row) => (
                <option key={row.id} value={row.id}>
                  {row.label}
                </option>
              ))}
            </select>
          </label>
        )}
        {activeProjectMessage ? (
          <p
            className="mt-3 text-sm text-slate-600 dark:text-neutral-300"
            role="status"
            aria-live="polite"
          >
            {activeProjectMessage}
          </p>
        ) : null}
      </div>
    </section>
  );
}
