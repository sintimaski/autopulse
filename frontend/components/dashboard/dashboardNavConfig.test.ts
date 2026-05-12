import { describe, expect, it } from "vitest";

import { DASHBOARD_NAV_SECTIONS, dashboardNavHrefs } from "./dashboardNavConfig";

describe("dashboardNavConfig", () => {
  it("lists diagnosis-first primary routes before advanced analytics", () => {
    const primary = DASHBOARD_NAV_SECTIONS.find((s) => s.id === "primary");
    expect(primary?.heading).toBeNull();
    expect(primary?.items.map((i) => i.href)).toEqual([
      "/dashboard",
      "/diagnosis",
      "/requests",
      "/incident",
      "/bookmarks",
      "/alerts",
    ]);
  });

  it("groups query and traces under Advanced", () => {
    const advanced = DASHBOARD_NAV_SECTIONS.find((s) => s.id === "advanced");
    expect(advanced?.heading).toBe("Advanced");
    expect(advanced?.items.map((i) => i.href)).toEqual(["/query-explorer", "/traces"]);
  });

  it("keeps settings as a separate trailing section", () => {
    const settings = DASHBOARD_NAV_SECTIONS.find((s) => s.id === "settings");
    expect(settings?.items).toHaveLength(1);
    expect(settings?.items[0]?.href).toBe("/settings");
  });

  it("exposes every dashboard shell route without duplicate hrefs", () => {
    const hrefs = dashboardNavHrefs();
    expect(new Set(hrefs).size).toBe(hrefs.length);
    expect(hrefs).toEqual([
      "/dashboard",
      "/diagnosis",
      "/requests",
      "/incident",
      "/bookmarks",
      "/alerts",
      "/query-explorer",
      "/traces",
      "/settings",
    ]);
  });
});
