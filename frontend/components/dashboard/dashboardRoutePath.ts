/** Matches `basePath` in `frontend/next.config.ts`. */
export const DASHBOARD_UI_BASE_PATH = "/autopulse/ui";

/**
 * Normalize Next.js pathname (includes `basePath`) to the logical dashboard route
 * (`/dashboard`, `/settings`, …) used for data-fetch gating.
 */
export function toDashboardRoutePath(pathname: string): string {
  let normalized = pathname;
  if (normalized === DASHBOARD_UI_BASE_PATH) {
    normalized = "/";
  } else if (normalized.startsWith(`${DASHBOARD_UI_BASE_PATH}/`)) {
    normalized = normalized.slice(DASHBOARD_UI_BASE_PATH.length);
  }
  if (normalized.length > 1 && normalized.endsWith("/")) {
    normalized = normalized.slice(0, -1);
  }
  return normalized === "" ? "/" : normalized;
}
