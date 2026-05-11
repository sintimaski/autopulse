import { describe, expect, it } from "vitest";

import { JOB_FAILURES_STARTER_SQL, QUERY_EXPLORER_JOB_FAILURES_PRESET } from "./queryExplorerPresets";

describe("queryExplorerPresets", () => {
  it("job failures preset is stable and scoped to scoped_events", () => {
    expect(QUERY_EXPLORER_JOB_FAILURES_PRESET).toBe("job_failures");
    expect(JOB_FAILURES_STARTER_SQL).toContain("FROM scoped_events");
    expect(JOB_FAILURES_STARTER_SQL.toLowerCase()).toContain("type");
    expect(JOB_FAILURES_STARTER_SQL).toContain("status_code >= 500");
  });
});
