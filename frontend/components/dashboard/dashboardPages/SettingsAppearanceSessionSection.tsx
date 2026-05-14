"use client";

import { LogOut } from "../../../lib/icons";

import type { ThemePreference } from "../dashboardTypes";

type Props = {
  viewerSession: boolean;
  themeMessage: string | null;
  setThemeMessage: (message: string | null) => void;
  themePreference: ThemePreference;
  themeSettingsSaving: boolean;
  saveThemePreference: (theme: ThemePreference) => Promise<boolean>;
  signOutDashboard: () => Promise<void> | void;
  /** Sign-out request in flight: drives the button loader + blocks double-submit. */
  signingOut?: boolean;
};

export function SettingsAppearanceSessionSection({
  viewerSession,
  themeMessage,
  setThemeMessage,
  themePreference,
  themeSettingsSaving,
  saveThemePreference,
  signOutDashboard,
  signingOut = false,
}: Props) {
  return (
    <>
      <section className="rounded-2xl border border-slate-200/80 bg-white/95 p-5 shadow-sm dark:border-neutral-800 dark:bg-neutral-900">
        <h2 className="text-base font-semibold text-slate-800 dark:text-neutral-100">Appearance</h2>
        <p className="mt-1 text-sm text-slate-500 dark:text-neutral-400">
          Theme preference is now a project setting stored in the backend.
        </p>
        {viewerSession ? (
          <p className="mt-2 text-sm text-slate-600 dark:text-neutral-300">
            Viewer role: theme and traffic filters are read-only. Ask an owner or admin to change project appearance
            settings.
          </p>
        ) : null}
        <div className="mt-3 grid gap-3 sm:grid-cols-3" role="radiogroup" aria-label="Dashboard theme">
          {(["system", "light", "dark"] as const).map((theme) => (
            <button
              key={theme}
              type="button"
              role="radio"
              aria-checked={themePreference === theme}
              onClick={async () => {
                const ok = await saveThemePreference(theme);
                setThemeMessage(ok ? "Theme saved." : "Failed to save theme.");
              }}
              disabled={viewerSession || themeSettingsSaving}
              className={`rounded-xl border px-3 py-2 text-left text-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-orange-500/40 ${
                themePreference === theme
                  ? "border-orange-300 bg-orange-50 text-orange-900 dark:border-orange-800 dark:bg-orange-950/50 dark:text-orange-100"
                  : "border-slate-200 bg-white text-slate-700 dark:border-neutral-700 dark:bg-neutral-900 dark:text-neutral-200"
              }`}
            >
              {theme === "system" ? "System" : theme === "light" ? "Light" : "Dark"}
            </button>
          ))}
        </div>
        {themeMessage ? (
          <p
            className="mt-2 text-sm text-slate-600 dark:text-neutral-300"
            role="status"
            aria-live="polite"
          >
            {themeMessage}
          </p>
        ) : null}
      </section>

      <section className="rounded-2xl border border-slate-200/80 bg-white/95 p-5 shadow-sm dark:border-neutral-800 dark:bg-neutral-900">
        <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-neutral-400">Session</p>
        <h2 className="text-base font-semibold text-slate-800 dark:text-neutral-100">Dashboard sign-out</h2>
        <div className="mt-4">
          <button
            type="button"
            disabled={signingOut}
            className="ap-btn inline-flex items-center gap-2 px-3 py-2 text-sm font-medium disabled:cursor-not-allowed disabled:opacity-50"
            onClick={() => void signOutDashboard()}
          >
            <LogOut className="size-4 shrink-0" aria-hidden />
            {signingOut ? "Signing out…" : "Sign out"}
          </button>
        </div>
      </section>
    </>
  );
}
