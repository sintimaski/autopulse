/**
 * Persisted dashboard theme (`localStorage`). Used by the paint-blocking boot script
 * in `app/layout.tsx` and by `dashboardThemeStorage.ts` — keep a single definition.
 */
export const DASHBOARD_THEME_PREFERENCE_STORAGE_KEY = "autopulse.dashboard.themePreference.v1" as const;
