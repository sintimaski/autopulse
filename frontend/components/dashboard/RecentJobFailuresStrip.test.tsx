import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { RecentJobFailuresStrip } from "./RecentJobFailuresStrip";

const range = {
  server_now: "2026-05-09T12:00:00Z",
  from_timestamp: "2026-05-09T09:00:00Z",
  to_timestamp: "2026-05-09T12:00:00Z",
};

describe("RecentJobFailuresStrip", () => {
  it("does not render when there are no job failures", () => {
    const html = renderToStaticMarkup(<RecentJobFailuresStrip data={{ ...range, items: [] }} />);
    expect(html).toBe("");
  });

  it("renders system diagnostics and diagnosis guidance when failures exist", () => {
    const html = renderToStaticMarkup(
      <RecentJobFailuresStrip
        data={{
          ...range,
          items: [
            {
              timestamp: "2026-05-09T10:00:00Z",
              trigger: "cron",
              job_name: "alerts-once",
              service_name: "api",
              environment: "prod",
              status_code: 500,
              latency_ms: 27.1,
              correlated_request_id: null,
              message: "smtp timeout",
            },
          ],
        }}
        moreHref="/diagnosis"
      />,
    );
    expect(html).toContain("Background jobs and cron");
    expect(html).toContain("Primary next action");
    expect(html).toContain("/settings#system-diagnostics");
    expect(html).toContain("/diagnosis");
  });
});
