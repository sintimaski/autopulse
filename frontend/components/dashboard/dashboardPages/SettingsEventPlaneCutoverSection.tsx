"use client";

import { InlineDataSpinner } from "../../ui/InlineDataSpinner";

type SettingsEventPlaneCutoverSectionProps = {
  canManageEventPlaneCutover: boolean;
  eventPlaneCutoverLoadState: "idle" | "loading" | "ready" | "error";
  eventPlaneCutoverMessage: string | null;
  eventPlaneUseSnapshotRead: boolean;
  setEventPlaneUseSnapshotRead: (next: boolean) => void;
  eventPlaneCutoverSaving: boolean;
  onSaveCutover: () => Promise<void>;
};

export function SettingsEventPlaneCutoverSection({
  canManageEventPlaneCutover,
  eventPlaneCutoverLoadState,
  eventPlaneCutoverMessage,
  eventPlaneUseSnapshotRead,
  setEventPlaneUseSnapshotRead,
  eventPlaneCutoverSaving,
  onSaveCutover,
}: SettingsEventPlaneCutoverSectionProps) {
  return (
    <section className="rounded-2xl border border-slate-200/80 bg-white/95 p-5 shadow-sm dark:border-neutral-800 dark:bg-neutral-900">
      <h2 className="text-base font-semibold text-slate-800 dark:text-neutral-100">Event Plane read cutover</h2>
      <p className="mt-1 text-sm text-slate-500 dark:text-neutral-400">
        Per-project rollback switch for Plan B reads. When enabled, Overview, Requests, and related traffic queries read
        from the published event snapshot when available, so rows can look older than live ingests until the next
        snapshot. Host and dashboard widget time series still read from the live DuckDB writer path.
      </p>
      {!canManageEventPlaneCutover ? (
        <p className="mt-2 text-sm text-slate-600 dark:text-neutral-300">
          Only organization owners and admins can change cutover.
        </p>
      ) : eventPlaneCutoverLoadState === "loading" ? (
        <div className="mt-4">
          <InlineDataSpinner label="Loading cutover setting…" />
        </div>
      ) : eventPlaneCutoverLoadState === "error" ? (
        <p className="mt-2 text-sm text-rose-700 dark:text-rose-300">
          {eventPlaneCutoverMessage ?? "Could not load cutover setting."}
        </p>
      ) : (
        <>
          <label className="mt-4 flex cursor-pointer items-start gap-3 rounded-lg border border-slate-200/80 bg-slate-50/60 p-4 dark:border-neutral-700 dark:bg-neutral-800/60">
            <input
              type="checkbox"
              className="mt-1 size-4 shrink-0 rounded border-slate-300 text-sky-600 focus:ring-sky-500 dark:border-neutral-600"
              checked={eventPlaneUseSnapshotRead}
              disabled={eventPlaneCutoverSaving}
              onChange={(event) => setEventPlaneUseSnapshotRead(event.target.checked)}
            />
            <span>
              <span className="text-sm font-semibold text-slate-900 dark:text-neutral-100">
                Use snapshot read path for this project
              </span>
              <span className="mt-1 block text-xs text-slate-600 dark:text-neutral-400">
                Keep this off until parity checks and lag SLOs are healthy. Turn off immediately if diagnosis parity
                regresses.
              </span>
            </span>
          </label>
          <div className="mt-3 flex items-center gap-3">
            <button
              type="button"
              className="ap-btn-primary"
              disabled={eventPlaneCutoverSaving}
              onClick={() => void onSaveCutover()}
            >
              {eventPlaneCutoverSaving ? "Saving..." : "Save cutover setting"}
            </button>
            {eventPlaneCutoverMessage ? (
              <p className="text-sm text-slate-600 dark:text-neutral-300">{eventPlaneCutoverMessage}</p>
            ) : null}
          </div>
        </>
      )}
    </section>
  );
}
