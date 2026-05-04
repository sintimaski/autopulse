import { describe, expect, it } from "vitest";

import {
  buildAlignedChartSpanOptions,
  buildAlignedRollupBucketOptions,
  buildVolumeStepOptions,
  defaultVolumeStepMinutes,
  formatMinutesForUi,
  VOLUME_CHART_TARGET_MAX_BUCKETS,
} from "./dashboardChartWindows";

describe("buildAlignedChartSpanOptions", () => {
  it("labels full range with main window and only lists spans strictly below it", () => {
    const opts = buildAlignedChartSpanOptions(15);
    expect(opts[opts.length - 1]).toEqual({ value: 0, label: "Full loaded range (15m)" });
    expect(opts.map((o) => o.value)).toEqual([1, 2, 5, 10, 0]);
    expect(opts.find((o) => o.value === 15)).toBeUndefined();
  });

  it("includes hour-style labels for large windows", () => {
    const opts = buildAlignedChartSpanOptions(120);
    expect(opts[opts.length - 1].label).toBe("Full loaded range (2h)");
    const last60 = opts.find((o) => o.value === 60);
    expect(last60?.label).toBe("Last 1h");
  });
});

describe("buildAlignedRollupBucketOptions", () => {
  it("includes native and buckets not larger than cap", () => {
    const opts = buildAlignedRollupBucketOptions(15);
    expect(opts.map((o) => o.value)).toEqual([0, 1, 5, 15]);
  });

  it("omits buckets larger than a short cap", () => {
    const opts = buildAlignedRollupBucketOptions(3);
    expect(opts.map((o) => o.value)).toEqual([0, 1]);
  });
});

describe("formatMinutesForUi", () => {
  it("formats hours for multiples of 60", () => {
    expect(formatMinutesForUi(60)).toBe("1h");
    expect(formatMinutesForUi(120)).toBe("2h");
  });
});

describe("buildVolumeStepOptions", () => {
  it("allows fine steps for short spans", () => {
    const steps = buildVolumeStepOptions(15);
    expect(steps).toContain(1);
    expect(steps[0]).toBe(1);
  });

  it("raises minimum step for 24h so bucket count stays bounded", () => {
    const steps = buildVolumeStepOptions(1440);
    expect(Math.min(...steps)).toBeGreaterThanOrEqual(Math.ceil(1440 / VOLUME_CHART_TARGET_MAX_BUCKETS));
    expect(steps).not.toContain(1);
    expect(steps).toContain(10);
  });

  it("uses span as sole step when span is below any preset", () => {
    expect(buildVolumeStepOptions(1)).toEqual([1]);
  });

  it("offers coarser steps for 12h windows", () => {
    const steps = buildVolumeStepOptions(720);
    expect(Math.min(...steps)).toBeGreaterThanOrEqual(5);
    expect(steps).toContain(10);
    expect(steps).toContain(15);
  });
});

describe("defaultVolumeStepMinutes", () => {
  it("prefers a coarser step than 1m when the span allows", () => {
    const allowed = buildVolumeStepOptions(15);
    expect(defaultVolumeStepMinutes(15, allowed)).toBeGreaterThanOrEqual(2);
  });

  it("falls back to the only allowed step for a 1-minute span", () => {
    const allowed = buildVolumeStepOptions(1);
    expect(defaultVolumeStepMinutes(1, allowed)).toBe(1);
  });

  it("targets a moderate bucket count for a 24h window", () => {
    const allowed = buildVolumeStepOptions(1440);
    const step = defaultVolumeStepMinutes(1440, allowed);
    expect(1440 / step).toBeLessThanOrEqual(48);
    expect(allowed).toContain(step);
  });
});
