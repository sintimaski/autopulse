import { describe, expect, it } from "vitest";

import { cn } from "./cn";

describe("cn", () => {
  it("merges tailwind conflicts (last wins)", () => {
    expect(cn("p-4 p-2")).toBe("p-2");
  });

  it("filters falsy entries", () => {
    expect(cn("a", false && "b", "c")).toBe("a c");
  });
});
