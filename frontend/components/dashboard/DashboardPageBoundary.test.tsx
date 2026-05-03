import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { ApiKeyMissing } from "./DashboardPageBoundary";

describe("ApiKeyMissing", () => {
  it("renders sign-in guidance", () => {
    const html = renderToStaticMarkup(<ApiKeyMissing />);
    expect(html).toContain("Dashboard sign in");
    expect(html).toContain("Request magic link");
    // Session-first copy preserved.
    expect(html).toContain("Session-first");
  });

  it("provides an accessible email input", () => {
    const html = renderToStaticMarkup(<ApiKeyMissing />);
    expect(html).toContain('aria-label="Email address"');
    expect(html).toContain("Email for magic link sign-in");
  });
});
