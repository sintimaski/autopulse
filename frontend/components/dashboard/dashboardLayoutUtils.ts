export const PAGE_META: Record<string, { title: string; subtitle: string }> = {
  "/dashboard": {
    title: "Overview",
    subtitle:
      "Health snapshot — Overview scope uses the same URL keys as Diagnosis and Requests; open those pages for path, latency, or advanced filters.",
  },
  "/widgets-showcase": {
    title: "Widgets",
    subtitle: "Live SDK charts from your scope plus a timer-driven mock preview.",
  },
  "/widgets-showroom": {
    title: "Widgets",
    subtitle: "This URL forwards to the unified widgets page.",
  },
  "/requests": {
    title: "Requests",
    subtitle: "Request-level evidence — same investigation scope as Overview and Diagnosis.",
  },
  "/diagnosis": {
    title: "Errors & Diagnosis",
    subtitle: "Grouped failures and signals — start here when something breaks.",
  },
  "/alerts": {
    title: "Alerts",
    subtitle: "Alert heuristics, settings, and runbook shortcuts.",
  },
  "/query-explorer": {
    title: "Query Explorer",
    subtitle:
      "DuckDB SQL — use the header scope (same as Requests), or run unscoped against the full live database for this project.",
  },
  "/traces": {
    title: "Traces (OTLP)",
    subtitle: "Search and inspect spans ingested via OTLP HTTP.",
  },
  "/settings": {
    title: "Settings",
    subtitle: "Project defaults, theme, and delivery channels.",
  },
  "/bookmarks": {
    title: "Bookmarks",
    subtitle: "Your saved deep links for this project — open, rename, or remove.",
  },
  "/logs": {
    title: "Requests",
    subtitle: "This URL forwards to Requests — bookmark /requests for clarity.",
  },
  "/onboarding": {
    title: "Onboarding",
    subtitle: ".env.autopulse, first ingest, diagnosis.",
  },
};

export function isScopedUrlSyncRoute(pathname: string): boolean {
  return (
    pathname === "/dashboard" ||
    pathname === "/diagnosis" ||
    pathname === "/logs" ||
    pathname === "/requests" ||
    pathname === "/query-explorer"
  );
}

export function isScopedPathRestoreRoute(pathname: string): boolean {
  return pathname === "/diagnosis" || pathname === "/logs" || pathname === "/requests";
}

export function replaceScopedUrlInPlace(nextHref: string): void {
  if (typeof window === "undefined") {
    return;
  }
  const current = `${window.location.pathname}${window.location.search}${window.location.hash}`;
  if (current === nextHref) {
    return;
  }
  window.history.replaceState(window.history.state, "", nextHref);
}
