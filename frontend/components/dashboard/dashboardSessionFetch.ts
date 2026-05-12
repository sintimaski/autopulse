import { buildApiUrl } from "./dashboardTypes";
import { DASHBOARD_FETCH_TIMEOUT_MS, fetchWithTimeout } from "./dashboardDataFetchUtils";

/**
 * Authenticated dashboard API fetch with default timeout and `credentials: "include"`.
 */
export function dashboardSessionFetch(
  path: string,
  init: RequestInit = {},
  parentSignal?: AbortSignal,
): Promise<Response> {
  return fetchWithTimeout(
    buildApiUrl(path),
    { ...init, credentials: "include" },
    DASHBOARD_FETCH_TIMEOUT_MS,
    parentSignal,
  );
}

export function dashboardSessionJsonPut(
  path: string,
  body: unknown,
  parentSignal?: AbortSignal,
): Promise<Response> {
  return dashboardSessionFetch(
    path,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    },
    parentSignal,
  );
}

export function dashboardSessionJsonPost(
  path: string,
  body: unknown,
  parentSignal?: AbortSignal,
): Promise<Response> {
  return dashboardSessionFetch(
    path,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    },
    parentSignal,
  );
}

export function dashboardSessionJsonPatch(
  path: string,
  body: unknown,
  parentSignal?: AbortSignal,
): Promise<Response> {
  return dashboardSessionFetch(
    path,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    },
    parentSignal,
  );
}
