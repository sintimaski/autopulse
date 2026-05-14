"use client";

import { dashboardNavHrefs } from "./dashboardNavConfig";
import { buildApiUrl } from "./dashboardTypes";

export type DashboardBookmarkItem = {
  id: string;
  title: string;
  pathname: string;
  query_string: string | null;
  hash_fragment: string | null;
  notes: string | null;
  visibility: "private" | "project";
  created_by_user_id: string;
  created_at: string;
  updated_at: string;
  project_id: string;
  project_name: string;
};

export type DashboardBookmarksListResponse = {
  items: DashboardBookmarkItem[];
};

async function parseJsonResponse<T>(response: Response): Promise<T> {
  const raw = await response.text();
  let parsed: unknown = null;
  try {
    parsed = raw ? JSON.parse(raw) : null;
  } catch {
    parsed = null;
  }
  if (!response.ok) {
    const detail =
      parsed && typeof parsed === "object" && parsed !== null && "detail" in parsed
        ? String((parsed as { detail: unknown }).detail)
        : raw.slice(0, 240);
    throw new Error(detail || `Request failed (${response.status})`);
  }
  return parsed as T;
}

/**
 * Known in-app dashboard route prefixes. A bookmark whose `pathname` does not
 * match one of these is treated as foreign/unrecognized and is not rendered as
 * a navigable link (mirrors the `safeUrl` guard in IncidentMarkdownBody.tsx).
 */
const KNOWN_DASHBOARD_ROUTES: readonly string[] = [
  ...dashboardNavHrefs(),
  "/dashboard",
  "/diagnosis",
  "/requests",
  "/incident",
  "/bookmarks",
  "/alerts",
  "/query-explorer",
  "/traces",
  "/settings",
  "/onboarding",
  "/w",
];

/**
 * True when a bookmark `pathname` points at a recognized in-app dashboard route.
 * Only same-origin absolute paths are accepted (must start with `/`); a known
 * route also matches its sub-paths (e.g. `/incident/abc`, `/w/proj/...`).
 */
export function isKnownDashboardRoute(pathname: string): boolean {
  const path = pathname?.trim() ?? "";
  if (!path.startsWith("/") || path.startsWith("//")) {
    return false;
  }
  // Strip any accidentally-included query/hash before matching the path.
  const clean = path.split(/[?#]/, 1)[0];
  return KNOWN_DASHBOARD_ROUTES.some(
    (route) => clean === route || clean.startsWith(`${route}/`),
  );
}

export async function fetchDashboardBookmarks(): Promise<DashboardBookmarkItem[]> {
  const response = await fetch(buildApiUrl("/dashboard/bookmarks"), { credentials: "include" });
  const body = await parseJsonResponse<DashboardBookmarksListResponse>(response);
  return body.items;
}

export async function createDashboardBookmark(payload: {
  title: string;
  pathname: string;
  query_string?: string | null;
  hash_fragment?: string | null;
  notes?: string | null;
  visibility?: "private" | "project";
}): Promise<DashboardBookmarkItem> {
  const response = await fetch(buildApiUrl("/dashboard/bookmarks"), {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return parseJsonResponse<DashboardBookmarkItem>(response);
}

export async function updateDashboardBookmark(
  id: string,
  payload: Partial<{
    title: string;
    pathname: string;
    query_string: string | null;
    hash_fragment: string | null;
    notes: string | null;
    visibility: "private" | "project";
  }>,
): Promise<DashboardBookmarkItem> {
  const response = await fetch(buildApiUrl(`/dashboard/bookmarks/${encodeURIComponent(id)}`), {
    method: "PUT",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return parseJsonResponse<DashboardBookmarkItem>(response);
}

export async function deleteDashboardBookmark(id: string): Promise<void> {
  const response = await fetch(buildApiUrl(`/dashboard/bookmarks/${encodeURIComponent(id)}`), {
    method: "DELETE",
    credentials: "include",
  });
  if (response.status === 204 || response.status === 200) {
    return;
  }
  await parseJsonResponse<unknown>(response);
}
