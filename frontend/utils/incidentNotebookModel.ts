export const INCIDENT_NOTEBOOK_STORAGE_VERSION = 1 as const;

/** Captured dashboard scope (same fields as ``DashboardScopedQueryState``). */
export type IncidentScopeCapturedState = {
  isAbsoluteWindow: boolean;
  windowMinutes: number;
  windowFromTimestamp: string;
  windowToTimestamp: string;
  method: string;
  statusClass: string;
  minLatencyMs: string;
  maxLatencyMs: string;
  pathQuery: string;
  serverEnvironmentQuery: string;
  serverServiceQuery: string;
  requestLimit: number;
  requestPage: number;
  errorGroupLimit: number;
  errorGroupPage: number;
  errorGroupSort: "last_seen" | "count";
  correlationRequestId: string;
  sqlFilterApplied: string;
  sqlFilterEnabled: boolean;
};

export function defaultEmptyIncidentScope(): IncidentScopeCapturedState {
  return {
    isAbsoluteWindow: false,
    windowMinutes: 60,
    windowFromTimestamp: "",
    windowToTimestamp: "",
    method: "ALL",
    statusClass: "ALL",
    minLatencyMs: "",
    maxLatencyMs: "",
    pathQuery: "",
    serverEnvironmentQuery: "",
    serverServiceQuery: "",
    requestLimit: 100,
    requestPage: 0,
    errorGroupLimit: 25,
    errorGroupPage: 0,
    errorGroupSort: "last_seen",
    correlationRequestId: "",
    sqlFilterApplied: "",
    sqlFilterEnabled: false,
  };
}

export type IncidentChecklistItem = { id: string; text: string; checked: boolean };

export type IncidentNotebookCell =
  | { id: string; type: "markdown"; source: string }
  | { id: string; type: "text"; source: string }
  | { id: string; type: "sql"; source: string; rowLimit: number; applyTimeWindow: boolean }
  | { id: string; type: "scope"; source: string; filters: IncidentScopeCapturedState | null }
  | { id: string; type: "checklist"; title: string; items: IncidentChecklistItem[] }
  | { id: string; type: "link"; label: string; href: string; note: string }
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
  "Use **markdown** (rendered), **scope** cells to capture or apply investigation filters, **SQL** on `scoped_events`, **checklists**, and **links**.",
  "",
  "Reorder with the toolbar on each row. SQL outputs stay in memory until refresh.",
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

export function newScopeCell(source = "", filters: IncidentScopeCapturedState | null = null): IncidentNotebookCell {
  return { id: randomId(), type: "scope", source, filters };
}

export function newChecklistCell(title = "", items: IncidentChecklistItem[] = []): IncidentNotebookCell {
  return {
    id: randomId(),
    type: "checklist",
    title,
    items:
      items.length > 0
        ? items
        : [{ id: randomId(), text: "First item", checked: false }],
  };
}

export function newLinkCell(label = "", href = "", note = ""): IncidentNotebookCell {
  return { id: randomId(), type: "link", label, href, note };
}

export function defaultIncidentNotebook(): IncidentNotebookDocument {
  return {
    version: INCIDENT_NOTEBOOK_STORAGE_VERSION,
    cells: [newScopeCell(), newMarkdownCell(WELCOME_MD), newSqlCell(DEFAULT_SQL, 200, true)],
  };
}

