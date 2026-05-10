export const PAGE_META: Record<string, { title: string; subtitle: string }> = {
  "/dashboard": {
    title: "Overview",
    subtitle:
      "Health snapshot — Overview scope uses the same URL keys as Diagnosis and Requests; open those pages for path, latency, or advanced filters.",
  },
  "/widgets": {
    title: "Widgets",
    subtitle: "This URL forwards to the studio layout lab.",
  },
  "/w/lx_showcase": {
    title: "Widget layout lab",
    subtitle: "Every widget type with varied sections, column spans, and row spans.",
  },
  "/widgets-showroom": {
    title: "Widgets",
    subtitle: "This URL forwards to /w/lx_showcase.",
  },
  "/widgets-showcase": {
    title: "Widgets",
    subtitle: "This URL forwards to /w/lx_showcase.",
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
      "DuckDB SQL — header Time scope sets the window only; filter in SQL, or turn off the time limit for a full-project scan.",
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
    subtitle: ".env.lumonox, first ingest, diagnosis.",
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
