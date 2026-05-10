import { describe, expect, it } from "vitest";

import type { DashboardWidgetsResponse } from "./dashboardTypes";
import {
  LX_STUDIO_WIDGET_POINT_PREFIX,
  MAX_WIDGET_POINTS_TOTAL,
  trimDashboardWidgetPayload,
} from "./dashboardDataFetchUtils";

const emptyWidgets = (): DashboardWidgetsResponse => ({
  server_now: "2026-01-01T02:00:00Z",
  from_timestamp: "2026-01-01T00:00:00Z",
  to_timestamp: "2026-01-01T02:00:00Z",
  definitions: [],
  points: [],
  layout: null,
});

describe("trimDashboardWidgetPayload", () => {
  it("keeps all lx_studio_ points when many user widget rows exceed the global cap", () => {
    const points: DashboardWidgetsResponse["points"] = [];
    for (let w = 0; w < 15; w++) {
      for (let i = 0; i < 240; i++) {
        points.push({
          widget_id: `user_widget_${w}`,
          timestamp: `2026-01-01T01:59:${String(i % 60).padStart(2, "0")}.${String(i + w * 1000).padStart(6, "0")}Z`,
          label: null,
          value: i,
        });
      }
    }
    const studioCount = 40;
    for (let i = 0; i < studioCount; i++) {
      points.push({
        widget_id: `${LX_STUDIO_WIDGET_POINT_PREFIX}full_line`,
        timestamp: `2026-01-01T00:00:${String(i).padStart(2, "0")}Z`,
        label: null,
        value: 42 + i,
      });
    }
    const out = trimDashboardWidgetPayload({ ...emptyWidgets(), points });
    const studioOut = out.points.filter((p) => p.widget_id.startsWith(LX_STUDIO_WIDGET_POINT_PREFIX));
    expect(studioOut.length).toBe(studioCount);
    expect(out.points.length).toBeLessThanOrEqual(MAX_WIDGET_POINTS_TOTAL);
  });
});
