import { describe, expect, it } from "vitest";

import { buildDashboardDataQueryRequest, planDashboardBatchQueryForRoute } from "./dashboardQueryBundle";

describe("planDashboardBatchQueryForRoute", () => {
  const base = {
    isDocumentVisible: true,
    hasAdvancedScopeFilters: false,
    requestLimit: 100,
    requestPage: 2,
    errorGroupLimit: 25,
    errorGroupPage: 1,
  };

  it("clamps requests on /dashboard", () => {
    const plan = planDashboardBatchQueryForRoute({ routePath: "/dashboard", ...base });
    expect(plan.requestsLimitForRoute).toBe(25);
    expect(plan.requestsOffsetForRoute).toBe(0);
    expect(plan.includeWidgets).toBe(false);
  });

  it("loads widgets on /widgets and /w/... studio routes", () => {
    expect(planDashboardBatchQueryForRoute({ routePath: "/widgets", ...base }).includeWidgets).toBe(true);
    const studio = planDashboardBatchQueryForRoute({ routePath: "/w/lx_showcase", ...base });
    expect(studio.includeWidgets).toBe(true);
    expect(studio.includeExtended).toBe(true);
    expect(studio.requestsOffsetForRoute).toBe(0);
  });

  it("drops widgets when document hidden except diagnosis extended", () => {
    const plan = planDashboardBatchQueryForRoute({
      routePath: "/dashboard",
      ...base,
      isDocumentVisible: false,
    });
    expect(plan.includeWidgets).toBe(false);
    expect(plan.includeExtended).toBe(false);
  });

  it("keeps diagnosis extended when tab hidden", () => {
    const plan = planDashboardBatchQueryForRoute({
      routePath: "/diagnosis",
      ...base,
      isDocumentVisible: false,
    });
    expect(plan.includeExtended).toBe(true);
    expect(plan.includeDiagnosis).toBe(true);
  });
});

describe("buildDashboardDataQueryRequest", () => {
  it("maps scope and flags from plan", () => {
    const plan = planDashboardBatchQueryForRoute({
      routePath: "/alerts",
      isDocumentVisible: true,
      hasAdvancedScopeFilters: false,
      requestLimit: 50,
      requestPage: 0,
      errorGroupLimit: 10,
      errorGroupPage: 0,
    });
    const req = buildDashboardDataQueryRequest({
      plan,
      toIsoWindow: { from: "2026-01-01T00:00:00Z", to: "2026-01-01T01:00:00Z" },
      windowMinutes: 60,
      method: "ALL",
      statusClass: "ALL",
      minLatencyMs: "",
      maxLatencyMs: "",
      pathQuery: "",
      serverEnvironmentQuery: "",
      serverServiceQuery: "",
      sqlFilterEnabled: false,
      sqlFilterApplied: "",
    });
    expect(req.scope.method).toBeUndefined();
    expect(req.scope.status_class).toBeUndefined();
    expect(req.include_alert_dispatches).toBe(true);
    expect(req.requests).toEqual({ limit: 50, offset: 0 });
  });
});
