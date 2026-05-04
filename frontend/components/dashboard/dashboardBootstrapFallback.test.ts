import { describe, expect, it } from "vitest";

import { createBootstrapFailureOnboardingFallback } from "./dashboardBootstrapFallback";

describe("createBootstrapFailureOnboardingFallback", () => {
  it("marks onboarding completed so shell routing does not deadlock", () => {
    const fallback = createBootstrapFailureOnboardingFallback();
    expect(fallback.onboarding_completed).toBe(true);
    expect(fallback.session_authenticated).toBe(true);
  });
});
