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

  it("moveCell and removeCellAt", () => {
    const doc = defaultIncidentNotebook();
    const [a, b] = doc.cells;
    const moved = moveCell([a!, b!], 0, 1);
    expect(moved[0]?.id).toBe(b!.id);
    const removed = removeCellAt(moved, 0);
    expect(removed).toHaveLength(1);
  });
});
