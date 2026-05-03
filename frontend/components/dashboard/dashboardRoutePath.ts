/** Matches `basePath` in `frontend/next.config.ts`. */
export const DASHBOARD_UI_BASE_PATH = "/autopulse/ui";

/**
 * UI prefix for same-origin navigation (static export under ``/autopulse/ui``, or ``""`` when
 * ``AUTOPULSE_FRONTEND_MODE=sidecar`` with no basePath).
 */
export function resolveDashboardUiPrefix(): string {
  if (typeof window === "undefined") {
    return DASHBOARD_UI_BASE_PATH;
  }
  const path = window.location.pathname;
  const base = DASHBOARD_UI_BASE_PATH;
  if (path === base || path.startsWith(`${base}/`)) {
    return base;
  }
  return "";
}

/** Absolute path to the magic-link sign-in page on the current origin (respects Next ``basePath``). */
export function dashboardMagicLinkHref(): string {
  const prefix = resolveDashboardUiPrefix().replace(/\/$/, "");
  return prefix ? `${prefix}/auth/magic-link/` : "/auth/magic-link/";
}

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
