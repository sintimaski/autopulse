type DashboardEndpointLabel = "overview" | "requests" | "error-groups";

export type DashboardFetchResult = {
  endpoint: DashboardEndpointLabel;
  response: Response;
};

export function buildDashboardFetchError(results: DashboardFetchResult[]): string | null {
  const failed = results.find(({ response }) => !response.ok);
  if (!failed) {
    return null;
  }

  const status = failed.response.status;
  const statusText = failed.response.statusText || "Unknown";
  if (status === 401 || status === 403) {
    return `Dashboard ${failed.endpoint} request was rejected (${status} ${statusText}). Check NEXT_PUBLIC_AUTOPULSE_API_KEY and backend auth settings.`;
  }
  if (status >= 500) {
    return `Dashboard ${failed.endpoint} request failed (${status} ${statusText}). Backend may be unavailable.`;
  }
  return `Dashboard ${failed.endpoint} request failed (${status} ${statusText}).`;
}

export function buildDashboardNetworkError(error: unknown): string {
  if (error instanceof Error && error.name === "AbortError") {
    return "Dashboard request was aborted.";
  }
  if (error instanceof TypeError) {
    return "Cannot reach dashboard API. Check NEXT_PUBLIC_AUTOPULSE_API_BASE_URL, backend status, and CORS settings.";
  }
  if (error instanceof Error) {
    return error.message;
  }
  return "Unexpected dashboard loading failure.";
}
