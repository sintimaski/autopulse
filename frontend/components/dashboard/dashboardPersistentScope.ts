import {
  GROUP_OPTIONS,
  LOGS_TABLE_SORT_KEY_SET,
  type GroupBy,
  type SortDir,
  type SortKey,
} from "./dashboardTypes";
import {
  buildScopedQuery,
  parseScopedQuery,
  type DashboardScopedQueryState,
} from "./dashboardQueryState";

const STORAGE_KEY = "lumonox.dashboard.session.v1";

const GROUP_VALUES = new Set<string>(GROUP_OPTIONS.map((o) => o.value));

const SORT_KEY_SET = LOGS_TABLE_SORT_KEY_SET;

export type PersistedLogsClientSlice = {
  groupBy: GroupBy;
  sortKey: SortKey;
  sortDir: SortDir;
  envTags: string[];
  serviceTags: string[];
};

export const DEFAULT_LOGS_VIEW_CLIENT: PersistedLogsClientSlice = {
  groupBy: "none",
  sortKey: "timestamp",
  sortDir: "desc",
  envTags: [],
  serviceTags: [],
};

/** v2: Diagnosis and Logs keep independent server-scope query strings. */
export type PersistedDashboardSession = {
  v: 2;
  diagnosisScopedQueryString: string;
  logsScopedQueryString: string;
  logsClient: PersistedLogsClientSlice;
};

type PersistedDashboardSessionV1 = {
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
  const sortDir =
    o.sortDir === "asc" || o.sortDir === "desc" || o.sortDir === "none" ? o.sortDir : "desc";
  const envTags = Array.isArray(o.envTags) ? o.envTags.filter((t): t is string => typeof t === "string") : [];
  const serviceTags = Array.isArray(o.serviceTags)
    ? o.serviceTags.filter((t): t is string => typeof t === "string")
    : [];
  return { groupBy, sortKey, sortDir, envTags, serviceTags };
}

function parseScopedFromQueryString(q: string): DashboardScopedQueryState {
  return parseScopedQuery(new URLSearchParams(q));
}

export function readPersistedDashboardSession(): {
  diagnosisScoped: DashboardScopedQueryState;
  logsScoped: DashboardScopedQueryState;
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
    const parsed = JSON.parse(raw) as Partial<PersistedDashboardSession> & Partial<PersistedDashboardSessionV1>;
    const logsClient =
      normalizeLogsClient(parsed.logsClient) ?? ({ ...DEFAULT_LOGS_VIEW_CLIENT } satisfies PersistedLogsClientSlice);

    if (parsed.v === 2 && typeof parsed.diagnosisScopedQueryString === "string" && typeof parsed.logsScopedQueryString === "string") {
      return {
        diagnosisScoped: parseScopedFromQueryString(parsed.diagnosisScopedQueryString),
        logsScoped: parseScopedFromQueryString(parsed.logsScopedQueryString),
        logsClient,
      };
    }
    if (parsed.v === 1 && typeof parsed.scopedQueryString === "string") {
      const shared = parseScopedFromQueryString(parsed.scopedQueryString);
      return {
        diagnosisScoped: shared,
        logsScoped: { ...shared },
        logsClient,
      };
    }
    return null;
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
  diagnosisScopedQueryString: string,
  logsScopedQueryString: string,
  logsClient: PersistedLogsClientSlice,
): PersistedDashboardSession {
  return {
    v: 2,
    diagnosisScopedQueryString,
    logsScopedQueryString,
    logsClient,
  };
}

/** Read v2 session from disk for merge-write; returns null if missing or invalid. */
export function readPersistedSessionRecord(): PersistedDashboardSession | null {
  if (typeof window === "undefined") {
    return null;
  }
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      return null;
    }
    const parsed = JSON.parse(raw) as Partial<PersistedDashboardSession> & Partial<PersistedDashboardSessionV1>;
    const logsClient =
      normalizeLogsClient(parsed.logsClient) ?? ({ ...DEFAULT_LOGS_VIEW_CLIENT } satisfies PersistedLogsClientSlice);

    if (parsed.v === 2 && typeof parsed.diagnosisScopedQueryString === "string" && typeof parsed.logsScopedQueryString === "string") {
      return {
        v: 2,
        diagnosisScopedQueryString: parsed.diagnosisScopedQueryString,
        logsScopedQueryString: parsed.logsScopedQueryString,
        logsClient,
      };
    }
    if (parsed.v === 1 && typeof parsed.scopedQueryString === "string") {
      const s = parsed.scopedQueryString;
      return {
        v: 2,
        diagnosisScopedQueryString: s,
        logsScopedQueryString: s,
        logsClient,
      };
    }
    return null;
  } catch {
    return null;
  }
}

/** Merge-update one route's scope string and write v2 session. */
export function mergePersistedScopedSession(
  routePath: string,
  scoped: DashboardScopedQueryState,
  logsClient: PersistedLogsClientSlice,
): void {
  const prior = readPersistedSessionRecord();
  const nextScoped = buildScopedQuery(scoped).toString();
  const diagnosisScopedQueryString =
    routePath === "/diagnosis" ? nextScoped : (prior?.diagnosisScopedQueryString ?? "");
  const logsScopedQueryString =
    routePath === "/logs" ? nextScoped : (prior?.logsScopedQueryString ?? "");
  writePersistedDashboardSession(
    buildPersistedSessionPayload(diagnosisScopedQueryString, logsScopedQueryString, logsClient),
  );
}
