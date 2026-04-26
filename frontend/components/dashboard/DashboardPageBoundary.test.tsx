import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { ApiKeyMissing } from "./DashboardPageBoundary";

describe("ApiKeyMissing", () => {
  it("renders required frontend env variable guidance", () => {
    const html = renderToStaticMarkup(<ApiKeyMissing />);
    expect(html).toContain("NEXT_PUBLIC_AUTOPULSE_API_KEY");
    expect(html).toContain("NEXT_PUBLIC_AUTOPULSE_API_BASE_URL");
    expect(html).toContain("frontend/.env.local");
  });
});
