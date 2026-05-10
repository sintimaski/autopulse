/**
 * Settings-page-only types (kept out of `SettingsContent.tsx` to shrink the main component).
 */

/** Snapshot merged from `DashboardInternalMetricsResponse.metrics` in the UI. */
export type InternalMetricsSnapshot = {
  dashboard_ws_tick_running?: boolean;
  dashboard_realtime_bus_subscriber_running?: boolean;
  scheduler_running?: boolean;
  retention_pressure_poll_running?: boolean;
  ingest_pressure?: Record<string, number>;
  ingest_aggregate_queue?: {
    enabled?: boolean;
    depth?: number | null;
    max_size?: number | null;
  };
};

export type EventPlaneCutoverSettings = {
  use_snapshot_read: boolean;
};
