"use client";

import { DASHBOARD_THEME_PREFERENCE_STORAGE_KEY } from "../../lib/dashboardThemeConstants";
import type { ThemePreference } from "./dashboardTypes";

export { DASHBOARD_THEME_PREFERENCE_STORAGE_KEY };

export function isThemePreference(value: unknown): value is ThemePreference {
  return value === "system" || value === "light" || value === "dark";
}

export function readStoredDashboardThemePreference(): ThemePreference | null {
  if (typeof window === "undefined") {
    return null;
  }
  try {
    const raw = window.localStorage.getItem(DASHBOARD_THEME_PREFERENCE_STORAGE_KEY);
    if (isThemePreference(raw)) {
      return raw;
    }
  } catch {
    /* ignore */
  }
  return null;
}

export function writeStoredDashboardThemePreference(preference: ThemePreference): void {
  if (typeof window === "undefined") {
    return;
  }
  try {
    window.localStorage.setItem(DASHBOARD_THEME_PREFERENCE_STORAGE_KEY, preference);
  } catch {
    /* ignore */
  }
}

/**
 * Whether dashboard chrome should render in dark mode before/without full bootstrap context.
 * Uses persisted preference when present; otherwise follows `prefers-color-scheme`.
 */
export function readDashboardChromeWantsDark(): boolean {
  if (typeof window === "undefined") {
    return false;
  }
  const stored = readStoredDashboardThemePreference();
  if (stored === "dark") {
    return true;
  }
  if (stored === "light") {
    return false;
  }
  try {
    return window.matchMedia("(prefers-color-scheme: dark)").matches;
  } catch {
    return false;
  }
}