function isRecord(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

function parseScopeFilters(raw: unknown): IncidentScopeCapturedState | null {
  if (raw === null || raw === undefined) {
    return null;
  }
  if (!isRecord(raw)) {
    return null;
  }
  const sort = raw.errorGroupSort === "count" ? "count" : "last_seen";
  return {
    isAbsoluteWindow: Boolean(raw.isAbsoluteWindow),
    windowMinutes: typeof raw.windowMinutes === "number" ? raw.windowMinutes : 60,
    windowFromTimestamp: typeof raw.windowFromTimestamp === "string" ? raw.windowFromTimestamp : "",
    windowToTimestamp: typeof raw.windowToTimestamp === "string" ? raw.windowToTimestamp : "",
    method: typeof raw.method === "string" ? raw.method : "ALL",
    statusClass: typeof raw.statusClass === "string" ? raw.statusClass : "ALL",
    minLatencyMs: typeof raw.minLatencyMs === "string" ? raw.minLatencyMs : "",
    maxLatencyMs: typeof raw.maxLatencyMs === "string" ? raw.maxLatencyMs : "",
    pathQuery: typeof raw.pathQuery === "string" ? raw.pathQuery : "",
    serverEnvironmentQuery: typeof raw.serverEnvironmentQuery === "string" ? raw.serverEnvironmentQuery : "",
    serverServiceQuery: typeof raw.serverServiceQuery === "string" ? raw.serverServiceQuery : "",
    requestLimit: typeof raw.requestLimit === "number" ? raw.requestLimit : 100,
    requestPage: typeof raw.requestPage === "number" ? raw.requestPage : 0,
    errorGroupLimit: typeof raw.errorGroupLimit === "number" ? raw.errorGroupLimit : 25,
    errorGroupPage: typeof raw.errorGroupPage === "number" ? raw.errorGroupPage : 0,
    errorGroupSort: sort,
    correlationRequestId: typeof raw.correlationRequestId === "string" ? raw.correlationRequestId : "",
    sqlFilterApplied: typeof raw.sqlFilterApplied === "string" ? raw.sqlFilterApplied : "",
    sqlFilterEnabled: Boolean(raw.sqlFilterEnabled),
  };
}

function parseChecklistItems(raw: unknown): IncidentChecklistItem[] | null {
  if (!Array.isArray(raw)) {
    return null;
  }
  const items: IncidentChecklistItem[] = [];
  for (const row of raw) {
    if (!isRecord(row)) {
      continue;
    }
    const id = typeof row.id === "string" && row.id.trim() ? row.id.trim() : randomId();
    const text = typeof row.text === "string" ? row.text : "";
    const checked = Boolean(row.checked);
    items.push({ id, text, checked });
  }
  return items.length ? items : null;
}

function parseCell(raw: unknown): IncidentNotebookCell | null {
  if (!isRecord(raw)) {
    return null;
  }
  const id = typeof raw.id === "string" && raw.id.trim() ? raw.id.trim() : null;
  const type = raw.type;
  if (
    !id ||
    (type !== "markdown" &&
      type !== "text" &&
      type !== "sql" &&
      type !== "scope" &&
      type !== "checklist" &&
      type !== "link" &&
      type !== "divider")
  ) {
    return null;
  }
  if (type === "divider") {
    return { id, type: "divider" };
  }
  if (type === "markdown" || type === "text") {
    return { id, type, source: typeof raw.source === "string" ? raw.source : "" };
  }
  if (type === "scope") {
    const filters = parseScopeFilters(raw.filters);
    return { id, type: "scope", source: typeof raw.source === "string" ? raw.source : "", filters };
  }
  if (type === "checklist") {
    const title = typeof raw.title === "string" ? raw.title : "";
    const items = parseChecklistItems(raw.items) ?? [{ id: randomId(), text: "", checked: false }];
    return { id, type: "checklist", title, items };
  }
  if (type === "link") {
    return {
      id,
      type: "link",
      label: typeof raw.label === "string" ? raw.label : "",
      href: typeof raw.href === "string" ? raw.href : "",
      note: typeof raw.note === "string" ? raw.note : "",
    };
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
      if (c.type === "scope") {
        return {
          id: c.id,
          type: "scope",
          source: c.source,
          filters: c.filters,
        };
      }
      if (c.type === "checklist") {
        return {
          id: c.id,
          type: "checklist",
          title: c.title,
          items: c.items.map((it) => ({ id: it.id, text: it.text, checked: it.checked })),
        };
      }
      if (c.type === "link") {
        return { id: c.id, type: "link", label: c.label, href: c.href, note: c.note };
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
