import { describe, expect, it } from "vitest";

import {
  defaultIncidentNotebook,
  moveCell,
  parseIncidentNotebookJson,
  removeCellAt,
  serializeIncidentNotebook,
} from "./incidentNotebookModel";

describe("incidentNotebookModel", () => {
  it("round-trips serialize and parse", () => {
    const doc = defaultIncidentNotebook();
    const json = serializeIncidentNotebook(doc);
    const back = parseIncidentNotebookJson(json);
    expect(back).not.toBeNull();
    expect(back!.version).toBe(1);
    expect(back!.cells.length).toBe(doc.cells.length);
    expect(back!.cells.map((c) => c.type)).toEqual(doc.cells.map((c) => c.type));
  });

  it("parses sql row_limit alias", () => {
    const raw = JSON.stringify({
      version: 1,
      cells: [
        {
          id: "a",
          type: "sql",
          source: "SELECT 1 FROM scoped_events",
          row_limit: 42,
          apply_time_window: false,
        },
      ],
    });
    const parsed = parseIncidentNotebookJson(raw);
    expect(parsed).not.toBeNull();
    const sql = parsed!.cells[0];
    expect(sql?.type).toBe("sql");
    if (sql?.type === "sql") {
      expect(sql.rowLimit).toBe(42);
      expect(sql.applyTimeWindow).toBe(false);
    }
  });

  it("parses scope cells", () => {
    const raw = JSON.stringify({
      version: 1,
      cells: [{ id: "scope-1", type: "scope", source: "Scope notes" }],
    });
    const parsed = parseIncidentNotebookJson(raw);
    expect(parsed).not.toBeNull();
    expect(parsed!.cells[0]).toEqual({ id: "scope-1", type: "scope", source: "Scope notes", filters: null });
  });

  it("parses legacy text cells as note", () => {
    const raw = JSON.stringify({
      version: 1,
      cells: [{ id: "t1", type: "text", source: "hello" }],
    });
    const parsed = parseIncidentNotebookJson(raw);
    expect(parsed).not.toBeNull();
    expect(parsed!.cells[0]).toEqual({ id: "t1", type: "note", source: "hello" });
  });

  it("parses scope with filters and checklist", () => {
    const filters = {
      isAbsoluteWindow: false,
      windowMinutes: 30,
      windowFromTimestamp: "",
      windowToTimestamp: "",
      method: "GET",
      statusClass: "5",
      minLatencyMs: "",
      maxLatencyMs: "",
      pathQuery: "/api",
      serverEnvironmentQuery: "",
      serverServiceQuery: "",
      requestLimit: 100,
      requestPage: 0,
      errorGroupLimit: 25,
      errorGroupPage: 0,
      errorGroupSort: "last_seen" as const,
      correlationRequestId: "",
      sqlFilterApplied: "",
      sqlFilterEnabled: false,
    };
    const raw = JSON.stringify({
      version: 1,
      cells: [
        { id: "s1", type: "scope", source: "n", filters },
        {
          id: "c1",
          type: "checklist",
          title: "T",
          items: [{ id: "i1", text: "one", checked: true }],
        },
        { id: "l1", type: "link", label: "L", href: "https://a.example", note: "" },
      ],
    });
    const parsed = parseIncidentNotebookJson(raw);
    expect(parsed).not.toBeNull();
    expect(parsed!.cells.map((c) => c.type)).toEqual(["scope", "checklist", "link"]);
  });

  it("moveCell and removeCellAt", () => {
    const doc = defaultIncidentNotebook();
    const [a, b] = doc.cells;
    const moved = moveCell([a!, b!], 0, 1);
    expect(moved[0]?.id).toBe(b!.id);
    const removed = removeCellAt(moved, 0);
    expect(removed).toHaveLength(1);
  });
});
