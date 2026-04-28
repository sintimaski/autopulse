import { describe, expect, it } from "vitest";

import { buildGuidedTroubleshootingHints } from "./guidedTroubleshooting";

describe("buildGuidedTroubleshootingHints", () => {
  it("returns healthy fallback when no issues are present", () => {
    const hints = buildGuidedTroubleshootingHints({
      errorSpikeCandidate: false,
      outageCandidate: false,
      topFailingRouteCount: 0,
      hasFailedDispatch: false,
      failedDispatchReason: null,
      archivalStatus: "idle",
      archivalError: null,
    });
    expect(hints).toEqual([{ id: "healthy", title: "No urgent incident pattern detected" }]);
  });

  it("returns incident hints when multiple signals exist", () => {
    const hints = buildGuidedTroubleshootingHints({
      errorSpikeCandidate: true,
      outageCandidate: true,
      topFailingRouteCount: 3,
      hasFailedDispatch: true,
      failedDispatchReason: "provider_unreachable",
      archivalStatus: "failed",
      archivalError: "TimeoutError",
    });
    expect(hints.map((hint) => hint.id)).toEqual([
      "error-spike",
      "outage",
      "high-5xx-route",
      "alert-delivery",
      "retention-backlog",
    ]);
  });
});
