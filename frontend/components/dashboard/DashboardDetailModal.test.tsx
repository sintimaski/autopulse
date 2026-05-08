import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import { DashboardDetailModal } from "./DashboardDetailModal";

describe("DashboardDetailModal", () => {
  it("does not render when closed", () => {
    const html = renderToStaticMarkup(
      <DashboardDetailModal open={false} title="Evidence" onClose={vi.fn()}>
        <div>body</div>
      </DashboardDetailModal>,
    );
    expect(html).toBe("");
  });

  it("renders dialog semantics and close control when open", () => {
    const html = renderToStaticMarkup(
      <DashboardDetailModal open title="Evidence" onClose={vi.fn()}>
        <div>body</div>
      </DashboardDetailModal>,
    );
    expect(html).toContain('role="dialog"');
    expect(html).toContain('aria-modal="true"');
    expect(html).toContain("Close");
    expect(html).toContain("Evidence");
  });
});
