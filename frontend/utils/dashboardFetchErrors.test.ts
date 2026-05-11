import { describe, expect, it } from "vitest";

import {
  buildDashboardFetchError,
  buildDashboardNetworkError,
  type DashboardFetchResult,
} from "./dashboardFetchErrors";

function result(
  endpoint: "bootstrap" | "overview" | "widgets" | "requests" | "error-groups",
  status: number,
): DashboardFetchResult {
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

  it("returns sign-in guidance for auth failures", () => {
    const message = buildDashboardFetchError([
      result("overview", 200),
      result("requests", 401),
      result("error-groups", 200),
    ]);
    expect(message).toContain("dashboard sign-in");
    expect(message).toContain("requests");
  });

  it("returns backend guidance for 5xx failures", () => {
    const message = buildDashboardFetchError([
      result("widgets", 500),
      result("requests", 200),
      result("error-groups", 200),
    ]);
    expect(message).toContain("Backend may be unavailable");
    expect(message).toContain("widgets");
  });

  it("returns rate-limit guidance for 429 responses", () => {
    const message = buildDashboardFetchError([
      result("overview", 200),
      result("requests", 429),
    ]);
    expect(message).toContain("rate-limited");
    expect(message).toContain("Narrow the time window");
    expect(message).toContain("requests");
  });

  it("returns slow-or-unavailable guidance for 503 responses", () => {
    const message = buildDashboardFetchError([
      result("overview", 200),
      result("error-groups", 503),
    ]);
    expect(message).toContain("unavailable or slow");
    expect(message).toContain("Narrow the window");
    expect(message).toContain("error-groups");
  });
});

describe("buildDashboardNetworkError", () => {
  it("returns connectivity guidance for network-level failures", () => {
    const message = buildDashboardNetworkError(new TypeError("Failed to fetch"));
    expect(message).toContain("NEXT_PUBLIC_LUMONOX_API_BASE_URL");
  });
});
