import { describe, expect, it } from "vitest";

import { getNextActiveMenuIndex } from "./RowActionsMenu";

describe("RowActionsMenu keyboard indexing", () => {
  it("returns -1 when there are no items", () => {
    expect(getNextActiveMenuIndex(0, 0, "ArrowDown")).toBe(-1);
    expect(getNextActiveMenuIndex(0, 0, "Home")).toBe(-1);
  });

  it("wraps with arrow keys", () => {
    expect(getNextActiveMenuIndex(0, 3, "ArrowDown")).toBe(1);
    expect(getNextActiveMenuIndex(2, 3, "ArrowDown")).toBe(0);
    expect(getNextActiveMenuIndex(0, 3, "ArrowUp")).toBe(2);
  });

  it("jumps to first/last on Home/End", () => {
    expect(getNextActiveMenuIndex(1, 4, "Home")).toBe(0);
    expect(getNextActiveMenuIndex(1, 4, "End")).toBe(3);
  });
});
