import { buildDashboardFetchError, type DashboardFetchResult } from "../../utils/dashboardFetchErrors";
import { parseDashboardBootstrapResponse } from "../../utils/dashboardResponseGuards";
import type { DashboardBootstrapResponse } from "./dashboardTypes";
import { dashboardSessionFetch } from "./dashboardSessionFetch";

/**
 * Fetches and parses `GET /dashboard/bootstrap`.
 * Call `onUnauthorized` when the response is HTTP 401 (before throwing on other errors).
 */
export async function loadDashboardBootstrap(
  signal: AbortSignal,
  onUnauthorized: () => void,
): Promise<DashboardBootstrapResponse> {
  const bootstrapResponse = await dashboardSessionFetch("/dashboard/bootstrap", {}, signal);
  if (bootstrapResponse.status === 401) {
    onUnauthorized();
  }
  const results = [{ endpoint: "bootstrap", response: bootstrapResponse }] as DashboardFetchResult[];
  const fetchError = buildDashboardFetchError(results);
  if (fetchError) {
    throw new Error(fetchError);
  }
  const rawBootstrap: unknown = await bootstrapResponse.json();
  const bootstrapData = parseDashboardBootstrapResponse(rawBootstrap);
  if (!bootstrapData) {
    throw new Error("bootstrap: invalid response shape");
  }
  return bootstrapData;
}
