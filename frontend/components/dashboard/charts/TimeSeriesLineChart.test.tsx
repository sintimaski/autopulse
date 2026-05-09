import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { TimeSeriesLineChart } from "./TimeSeriesLineChart";

describe("TimeSeriesLineChart", () => {
  it("exposes chart semantics for assistive technologies", () => {
    const html = renderToStaticMarkup(
      <TimeSeriesLineChart
        title="Error Rate Trend"
        values={[1, 2, 3]}
        labels={["10:00", "10:01", "10:02"]}
        color="#f43f5e"
        formatValue={(value) => `${value.toFixed(1)}%`}
      />,
    );
    expect(html).toContain('role="img"');
    expect(html).toContain('aria-label="Error Rate Trend time series chart"');
  });
});
