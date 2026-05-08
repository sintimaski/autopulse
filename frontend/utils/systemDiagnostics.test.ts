import { describe, expect, it } from "vitest";

import {
  formatDurationSeconds,
  normalizeSystemDiagnostics,
  normalizeSchedulerJobs,
} from "./systemDiagnostics";

describe("normalizeSystemDiagnostics", () => {
  it("returns unknown defaults when payload is null", () => {
    const summary = normalizeSystemDiagnostics(null);
    expect(summary.guardrailStatus).toBe("unknown");
    expect(summary.schedulerStatus).toBe("unknown");
    expect(summary.pendingSqlTailRepairs).toBeNull();
  });

  it("extracts key supportability indicators from payload", () => {
    const summary = normalizeSystemDiagnostics({
      generated_at: "2026-05-08T13:00:00Z",
      topology: {
        guardrails: {
          status: "degraded",
        },
      },
      scheduler: {
        scheduler_running: false,
      },
      replay_queue: {
        pending_sql_tail_repairs: 3,
        dead_lettered_sql_tail_repairs: 1,
        aggregate_dead_letter_backlog_total: 2,
      },
      ingestion_freshness: {
        lag_seconds: 91,
      },
      config_diagnostics: {},
    });
    expect(summary.generatedAt).toBe("2026-05-08T13:00:00Z");
    expect(summary.guardrailStatus).toBe("degraded");
    expect(summary.schedulerStatus).toBe("stopped");
    expect(summary.pendingSqlTailRepairs).toBe(3);
    expect(summary.deadLetteredSqlTailRepairs).toBe(1);
    expect(summary.aggregateDeadLetterBacklog).toBe(2);
    expect(summary.ingestionLagSeconds).toBe(91);
  });
});

describe("formatDurationSeconds", () => {
  it("formats null and small values", () => {
    expect(formatDurationSeconds(null)).toBe("n/a");
    expect(formatDurationSeconds(9)).toBe("9s");
  });

  it("formats minute and hour ranges", () => {
    expect(formatDurationSeconds(90)).toBe("1.5m");
    expect(formatDurationSeconds(7200)).toBe("2.0h");
  });
});

describe("normalizeSchedulerJobs", () => {
  it("returns empty rows when payload or jobs are missing", () => {
    expect(normalizeSchedulerJobs(null)).toEqual([]);
    expect(
      normalizeSchedulerJobs({
        generated_at: "2026-05-08T13:00:00Z",
        topology: {},
        scheduler: {},
        replay_queue: {},
        ingestion_freshness: {},
        config_diagnostics: {},
      }),
    ).toEqual([]);
  });

  it("extracts scheduler job timing and failure status", () => {
    expect(
      normalizeSchedulerJobs({
        generated_at: "2026-05-08T13:00:00Z",
        topology: {},
        scheduler: {
          jobs: [
            {
              job_name: "retention",
              status: "failed",
              finished_at: "2026-05-08T13:00:00Z",
              next_scheduled_at: "2026-05-08T13:02:00Z",
              failure_reason: "RuntimeError",
            },
            {
              job_name: "alerts",
              status: "succeeded",
              finished_at: "2026-05-08T13:00:05Z",
              next_scheduled_at: "2026-05-08T13:01:05Z",
              failure_reason: null,
            },
          ],
        },
        replay_queue: {},
        ingestion_freshness: {},
        config_diagnostics: {},
      }),
    ).toEqual([
      {
        jobName: "retention",
        status: "failed",
        lastFinishedAt: "2026-05-08T13:00:00Z",
        nextScheduledAt: "2026-05-08T13:02:00Z",
        failureReason: "RuntimeError",
      },
      {
        jobName: "alerts",
        status: "succeeded",
        lastFinishedAt: "2026-05-08T13:00:05Z",
        nextScheduledAt: "2026-05-08T13:01:05Z",
        failureReason: null,
      },
    ]);
  });
});
