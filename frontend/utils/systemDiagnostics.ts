import type { DashboardSystemDiagnosticsResponse } from "../components/dashboard/dashboardTypes";

export type SystemDiagnosticsSummary = {
  generatedAt: string | null;
  guardrailStatus: "healthy" | "degraded" | "unknown";
  schedulerStatus: "running" | "stopped" | "unknown";
  pendingSqlTailRepairs: number | null;
  deadLetteredSqlTailRepairs: number | null;
  aggregateDeadLetterBacklog: number | null;
  ingestionLagSeconds: number | null;
};

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" ? (value as Record<string, unknown>) : {};
}

function asNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

export function normalizeSystemDiagnostics(
  payload: DashboardSystemDiagnosticsResponse | null,
): SystemDiagnosticsSummary {
  if (!payload) {
    return {
      generatedAt: null,
      guardrailStatus: "unknown",
      schedulerStatus: "unknown",
      pendingSqlTailRepairs: null,
      deadLetteredSqlTailRepairs: null,
      aggregateDeadLetterBacklog: null,
      ingestionLagSeconds: null,
    };
  }
  const topology = asRecord(payload.topology);
  const scheduler = asRecord(payload.scheduler);
  const replayQueue = asRecord(payload.replay_queue);
  const freshness = asRecord(payload.ingestion_freshness);
  const guardrails = asRecord(topology.guardrails);
  const guardrailStatus =
    guardrails.status === "healthy" || guardrails.status === "degraded"
      ? guardrails.status
      : "unknown";
  const schedulerStatus =
    scheduler.scheduler_running === true
      ? "running"
      : scheduler.scheduler_running === false
        ? "stopped"
        : "unknown";
  return {
    generatedAt: payload.generated_at ?? null,
    guardrailStatus,
    schedulerStatus,
    pendingSqlTailRepairs: asNumber(replayQueue.pending_sql_tail_repairs),
    deadLetteredSqlTailRepairs: asNumber(replayQueue.dead_lettered_sql_tail_repairs),
    aggregateDeadLetterBacklog: asNumber(replayQueue.aggregate_dead_letter_backlog_total),
    ingestionLagSeconds: asNumber(freshness.lag_seconds),
  };
}

export function formatDurationSeconds(seconds: number | null): string {
  if (seconds === null) {
    return "n/a";
  }
  if (seconds < 60) {
    return `${seconds.toFixed(0)}s`;
  }
  if (seconds < 3600) {
    return `${(seconds / 60).toFixed(1)}m`;
  }
  return `${(seconds / 3600).toFixed(1)}h`;
}
