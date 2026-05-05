import { describe, expect, it } from "vitest";

import { logicalDashboardLocationHrefWithPrefix, toDashboardRoutePath } from "./dashboardRoutePath";

describe("toDashboardRoutePath", () => {
  it("strips static UI base path", () => {
    expect(toDashboardRoutePath("/autopulse/ui/dashboard/")).toBe("/dashboard");
    expect(toDashboardRoutePath("/autopulse/ui")).toBe("/");
  });
});

describe("logicalDashboardLocationHrefWithPrefix", () => {
  it("leaves logical href unchanged when there is no UI prefix (sidecar dev)", () => {
    expect(logicalDashboardLocationHrefWithPrefix("/dashboard?w=5", "")).toBe("/dashboard?w=5");
  });

  it("prefixes static export base path and adds trailing slash before query", () => {
    expect(logicalDashboardLocationHrefWithPrefix("/dashboard?w=5", "/autopulse/ui")).toBe(
      "/autopulse/ui/dashboard/?w=5",
    );
  });

  it("handles hash-only suffix", () => {
    expect(logicalDashboardLocationHrefWithPrefix("/dashboard#x", "/autopulse/ui")).toBe(
      "/autopulse/ui/dashboard/#x",
    );
  });

  it("maps logical root", () => {
    expect(logicalDashboardLocationHrefWithPrefix("/", "/autopulse/ui")).toBe("/autopulse/ui/");
    expect(logicalDashboardLocationHrefWithPrefix("/?x=1", "/autopulse/ui")).toBe("/autopulse/ui/?x=1");
  });
});
