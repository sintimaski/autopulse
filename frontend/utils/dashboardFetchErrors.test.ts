import { describe, expect, it } from "vitest";

import {
  buildDashboardFetchError,
  buildDashboardNetworkError,
  type DashboardFetchResult,
} from "./dashboardFetchErrors";

function result(endpoint: "overview" | "requests" | "error-groups", status: number): DashboardFetchResult {
  return {
    endpoint,
    response: new Response(null, { status, statusText: `S${status}` }),
  };
}

describe("buildDashboardFetchError", () => {
  it("returns null when every request succeeds", () => {
    const message = buildDashboardFetchError([
      result("overview", 200),
      result("requests", 200),
      result("error-groups", 200),
    ]);
    expect(message).toBeNull();
  });

  it("returns API key guidance for auth failures", () => {
    const message = buildDashboardFetchError([
      result("overview", 200),
      result("requests", 401),
      result("error-groups", 200),
    ]);
    expect(message).toContain("NEXT_PUBLIC_AUTOPULSE_API_KEY");
    expect(message).toContain("requests");
  });

  it("returns backend guidance for 5xx failures", () => {
    const message = buildDashboardFetchError([
      result("overview", 500),
      result("requests", 200),
      result("error-groups", 200),
    ]);
    expect(message).toContain("Backend may be unavailable");
    expect(message).toContain("overview");
  });
});

describe("buildDashboardNetworkError", () => {
  it("returns connectivity guidance for network-level failures", () => {
    const message = buildDashboardNetworkError(new TypeError("Failed to fetch"));
    expect(message).toContain("NEXT_PUBLIC_AUTOPULSE_API_BASE_URL");
  });
});
