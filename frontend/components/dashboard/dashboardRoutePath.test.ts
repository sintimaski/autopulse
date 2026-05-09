import { describe, expect, it } from "vitest";

import { logicalDashboardLocationHrefWithPrefix, toDashboardRoutePath } from "./dashboardRoutePath";

describe("toDashboardRoutePath", () => {
  it("strips static UI base path", () => {
    expect(toDashboardRoutePath("/lumonox/ui/dashboard/")).toBe("/dashboard");
    expect(toDashboardRoutePath("/lumonox/ui")).toBe("/");
  });
});

describe("logicalDashboardLocationHrefWithPrefix", () => {
  it("leaves logical href unchanged when there is no UI prefix (sidecar dev)", () => {
    expect(logicalDashboardLocationHrefWithPrefix("/dashboard?w=5", "")).toBe("/dashboard?w=5");
  });

  it("prefixes static export base path and adds trailing slash before query", () => {
    expect(logicalDashboardLocationHrefWithPrefix("/dashboard?w=5", "/lumonox/ui")).toBe(
      "/lumonox/ui/dashboard/?w=5",
    );
  });

  it("handles hash-only suffix", () => {
    expect(logicalDashboardLocationHrefWithPrefix("/dashboard#x", "/lumonox/ui")).toBe(
      "/lumonox/ui/dashboard/#x",
    );
  });

  it("maps logical root", () => {
    expect(logicalDashboardLocationHrefWithPrefix("/", "/lumonox/ui")).toBe("/lumonox/ui/");
    expect(logicalDashboardLocationHrefWithPrefix("/?x=1", "/lumonox/ui")).toBe("/lumonox/ui/?x=1");
  });
});
