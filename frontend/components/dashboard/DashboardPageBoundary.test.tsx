import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { ApiKeyMissing } from "./DashboardPageBoundary";

describe("ApiKeyMissing", () => {
  it("renders sign-in guidance", () => {
    const html = renderToStaticMarkup(<ApiKeyMissing />);
    expect(html).toContain("Dashboard sign in");
    expect(html).toContain("Request magic link");
    expect(html).toContain("Verify and continue");
  });
});
