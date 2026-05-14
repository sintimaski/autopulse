"use client";

import { InlineDataSpinner } from "../../ui/InlineDataSpinner";
import type { RetentionSettings } from "../dashboardTypes";

type SettingsRetentionPolicySectionProps = {
  effectiveDraft: RetentionSettings | null;
  canEditRetention: boolean;
  dashboardLoading: boolean;
  dashboardErrorMessage: string | null;
  retentionMessage: string | null;
  onDraftChange: (next: RetentionSettings) => void;
  onSave: () => Promise<void> | void;
  /** Save request in flight: drives the button loader + blocks double-submit. */
  saving?: boolean;
};

export function SettingsRetentionPolicySection({
  effectiveDraft,
  canEditRetention,
  dashboardLoading,
  dashboardErrorMessage,
  retentionMessage,
  onDraftChange,
  onSave,
  saving = false,
}: SettingsRetentionPolicySectionProps) {
  return (
    <section className="rounded-2xl border border-slate-200/80 bg-white/95 p-5 shadow-sm dark:border-neutral-800 dark:bg-neutral-900">
      <h2 className="text-base font-semibold text-slate-800 dark:text-neutral-100">Retention policy</h2>
      {effectiveDraft ? (
        <>
          <p className="mt-1 text-sm text-slate-500 dark:text-neutral-400">
            Configure how long raw events are retained and the max query window for SQL logs.
          </p>
          {!canEditRetention ? (
            <p className="mt-2 text-sm text-slate-600 dark:text-neutral-300">
              Only organization owners and admins can change retention. You can still view the current policy.
            </p>
          ) : null}
          <div className="mt-4 grid gap-x-6 gap-y-4 sm:grid-cols-2">
            <label className="block min-w-0 max-w-md text-sm text-slate-700 dark:text-neutral-200">
              Raw events retention (days)
              <input
                type="number"
                min={1}
                disabled={!canEditRetention}
                value={effectiveDraft.raw_events_days}
                onChange={(event) =>
                  onDraftChange({
                    raw_events_days: Number(event.target.value),
                    logs_query_max_window_minutes: effectiveDraft.logs_query_max_window_minutes,
                    retention_max_db_size_mb: effectiveDraft.retention_max_db_size_mb,
                    retention_max_log_rows: effectiveDraft.retention_max_log_rows,
                    retention_plan: effectiveDraft.retention_plan,
                    archival_enabled: effectiveDraft.archival_enabled,
                    archival_mode: effectiveDraft.archival_mode,
                    archival_status: effectiveDraft.archival_status,
                    archival_last_success_at: effectiveDraft.archival_last_success_at,
                    archival_last_error: effectiveDraft.archival_last_error,
                  })
                }
                className="ap-input mt-1"
              />
            </label>
            <label className="block min-w-0 max-w-md text-sm text-slate-700 dark:text-neutral-200">
              Max SQL query window (minutes)
              <input
                type="number"
                min={1}
                disabled={!canEditRetention}
                value={effectiveDraft.logs_query_max_window_minutes}
                onChange={(event) =>
                  onDraftChange({
                    raw_events_days: effectiveDraft.raw_events_days,
                    logs_query_max_window_minutes: Number(event.target.value),
                    retention_max_db_size_mb: effectiveDraft.retention_max_db_size_mb,
                    retention_max_log_rows: effectiveDraft.retention_max_log_rows,
                    retention_plan: effectiveDraft.retention_plan,
                    archival_enabled: effectiveDraft.archival_enabled,
                    archival_mode: effectiveDraft.archival_mode,
                    archival_status: effectiveDraft.archival_status,
                    archival_last_success_at: effectiveDraft.archival_last_success_at,
                    archival_last_error: effectiveDraft.archival_last_error,
                  })
                }
                className="ap-input mt-1"
              />
            </label>
            <label className="block min-w-0 max-w-md text-sm text-slate-700 dark:text-neutral-200">
              Embedded logs max DB size (MB)
              <input
                type="number"
                min={1}
                disabled={!canEditRetention}
                value={effectiveDraft.retention_max_db_size_mb ?? ""}
                onChange={(event) =>
                  onDraftChange({
                    ...effectiveDraft,
                    retention_max_db_size_mb:
                      event.target.value.trim() === "" ? null : Number(event.target.value),
                  })
                }
                className="ap-input mt-1"
              />
            </label>
            <label className="block min-w-0 max-w-md text-sm text-slate-700 dark:text-neutral-200">
              Max logs retained (rows)
              <input
                type="number"
                min={1}
                disabled={!canEditRetention}
                value={effectiveDraft.retention_max_log_rows ?? ""}
                onChange={(event) =>
                  onDraftChange({
                    ...effectiveDraft,
                    retention_max_log_rows:
                      event.target.value.trim() === "" ? null : Number(event.target.value),
                  })
                }
                className="ap-input mt-1"
              />
            </label>
          </div>
          <div className="mt-4 flex flex-wrap items-end gap-6 border-t border-slate-200/80 pt-4 dark:border-neutral-800">
            <label className="block w-full max-w-xs text-sm text-slate-700 dark:text-neutral-200">
              Retention tier
              <span className="mt-0.5 block text-xs font-normal text-slate-500 dark:text-neutral-400">
                Preset rotation policy — not a billing plan. Starter also caps the ingest rate to stay within
                single-node budgets.
              </span>
              <select
                value={effectiveDraft.retention_plan}
                disabled={!canEditRetention}
                onChange={(event) =>
                  onDraftChange({
                    ...effectiveDraft,
                    retention_plan: event.target.value as RetentionSettings["retention_plan"],
                  })
                }
                className="ap-select mt-1 w-full"
              >
                <option value="starter">Starter</option>
                <option value="standard">Standard</option>
                <option value="extended">Extended</option>
              </select>
            </label>
            <label className="flex max-w-md flex-1 items-center gap-2 text-sm text-slate-700 dark:text-neutral-200">
              <input
                type="checkbox"
                disabled={!canEditRetention}
                checked={effectiveDraft.archival_enabled}
                onChange={(event) =>
                  onDraftChange({
                    ...effectiveDraft,
                    archival_enabled: event.target.checked,
                  })
                }
              />
              Archive expired events before delete
            </label>
          </div>
          <p className="mt-2 text-xs text-slate-500 dark:text-neutral-400">
            Optional rotation caps apply to the active log store (DuckDB or SQLite).
          </p>
          <p className="mt-1 text-xs text-slate-500 dark:text-neutral-400">
            Archive status: {effectiveDraft.archival_status}
            {effectiveDraft.archival_last_success_at
              ? ` · last success ${new Date(effectiveDraft.archival_last_success_at).toLocaleString()}`
              : ""}
            {effectiveDraft.archival_last_error ? ` · last error ${effectiveDraft.archival_last_error}` : ""}
          </p>
          <button
            type="button"
            disabled={!canEditRetention || saving}
            onClick={() => void onSave()}
            className="ap-btn-primary mt-3 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {saving ? "Saving…" : "Save retention policy"}
          </button>
          {retentionMessage ? (
            <p
              className="mt-2 text-sm text-slate-600 dark:text-neutral-300"
              role="status"
              aria-live="polite"
            >
              {retentionMessage}
            </p>
          ) : null}
        </>
      ) : dashboardLoading && !dashboardErrorMessage ? (
        <div className="mt-4">
          <InlineDataSpinner label="Loading retention settings…" />
        </div>
      ) : (
        <p className="mt-2 text-sm text-slate-500 dark:text-neutral-400">
          {dashboardErrorMessage ?? "Retention settings are not available."}
        </p>
      )}
    </section>
  );
}
