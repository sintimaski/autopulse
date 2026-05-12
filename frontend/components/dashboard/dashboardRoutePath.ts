/** Matches `basePath` in `frontend/next.config.ts`. */
const DASHBOARD_UI_BASE_PATH = "/lumonox/ui";

/** Set in ``next.config.ts`` sidecar branch via ``env.NEXT_PUBLIC_LUMONOX_FRONTEND_MODE``. */
const IS_NEXT_SIDECAR =
  process.env.NEXT_PUBLIC_LUMONOX_FRONTEND_MODE?.trim().toLowerCase() === "sidecar";

/**
 * UI prefix for same-origin navigation (static export under ``/lumonox/ui``, or ``""`` when
 * ``NEXT_PUBLIC_LUMONOX_FRONTEND_MODE=sidecar`` / Next sidecar config with no basePath).
 */
function resolveDashboardUiPrefix(): string {
  if (typeof window === "undefined") {
    // Next SSR/RSC: no ``location`` yet. Sidecar dev has no ``/lumonox/ui`` basePath; defaulting to
    // ``DASHBOARD_UI_BASE_PATH`` here produced wrong hrefs (e.g. DB share links → ``/lumonox/ui/incident/`` → 404).
    if (IS_NEXT_SIDECAR) {
      return "";
    }
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

/**
 * Pure mapping from a logical dashboard href to the browser location path (prefix + trailing
 * slash before query), used by {@link logicalDashboardLocationHref} and unit-tested directly.
 */
export function logicalDashboardLocationHrefWithPrefix(logicalHref: string, uiPrefix: string): string {
  const prefix = uiPrefix.replace(/\/$/, "");
  const full = logicalHref.startsWith("/") ? logicalHref : `/${logicalHref}`;
  if (!prefix) {
    return full;
  }

  const q = full.indexOf("?");
  const h = full.indexOf("#");
  const meta = [q, h].filter((i) => i >= 0);
  const cut = meta.length === 0 ? Infinity : Math.min(...meta);
  const pathPart = cut === Infinity ? full : full.slice(0, cut);
  const suffix = cut === Infinity ? "" : full.slice(cut);

  if (pathPart === "/" || pathPart === "") {
    return `${prefix}/${suffix}`;
  }
  const withSlash = pathPart.endsWith("/") ? pathPart : `${pathPart}/`;
  return `${prefix}${withSlash}${suffix}`;
}

/**
 * Turn a logical dashboard URL (no `basePath`) into the path+search+hash string the browser
 * should show after `history.replaceState`, e.g. `/dashboard?…` → `/lumonox/ui/dashboard/?…`
 * when the bundle is served under `/lumonox/ui` (see `next.config.ts`). Without this, a path
 * starting with `/` is resolved from the site root and drops the UI prefix.
 */
export function logicalDashboardLocationHref(logicalHref: string): string {
  return logicalDashboardLocationHrefWithPrefix(logicalHref, resolveDashboardUiPrefix());
}
