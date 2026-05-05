import { describe, expect, it } from "vitest";

import { sanitizeRumPath, sanitizeRumStack, sanitizeRumText } from "./rumSanitize";

describe("sanitizeRumText", () => {
  it("redacts email addresses and token-like query pairs", () => {
    const value = sanitizeRumText("failed for jane@example.com token=abc123&api_key=xyz");
    expect(value).toContain("[redacted-email]");
    expect(value).not.toContain("jane@example.com");
    expect(value).toContain("token=[redacted]");
    expect(value).toContain("api_key=[redacted]");
  });
});

describe("sanitizeRumPath", () => {
  it("drops query/hash and masks id-like segments", () => {
    const path = sanitizeRumPath(
      "/users/123/orders/8a5fbb40-bf41-4520-b5d4-6fc4f6f4781e?email=jane@example.com#frag",
    );
    expect(path).toBe("/users/:id/orders/:id");
  });
});

describe("sanitizeRumStack", () => {
  it("keeps only first two sanitized lines", () => {
    const stack = sanitizeRumStack(
      "Error: failed user jane@example.com\nat fn (https://x.dev/path?token=abc)\nat ignored line",
    );
    expect(stack).toContain("[redacted-email]");
    expect(stack).not.toContain("token=abc");
    expect(stack).not.toContain("ignored line");
  });
});
