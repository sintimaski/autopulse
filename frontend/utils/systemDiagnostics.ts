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

export type SchedulerJobSummary = {
  jobName: string;
  status: "succeeded" | "failed" | "unknown";
  lastFinishedAt: string | null;
  nextScheduledAt: string | null;
  failureReason: string | null;
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

export function normalizeSchedulerJobs(
  payload: DashboardSystemDiagnosticsResponse | null,
): SchedulerJobSummary[] {
  if (!payload) {
    return [];
  }
  const scheduler = asRecord(payload.scheduler);
  const jobs = Array.isArray(scheduler.jobs) ? scheduler.jobs : [];
  return jobs
    .map((job) => {
      const row = asRecord(job);
      const jobName = typeof row.job_name === "string" ? row.job_name : null;
      if (!jobName) {
        return null;
      }
      const status =
        row.status === "succeeded" || row.status === "failed" ? row.status : "unknown";
      return {
        jobName,
        status,
        lastFinishedAt: typeof row.finished_at === "string" ? row.finished_at : null,
        nextScheduledAt: typeof row.next_scheduled_at === "string" ? row.next_scheduled_at : null,
        failureReason: typeof row.failure_reason === "string" ? row.failure_reason : null,
      } satisfies SchedulerJobSummary;
    })
    .filter((row): row is SchedulerJobSummary => row !== null);
}
