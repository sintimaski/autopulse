"use client";

import { useMemo } from "react";

import type { InternalMetricsSnapshot } from "./settingsContentTypes";

export function useSettingsAggregateQueueStats(snapshot: InternalMetricsSnapshot | null) {
  return useMemo(() => {
    const aggregateQueueDepth = snapshot?.ingest_aggregate_queue?.depth ?? null;
    const aggregateQueueMax = snapshot?.ingest_aggregate_queue?.max_size ?? null;
    const aggregateQueueEnabled = Boolean(snapshot?.ingest_aggregate_queue?.enabled);
    const queueUsageRatio =
      typeof aggregateQueueDepth === "number" &&
      typeof aggregateQueueMax === "number" &&
      aggregateQueueMax > 0
        ? aggregateQueueDepth / aggregateQueueMax
        : null;
    const aggregateQueueHealthy = queueUsageRatio === null ? null : queueUsageRatio < 0.8;
    const aggregateWorkerHealthy = aggregateQueueEnabled ? aggregateQueueHealthy : null;

    return {
      aggregateQueueDepth,
      aggregateQueueMax,
      aggregateQueueEnabled,
      queueUsageRatio,
      aggregateQueueHealthy,
      aggregateWorkerHealthy,
    };
  }, [snapshot]);
}
