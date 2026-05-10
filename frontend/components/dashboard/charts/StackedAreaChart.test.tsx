import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { StackedAreaChart } from "./StackedAreaChart";

describe("StackedAreaChart", () => {
  it("exposes a single concise assistive summary on the chart canvas region", () => {
    const html = renderToStaticMarkup(
      <StackedAreaChart
        labels={["10:00", "10:01"]}
        series={[
          { id: "a", label: "Series A", color: "#22c55e", values: [1, 2] },
          { id: "b", label: "Series B", color: "#f43f5e", values: [0, 1] },
        ]}
        accessibilityLabel="Custom stacked chart summary for tests"
      />,
    );
    expect(html).toContain('role="img"');
    expect(html).toContain('aria-label="Custom stacked chart summary for tests"');
  });

  it("builds a default aria-label from labels and series when none is passed", () => {
    const html = renderToStaticMarkup(
      <StackedAreaChart
        labels={["Mon", "Tue"]}
        series={[{ id: "2xx", label: "2xx", color: "#22c55e", values: [5, 6] }]}
      />,
    );
    expect(html).toContain('role="img"');
    expect(html).toContain("Stacked area chart: 2xx");
    expect(html).toContain("2 time buckets");
  });
});
