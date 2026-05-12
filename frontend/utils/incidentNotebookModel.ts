export const INCIDENT_NOTEBOOK_STORAGE_VERSION = 1 as const;

export type IncidentNotebookCell =
  | { id: string; type: "markdown"; source: string }
  | { id: string; type: "text"; source: string }
  | { id: string; type: "sql"; source: string; rowLimit: number; applyTimeWindow: boolean }
  | { id: string; type: "divider" };

export type IncidentNotebookDocument = {
  version: typeof INCIDENT_NOTEBOOK_STORAGE_VERSION;
  cells: IncidentNotebookCell[];
};

const DEFAULT_SQL = [
  "SELECT",
  "  service_name,",
  "  environment,",
  "  COUNT(*) AS requests",
  "FROM scoped_events",
  "GROUP BY 1, 2",
  "ORDER BY requests DESC",
].join("\n");

const WELCOME_MD = [
  "## Incident notebook",
  "",
  "Add **markdown** for narrative, **notes** for freeform text, **SQL** cells that run against `scoped_events` (same engine as Query Explorer), and **dividers** to separate sections.",
  "",
  "Use the toolbar on each row to reorder or delete. Outputs are kept in memory until you refresh the page.",
].join("\n");

function randomId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `cell-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

export function newMarkdownCell(source = ""): IncidentNotebookCell {
  return { id: randomId(), type: "markdown", source };
}

export function newTextCell(source = ""): IncidentNotebookCell {
  return { id: randomId(), type: "text", source };
}

export function newSqlCell(
  source = DEFAULT_SQL,
  rowLimit = 200,
  applyTimeWindow = true,
): IncidentNotebookCell {
  return { id: randomId(), type: "sql", source, rowLimit, applyTimeWindow };
}

export function newDividerCell(): IncidentNotebookCell {
  return { id: randomId(), type: "divider" };
}

export function defaultIncidentNotebook(): IncidentNotebookDocument {
  return {
    version: INCIDENT_NOTEBOOK_STORAGE_VERSION,
    cells: [newMarkdownCell(WELCOME_MD), newSqlCell(DEFAULT_SQL, 200, true)],
  };
}

function isRecord(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

function parseCell(raw: unknown): IncidentNotebookCell | null {
  if (!isRecord(raw)) {
    return null;
  }
  const id = typeof raw.id === "string" && raw.id.trim() ? raw.id.trim() : null;
  const type = raw.type;
  if (!id || (type !== "markdown" && type !== "text" && type !== "sql" && type !== "divider")) {
    return null;
  }
  if (type === "divider") {
    return { id, type: "divider" };
  }
  if (type === "markdown" || type === "text") {
    return { id, type, source: typeof raw.source === "string" ? raw.source : "" };
  }
  const source = typeof raw.source === "string" ? raw.source : "";
  const rowLimitRaw = Number(raw.row_limit ?? raw.rowLimit);
  const rowLimit =
    Number.isFinite(rowLimitRaw) && rowLimitRaw > 0 ? Math.max(1, Math.min(500, Math.floor(rowLimitRaw))) : 200;
  const applyTimeWindow =
    typeof raw.apply_time_window === "boolean"
      ? raw.apply_time_window
      : typeof raw.applyTimeWindow === "boolean"
        ? raw.applyTimeWindow
        : true;
  return { id, type: "sql", source, rowLimit, applyTimeWindow };
}

export function parseIncidentNotebookJson(raw: string): IncidentNotebookDocument | null {
  let parsed: unknown;
  try {
    parsed = JSON.parse(raw) as unknown;
  } catch {
    return null;
  }
  if (!isRecord(parsed)) {
    return null;
  }
  if (parsed.version !== INCIDENT_NOTEBOOK_STORAGE_VERSION) {
    return null;
  }
  if (!Array.isArray(parsed.cells)) {
    return null;
  }
  const cells: IncidentNotebookCell[] = [];
  for (const item of parsed.cells) {
    const c = parseCell(item);
    if (c) {
      cells.push(c);
    }
  }
  if (cells.length === 0) {
    return null;
  }
  return { version: INCIDENT_NOTEBOOK_STORAGE_VERSION, cells };
}

export function serializeIncidentNotebook(doc: IncidentNotebookDocument): string {
  const payload = {
    version: doc.version,
    cells: doc.cells.map((c) => {
      if (c.type === "divider") {
        return { id: c.id, type: "divider" };
      }
      if (c.type === "sql") {
        return {
          id: c.id,
          type: "sql",
          source: c.source,
          row_limit: c.rowLimit,
          apply_time_window: c.applyTimeWindow,
        };
      }
      return { id: c.id, type: c.type, source: c.source };
    }),
  };
  return JSON.stringify(payload);
}

export function moveCell(cells: IncidentNotebookCell[], index: number, delta: -1 | 1): IncidentNotebookCell[] {
  const next = index + delta;
  if (next < 0 || next >= cells.length) {
    return cells;
  }
  const copy = [...cells];
  const [removed] = copy.splice(index, 1);
  copy.splice(next, 0, removed!);
  return copy;
}

export function removeCellAt(cells: IncidentNotebookCell[], index: number): IncidentNotebookCell[] {
  return cells.filter((_, i) => i !== index);
}
