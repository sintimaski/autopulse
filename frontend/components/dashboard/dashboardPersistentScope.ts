import {
  GROUP_OPTIONS,
  type GroupBy,
  type SortDir,
  type SortKey,
} from "./dashboardTypes";
import {
  buildScopedQuery,
  parseScopedQuery,
  type DashboardScopedQueryState,
} from "./dashboardQueryState";

const STORAGE_KEY = "autopulse.dashboard.session.v1";

const GROUP_VALUES = new Set<string>(GROUP_OPTIONS.map((o) => o.value));

const SORT_KEYS: SortKey[] = [
  "timestamp",
  "method",
  "path",
  "status_code",
  "latency_ms",
  "service_name",
  "environment",
];

const SORT_KEY_SET = new Set<string>(SORT_KEYS);

export type PersistedLogsClientSlice = {
  groupBy: GroupBy;
  sortKey: SortKey;
  sortDir: SortDir;
  envTags: string[];
  serviceTags: string[];
};

export type PersistedDashboardSession = {
  v: 1;
  scopedQueryString: string;
  logsClient: PersistedLogsClientSlice;
};

function normalizeLogsClient(raw: unknown): PersistedLogsClientSlice | null {
  if (!raw || typeof raw !== "object") {
    return null;
  }
  const o = raw as Record<string, unknown>;
  const groupBy = typeof o.groupBy === "string" && GROUP_VALUES.has(o.groupBy) ? (o.groupBy as GroupBy) : "none";
  const sortKey =
    typeof o.sortKey === "string" && SORT_KEY_SET.has(o.sortKey) ? (o.sortKey as SortKey) : "timestamp";
  const sortDir = o.sortDir === "asc" || o.sortDir === "desc" ? o.sortDir : "desc";
  const envTags = Array.isArray(o.envTags) ? o.envTags.filter((t): t is string => typeof t === "string") : [];
  const serviceTags = Array.isArray(o.serviceTags)
    ? o.serviceTags.filter((t): t is string => typeof t === "string")
    : [];
  return { groupBy, sortKey, sortDir, envTags, serviceTags };
}

export function readPersistedDashboardSession(): {
  scoped: DashboardScopedQueryState;
  logsClient: PersistedLogsClientSlice;
} | null {
  if (typeof window === "undefined") {
    return null;
  }
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      return null;
    }
    const parsed = JSON.parse(raw) as Partial<PersistedDashboardSession>;
    if (parsed.v !== 1 || typeof parsed.scopedQueryString !== "string") {
      return null;
    }
    const scoped = parseScopedQuery(new URLSearchParams(parsed.scopedQueryString));
    const logsClient =
      normalizeLogsClient(parsed.logsClient) ??
      ({
        groupBy: "none",
        sortKey: "timestamp",
        sortDir: "desc",
        envTags: [],
        serviceTags: [],
      } satisfies PersistedLogsClientSlice);
    return { scoped, logsClient };
  } catch {
    return null;
  }
}

export function writePersistedDashboardSession(payload: PersistedDashboardSession): void {
  if (typeof window === "undefined") {
    return;
  }
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
  } catch {
    // ignore quota / private mode
  }
}

export function buildPersistedSessionPayload(
  scoped: DashboardScopedQueryState,
  logsClient: PersistedLogsClientSlice,
): PersistedDashboardSession {
  return {
    v: 1,
    scopedQueryString: buildScopedQuery(scoped).toString(),
    logsClient,
  };
}
