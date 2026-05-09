import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { AutoCollapsibleHeaderPanel } from "./AutoCollapsibleHeaderPanel";

describe("AutoCollapsibleHeaderPanel", () => {
  it("renders a native disclosure button for compact controls", () => {
    const html = renderToStaticMarkup(
      <AutoCollapsibleHeaderPanel>
        <div>filters</div>
      </AutoCollapsibleHeaderPanel>,
    );
    expect(html).toContain('type="button"');
    expect(html).toContain('aria-expanded="false"');
    expect(html).toContain("aria-controls");
    expect(html).toContain("Server scope");
    expect(html).not.toContain('role="button"');
  });

  it("renders the reset filters action as a sibling button", () => {
    const html = renderToStaticMarkup(
      <AutoCollapsibleHeaderPanel onResetFilters={() => {}}>
        <div>filters</div>
      </AutoCollapsibleHeaderPanel>,
    );
    expect(html).toContain('aria-label="Reset filters"');
  });
});
