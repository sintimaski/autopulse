import { describe, expect, it } from "vitest";

import {
  onboardingFirstIngestGuidance,
  onboardingNoDataPrimaryAction,
  onboardingRoleActionCopy,
} from "./OnboardingContent";

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

describe("onboarding role and no-data guidance", () => {
  it("returns role-specific copy for owners/admins", () => {
    expect(onboardingRoleActionCopy(true)).toContain("owner/admin");
    expect(onboardingRoleActionCopy(true)).toContain("issue or rotate");
  });

  it("returns role-specific copy for members/viewers", () => {
    expect(onboardingRoleActionCopy(false)).toContain("member/viewer");
    expect(onboardingRoleActionCopy(false)).toContain("owner/admin");
  });

  it("provides one primary no-data action for key managers", () => {
    const copy = onboardingNoDataPrimaryAction(true, false);
    expect(copy).toContain("Primary next action");
    expect(copy).toContain("issue a key");
  });

  it("provides one primary no-data action for non-managers", () => {
    const copy = onboardingNoDataPrimaryAction(false, true);
    expect(copy).toContain("Primary next action");
    expect(copy).toContain("owner/admin");
  });
});
