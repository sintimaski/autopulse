import { describe, expect, it } from "vitest";

import { onboardingFirstIngestGuidance } from "./OnboardingContent";

describe("onboardingFirstIngestGuidance", () => {
  it("mentions HTTP 200 accepted guidance for static subpath UI", () => {
    const copy = onboardingFirstIngestGuidance(true);
    expect(copy).toContain("HTTP 200");
    expect(copy).toContain("accepted count");
    expect(copy).toContain("refresh");
  });

  it("mentions HTTP 200 accepted guidance for non-subpath deployments", () => {
    const copy = onboardingFirstIngestGuidance(false);
    expect(copy).toContain("HTTP 200");
    expect(copy).toContain("accepted count");
    expect(copy).toContain("instrumented app");
  });
});
