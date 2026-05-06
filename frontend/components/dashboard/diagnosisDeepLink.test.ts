import { describe, expect, it } from "vitest";

import {
  isDiagnosisScopePartial,
  nextDeepLinkRetryAction,
  parseErrorGroupHash,
} from "./diagnosisDeepLink";

describe("parseErrorGroupHash", () => {
  it("returns decoded key for error-group hash", () => {
    expect(parseErrorGroupHash("#error-group:foo%2Fbar")).toBe("foo/bar");
  });

  it("returns null for unsupported hash", () => {
    expect(parseErrorGroupHash("#grouped-errors")).toBeNull();
  });
});

describe("nextDeepLinkRetryAction", () => {
  it("resets page first when page is not zero", () => {
    expect(
      nextDeepLinkRetryAction({
        targetGroupKey: "g-1",
        lastRetriedKey: null,
        errorGroupPage: 3,
        errorGroupLimit: 25,
      }),
    ).toBe("reset_page");
  });

  it("expands limit when page is already zero", () => {
    expect(
      nextDeepLinkRetryAction({
        targetGroupKey: "g-1",
        lastRetriedKey: null,
        errorGroupPage: 0,
        errorGroupLimit: 25,
      }),
    ).toBe("expand_limit");
  });

  it("does not retry twice for same key", () => {
    expect(
      nextDeepLinkRetryAction({
        targetGroupKey: "g-1",
        lastRetriedKey: "g-1",
        errorGroupPage: 0,
        errorGroupLimit: 25,
      }),
    ).toBe("none");
  });
});

describe("isDiagnosisScopePartial", () => {
  it("flags partial when request sample is truncated", () => {
    expect(
      isDiagnosisScopePartial({
        requestSampleCount: 25,
        requestTotalCount: 120,
        requestOffset: 0,
        errorGroupSampleCount: 10,
        errorGroupTotalCount: 10,
        errorGroupPage: 0,
        hasScopeNarrowing: false,
      }),
    ).toBe(true);
  });

  it("flags partial when scope has narrowing filters", () => {
    expect(
      isDiagnosisScopePartial({
        requestSampleCount: 25,
        requestTotalCount: 25,
        requestOffset: 0,
        errorGroupSampleCount: 10,
        errorGroupTotalCount: 10,
        errorGroupPage: 0,
        hasScopeNarrowing: true,
      }),
    ).toBe(true);
  });

  it("returns false for fully loaded, unfiltered scope", () => {
    expect(
      isDiagnosisScopePartial({
        requestSampleCount: 25,
        requestTotalCount: 25,
        requestOffset: 0,
        errorGroupSampleCount: 10,
        errorGroupTotalCount: 10,
        errorGroupPage: 0,
        hasScopeNarrowing: false,
      }),
    ).toBe(false);
  });
});
