"use client";

type SettingsExcludeLumonoxTrafficSectionProps = {
  canEditRetention: boolean;
  excludeLumonoxTraffic: boolean;
  themeSettingsSaving: boolean;
  onToggleExclude: (next: boolean) => Promise<void>;
};

export function SettingsExcludeLumonoxTrafficSection({
  canEditRetention,
  excludeLumonoxTraffic,
  themeSettingsSaving,
  onToggleExclude,
}: SettingsExcludeLumonoxTrafficSectionProps) {
  return (
    <section className="rounded-2xl border-2 border-orange-400/50 bg-gradient-to-br from-orange-50 to-white p-5 shadow-md dark:border-orange-600/40 dark:from-orange-950/40 dark:to-neutral-900">
      <h2 className="text-lg font-bold tracking-tight text-slate-900 dark:text-neutral-50">
        Exclude Lumonox internal traffic
      </h2>
      {!canEditRetention ? (
        <p className="mt-2 text-sm text-slate-700 dark:text-neutral-200">
          Only organization owners and admins can change this setting.
        </p>
      ) : null}
      <p className="mt-2 text-sm font-medium text-slate-700 dark:text-neutral-200">
        Hides Lumonox’s own traffic (<code className="rounded bg-white/80 px-1 font-mono text-xs dark:bg-neutral-950/80">/lumonox/*</code>,{" "}
        <code className="rounded bg-white/80 px-1 font-mono text-xs dark:bg-neutral-950/80">/dashboard/*</code>,{" "}
        <code className="rounded bg-white/80 px-1 font-mono text-xs dark:bg-neutral-950/80">/ingest</code>) from analytics, logs, and alerts, so console noise doesn’t skew your app metrics.
      </p>
      <label className="mt-4 flex cursor-pointer items-start gap-3 rounded-lg border border-orange-200/80 bg-white/90 p-4 dark:border-orange-900/50 dark:bg-neutral-950/50">
        <input
          type="checkbox"
          className="mt-1 size-4 shrink-0 rounded border-slate-300 text-orange-600 focus:ring-orange-500 dark:border-neutral-600"
          checked={excludeLumonoxTraffic}
          disabled={!canEditRetention || themeSettingsSaving}
          onChange={async (event) => {
            await onToggleExclude(event.target.checked);
          }}
        />
        <span>
          <span className="text-base font-bold text-slate-900 dark:text-neutral-100">Hide internal Lumonox traffic</span>
          <span className="mt-1 block text-sm font-normal text-slate-600 dark:text-neutral-400">
            Recommended for production projects. Toggle off only when debugging the dashboard itself.
          </span>
        </span>
      </label>
    </section>
  );
}
