import { describe, expect, it } from "vitest";

import { RUNBOOK_ALERTS_CMD, RUNBOOK_RETENTION_CMD } from "../components/dashboard/dashboardTypes";

describe("dashboard runbook strings", () => {
  it("documents alerts job stdout semantics and includes the uv command", () => {
    expect(RUNBOOK_ALERTS_CMD).toContain("stdout: number of alert dispatches");
    expect(RUNBOOK_ALERTS_CMD).toContain("uv run python -m lumonox_backend.jobs alerts-once");
    expect(RUNBOOK_ALERTS_CMD).toContain("ALERTS_ENABLED");
  });

  it("includes retention job command", () => {
    expect(RUNBOOK_RETENTION_CMD).toContain("uv run python -m lumonox_backend.jobs retention-once");
  });
});
