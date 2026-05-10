import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import { MetricCard } from "./MetricCard";

describe("MetricCard", () => {
  it("uses article without button role when not clickable", () => {
    const html = renderToStaticMarkup(
      <MetricCard label="Errors" value="12" helper="Last window" tone="danger" />,
    );
    expect(html).toContain("<article");
    expect(html).not.toContain('role="button"');
  });

  it("exposes button semantics and aria-label when clickable", () => {
    const html = renderToStaticMarkup(
      <MetricCard label="Errors" value="12" helper="Click for details" tone="danger" onClick={vi.fn()} />,
    );
    expect(html).toContain('role="button"');
    expect(html).toContain('aria-label="Errors: 12. Click for details"');
    expect(html).toContain("focus-visible:ring-2");
  });
});
