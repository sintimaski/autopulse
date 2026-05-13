"use client";

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
