"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";

import {
  computeOperationalSignals,
  M5_ALERT_DEFAULTS,
  resolveSparklineSeries,
  type OverviewBucket,
} from "../../utils/dashboardData";
import {
  buildDashboardFetchError,
  buildDashboardNetworkError,
  type DashboardFetchResult,
} from "../../utils/dashboardFetchErrors";
import {
  apiBaseUrl,
  apiKey,
  compareValues,
  ERROR_GROUP_LIMIT_OPTIONS,
  GROUP_OPTIONS,
  METHOD_OPTIONS,
  REQUEST_LIMIT_OPTIONS,
  RUNBOOK_ALERTS_CMD,
  RUNBOOK_RETENTION_CMD,
  STATUS_CLASS_OPTIONS,
  WINDOW_OPTIONS,
  type AlertSettings,
  type ErrorGroupItem,
  type ErrorGroupsResponse,
  type GroupBy,
  type OverviewResponse,
  type RequestItem,
  type RequestsResponse,
  type SortDir,
  type SortKey,
} from "./dashboardTypes";

export type DashboardDataContextValue = {
  hasApiKey: boolean;
  windowMinutes: number;
  method: string;
  statusClass: string;
  requestLimit: number;
  requestPage: number;
  errorGroupLimit: number;
  errorGroupPage: number;
  minLatencyMs: string;
  maxLatencyMs: string;
  serverServiceQuery: string;
  serverEnvironmentQuery: string;
  pathQuery: string;
  groupBy: GroupBy;
  sortKey: SortKey;
  sortDir: SortDir;
  envTags: Set<string>;
  serviceTags: Set<string>;
  overview: OverviewResponse | null;
  requests: RequestsResponse | null;
  errorGroups: ErrorGroupsResponse | null;
  alertSettings: AlertSettings | null;
  errorGroupSort: "last_seen" | "count";
  loading: boolean;
  errorMessage: string | null;
  refreshToken: number;
  runbookMessage: string | null;
  alertSettingsMessage: string | null;
  alertSettingsSaving: boolean;
  expandedRequestIds: Set<string>;
  setRequestLimit: (n: number) => void;
  setRequestPage: React.Dispatch<React.SetStateAction<number>>;
  setErrorGroupLimit: (n: number) => void;
  setErrorGroupPage: React.Dispatch<React.SetStateAction<number>>;
  setMinLatencyMs: React.Dispatch<React.SetStateAction<string>>;
  setMaxLatencyMs: React.Dispatch<React.SetStateAction<string>>;
  setServerServiceQuery: React.Dispatch<React.SetStateAction<string>>;
  setServerEnvironmentQuery: React.Dispatch<React.SetStateAction<string>>;
  setPathQuery: React.Dispatch<React.SetStateAction<string>>;
  setGroupBy: React.Dispatch<React.SetStateAction<GroupBy>>;
  setErrorGroupSort: (s: "last_seen" | "count") => void;
  setRefreshToken: React.Dispatch<React.SetStateAction<number>>;
  onServerWindowChange: (minutes: number) => void;
  onServerMethodChange: (value: string) => void;
  onServerStatusClassChange: (value: string) => void;
  toggleEnv: (value: string) => void;
  toggleService: (value: string) => void;
  clearClientFilters: () => void;
  copyRunbookCommand: (command: string, label: string) => Promise<void>;
  saveAlertSettings: (next: AlertSettings) => Promise<boolean>;
  updateAlertSettingsDraft: (next: AlertSettings) => void;
  toggleRequestRow: (id: string) => void;
  onSortHeader: (key: SortKey) => void;
  rawItems: RequestItem[];
  availableEnvironments: string[];
  availableServices: string[];
  filteredSorted: RequestItem[];
  topFailingRoutes: [string, number][];
  recentErrorsPreview: ErrorGroupItem[];
  displayedErrorGroups: ErrorGroupItem[];
  grouped: { key: string; label: string; items: RequestItem[] }[];
  sparklineSeries: OverviewBucket[];
  operationalSignals: ReturnType<typeof computeOperationalSignals>;
  WINDOW_OPTIONS: typeof WINDOW_OPTIONS;
  METHOD_OPTIONS: typeof METHOD_OPTIONS;
  STATUS_CLASS_OPTIONS: typeof STATUS_CLASS_OPTIONS;
  REQUEST_LIMIT_OPTIONS: typeof REQUEST_LIMIT_OPTIONS;
  ERROR_GROUP_LIMIT_OPTIONS: typeof ERROR_GROUP_LIMIT_OPTIONS;
  GROUP_OPTIONS: typeof GROUP_OPTIONS;
  RUNBOOK_ALERTS_CMD: typeof RUNBOOK_ALERTS_CMD;
  RUNBOOK_RETENTION_CMD: typeof RUNBOOK_RETENTION_CMD;
  M5_ALERT_DEFAULTS: typeof M5_ALERT_DEFAULTS;
};

const DashboardDataContext = createContext<DashboardDataContextValue | null>(null);

export function useDashboardData(): DashboardDataContextValue {
  const ctx = useContext(DashboardDataContext);
  if (!ctx) {
    throw new Error("useDashboardData must be used within DashboardDataProvider");
  }
  return ctx;
}

export function DashboardDataProvider({ children }: { children: ReactNode }) {
  const hasApiKey = Boolean(apiKey);

  const [windowMinutes, setWindowMinutes] = useState(60);
  const [method, setMethod] = useState("ALL");
  const [statusClass, setStatusClass] = useState("ALL");
  const [requestLimit, setRequestLimit] = useState(100);
  const [requestPage, setRequestPage] = useState(0);
  const [errorGroupLimit, setErrorGroupLimit] = useState(25);
  const [errorGroupPage, setErrorGroupPage] = useState(0);
  const [minLatencyMs, setMinLatencyMs] = useState("");
  const [maxLatencyMs, setMaxLatencyMs] = useState("");
  const [serverServiceQuery, setServerServiceQuery] = useState("");
  const [serverEnvironmentQuery, setServerEnvironmentQuery] = useState("");
  const [pathQuery, setPathQuery] = useState("");
  const [groupBy, setGroupBy] = useState<GroupBy>("none");
  const [sortKey, setSortKey] = useState<SortKey>("timestamp");
  const [sortDir, setSortDir] = useState<SortDir>("desc");
  const [envTags, setEnvTags] = useState<Set<string>>(new Set());
  const [serviceTags, setServiceTags] = useState<Set<string>>(new Set());
  const [overview, setOverview] = useState<OverviewResponse | null>(null);
  const [requests, setRequests] = useState<RequestsResponse | null>(null);
  const [errorGroups, setErrorGroups] = useState<ErrorGroupsResponse | null>(null);
  const [alertSettings, setAlertSettings] = useState<AlertSettings | null>(null);
  const [errorGroupSort, setErrorGroupSort] = useState<"last_seen" | "count">("last_seen");
  const [loading, setLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [refreshToken, setRefreshToken] = useState(0);
  const [runbookMessage, setRunbookMessage] = useState<string | null>(null);
  const [alertSettingsMessage, setAlertSettingsMessage] = useState<string | null>(null);
  const [alertSettingsSaving, setAlertSettingsSaving] = useState(false);
  const runbookTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [expandedRequestIds, setExpandedRequestIds] = useState<Set<string>>(() => new Set());

  const toIsoWindow = useMemo(() => {
    const to = new Date();
    const from = new Date(to.getTime() - windowMinutes * 60 * 1000);
    return { from: from.toISOString(), to: to.toISOString() };
  }, [windowMinutes]);

  useEffect(() => {
    if (!apiKey) {
      return;
    }

    const run = async () => {
      setLoading(true);
      setErrorMessage(null);
      try {
        const headers = { Authorization: `Bearer ${apiKey}` };
        const overviewParams = new URLSearchParams({
          from_timestamp: toIsoWindow.from,
          to_timestamp: toIsoWindow.to,
        });

        const requestsParams = new URLSearchParams({
          from_timestamp: toIsoWindow.from,
          to_timestamp: toIsoWindow.to,
          limit: String(requestLimit),
          offset: String(requestPage * requestLimit),
        });
        if (method !== "ALL") {
          requestsParams.set("method", method);
        }
        if (statusClass !== "ALL") {
          requestsParams.set("status_class", statusClass);
        }
        const minLatency = Number(minLatencyMs);
        if (minLatencyMs.trim() !== "" && Number.isFinite(minLatency) && minLatency >= 0) {
          requestsParams.set("min_latency_ms", String(minLatency));
        }
        const maxLatency = Number(maxLatencyMs);
        if (maxLatencyMs.trim() !== "" && Number.isFinite(maxLatency) && maxLatency >= 0) {
          requestsParams.set("max_latency_ms", String(maxLatency));
        }
        const serverPath = pathQuery.trim();
        if (serverPath) {
          requestsParams.set("path_contains", serverPath);
        }
        const envCsv = serverEnvironmentQuery
          .split(",")
          .map((v) => v.trim())
          .filter(Boolean)
          .join(",");
        if (envCsv) {
          requestsParams.set("environments", envCsv);
        }
        const serviceCsv = serverServiceQuery
          .split(",")
          .map((v) => v.trim())
          .filter(Boolean)
          .join(",");
        if (serviceCsv) {
          requestsParams.set("services", serviceCsv);
        }

        const errorGroupsParams = new URLSearchParams({
          from_timestamp: toIsoWindow.from,
          to_timestamp: toIsoWindow.to,
          limit: String(errorGroupLimit),
          offset: String(errorGroupPage * errorGroupLimit),
        });

        const results = (await Promise.all([
          fetch(`${apiBaseUrl}/dashboard/overview?${overviewParams.toString()}`, { headers }),
          fetch(`${apiBaseUrl}/dashboard/requests?${requestsParams.toString()}`, { headers }),
          fetch(`${apiBaseUrl}/dashboard/error-groups?${errorGroupsParams.toString()}`, {
            headers,
          }),
          fetch(`${apiBaseUrl}/dashboard/alert-settings`, { headers }),
        ]).then(
          ([
            overviewResponse,
            requestsResponse,
            errorGroupsResponse,
            alertSettingsResponse,
          ]) => [
          { endpoint: "overview", response: overviewResponse },
          { endpoint: "requests", response: requestsResponse },
          { endpoint: "error-groups", response: errorGroupsResponse },
          { endpoint: "alert-settings", response: alertSettingsResponse },
          ],
        )) as DashboardFetchResult[];

        const fetchError = buildDashboardFetchError(results);
        if (fetchError) {
          throw new Error(fetchError);
        }

        const [overviewData, requestsData, errorGroupsData, alertSettingsData] = (await Promise.all(
          results.map(async ({ response }) => response.json()),
        )) as [OverviewResponse, RequestsResponse, ErrorGroupsResponse, AlertSettings];
        setOverview(overviewData);
        setRequests(requestsData);
        setErrorGroups(errorGroupsData);
        setAlertSettings(alertSettingsData);
      } catch (error) {
        setErrorMessage(buildDashboardNetworkError(error));
      } finally {
        setLoading(false);
      }
    };

    void run();
  }, [
    method,
    statusClass,
    toIsoWindow,
    refreshToken,
    requestLimit,
    requestPage,
    errorGroupLimit,
    errorGroupPage,
    minLatencyMs,
    maxLatencyMs,
    pathQuery,
    serverEnvironmentQuery,
    serverServiceQuery,
  ]);

  useEffect(() => {
    return () => {
      if (runbookTimer.current) {
        clearTimeout(runbookTimer.current);
      }
    };
  }, []);

  const rawItems = useMemo(() => requests?.items ?? [], [requests]);

  const onServerWindowChange = useCallback((minutes: number) => {
    setWindowMinutes(minutes);
    setRequestPage(0);
    setErrorGroupPage(0);
  }, []);

  const onServerMethodChange = useCallback((value: string) => {
    setMethod(value);
    setRequestPage(0);
    setErrorGroupPage(0);
  }, []);

  const onServerStatusClassChange = useCallback((value: string) => {
    setStatusClass(value);
    setRequestPage(0);
    setErrorGroupPage(0);
  }, []);

  const availableEnvironments = useMemo(
    () => [...new Set(rawItems.map((i) => i.environment))].sort(),
    [rawItems],
  );
  const availableServices = useMemo(
    () => [...new Set(rawItems.map((i) => i.service_name))].sort(),
    [rawItems],
  );

  const toggleEnv = useCallback((value: string) => {
    setEnvTags((prev) => {
      const next = new Set(prev);
      if (next.has(value)) {
        next.delete(value);
      } else {
        next.add(value);
      }
      return next;
    });
  }, []);

  const toggleService = useCallback((value: string) => {
    setServiceTags((prev) => {
      const next = new Set(prev);
      if (next.has(value)) {
        next.delete(value);
      } else {
        next.add(value);
      }
      return next;
    });
  }, []);

  const clearClientFilters = useCallback(() => {
    setPathQuery("");
    setMinLatencyMs("");
    setMaxLatencyMs("");
    setServerServiceQuery("");
    setServerEnvironmentQuery("");
    setEnvTags(new Set());
    setServiceTags(new Set());
    setGroupBy("none");
    setSortKey("timestamp");
    setSortDir("desc");
  }, []);

  const copyRunbookCommand = useCallback(async (command: string, label: string) => {
    try {
      await navigator.clipboard.writeText(command);
      if (runbookTimer.current) {
        clearTimeout(runbookTimer.current);
      }
      setRunbookMessage(`${label} copied to clipboard.`);
      runbookTimer.current = setTimeout(() => setRunbookMessage(null), 2800);
    } catch {
      setRunbookMessage("Clipboard unavailable — copy the command text manually.");
    }
  }, []);

  const saveAlertSettings = useCallback(
    async (next: AlertSettings): Promise<boolean> => {
      if (!apiKey) {
        return false;
      }
      setAlertSettingsSaving(true);
      setAlertSettingsMessage(null);
      try {
        const response = await fetch(`${apiBaseUrl}/dashboard/alert-settings`, {
          method: "PUT",
          headers: {
            Authorization: `Bearer ${apiKey}`,
            "Content-Type": "application/json",
          },
          body: JSON.stringify(next),
        });
        if (!response.ok) {
          throw new Error(`alert-settings update failed (${response.status})`);
        }
        const updated = (await response.json()) as AlertSettings;
        setAlertSettings(updated);
        setAlertSettingsMessage("Alert settings saved.");
        return true;
      } catch {
        setAlertSettingsMessage("Failed to save alert settings. Try again.");
        return false;
      } finally {
        setAlertSettingsSaving(false);
      }
    },
    [],
  );

  const updateAlertSettingsDraft = useCallback((next: AlertSettings) => {
    setAlertSettings(next);
  }, []);

  const toggleRequestRow = useCallback((id: string) => {
    setExpandedRequestIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  }, []);

  const onSortHeader = useCallback(
    (key: SortKey) => {
      if (sortKey === key) {
        setSortDir((d) => (d === "asc" ? "desc" : "asc"));
      } else {
        setSortKey(key);
        setSortDir(key === "timestamp" || key === "status_code" || key === "latency_ms" ? "desc" : "asc");
      }
    },
    [sortKey],
  );

  const filteredSorted = useMemo(() => {
    const q = pathQuery.trim().toLowerCase();
    let rows = rawItems.filter((item) => {
      if (q && !item.path.toLowerCase().includes(q)) {
        return false;
      }
      if (envTags.size > 0 && !envTags.has(item.environment)) {
        return false;
      }
      if (serviceTags.size > 0 && !serviceTags.has(item.service_name)) {
        return false;
      }
      return true;
    });

    rows = [...rows].sort((a, b) => {
      const va = a[sortKey];
      const vb = b[sortKey];
      if (sortKey === "timestamp") {
        const ta = new Date(va as string).getTime();
        const tb = new Date(vb as string).getTime();
        return sortDir === "asc" ? ta - tb : tb - ta;
      }
      return compareValues(va as string | number, vb as string | number, sortDir);
    });

    return rows;
  }, [rawItems, pathQuery, envTags, serviceTags, sortKey, sortDir]);

  const topFailingRoutes = useMemo(() => {
    const counts = new Map<string, number>();
    for (const item of rawItems) {
      if (item.status_code >= 500) {
        counts.set(item.path, (counts.get(item.path) ?? 0) + 1);
      }
    }
    return [...counts.entries()]
      .sort((a, b) => b[1] - a[1])
      .slice(0, 5);
  }, [rawItems]);

  const recentErrorsPreview = useMemo(() => {
    const items = errorGroups?.items;
    if (!items?.length) {
      return [];
    }
    return [...items]
      .sort(
        (a, b) =>
          new Date(b.last_seen).getTime() -
          new Date(a.last_seen).getTime(),
      )
      .slice(0, 5);
  }, [errorGroups]);

  const displayedErrorGroups = useMemo(() => {
    const source = errorGroups?.items;
    if (!source?.length) {
      return [];
    }
    const items = [...source];
    if (errorGroupSort === "count") {
      items.sort((a, b) => {
        if (b.count !== a.count) {
          return b.count - a.count;
        }
        return new Date(b.last_seen).getTime() - new Date(a.last_seen).getTime();
      });
    } else {
      items.sort((a, b) => {
        const t = new Date(b.last_seen).getTime() - new Date(a.last_seen).getTime();
        if (t !== 0) {
          return t;
        }
        return b.count - a.count;
      });
    }
    return items;
  }, [errorGroups, errorGroupSort]);

  const grouped = useMemo(() => {
    if (groupBy === "none") {
      return [{ key: "all", label: "All traffic", items: filteredSorted }];
    }
    const map = new Map<string, RequestItem[]>();
    for (const item of filteredSorted) {
      const k = String(item[groupBy as keyof RequestItem] ?? "");
      if (!map.has(k)) {
        map.set(k, []);
      }
      map.get(k)!.push(item);
    }
    const keys = [...map.keys()].sort((a, b) => a.localeCompare(b));
    return keys.map((key) => ({
      key,
      label: key || "(empty)",
      items: map.get(key)!,
    }));
  }, [filteredSorted, groupBy]);

  const sparklineSeries = useMemo(
    () =>
      resolveSparklineSeries(overview, requests, {
        // When server-side filters are active, derive buckets from the filtered request page
        // so chart + cards reflect selected method/status.
        preferRequests: method !== "ALL" || statusClass !== "ALL",
      }),
    [overview, requests, method, statusClass],
  );

  const operationalSignals = useMemo(
    () => computeOperationalSignals(overview, M5_ALERT_DEFAULTS),
    [overview],
  );

  const value = useMemo(
    (): DashboardDataContextValue => ({
      hasApiKey,
      windowMinutes,
      method,
      statusClass,
      requestLimit,
      requestPage,
      errorGroupLimit,
      errorGroupPage,
      minLatencyMs,
      maxLatencyMs,
      serverServiceQuery,
      serverEnvironmentQuery,
      pathQuery,
      groupBy,
      sortKey,
      sortDir,
      envTags,
      serviceTags,
      overview,
      requests,
      errorGroups,
      alertSettings,
      errorGroupSort,
      loading,
      errorMessage,
      refreshToken,
      runbookMessage,
      alertSettingsMessage,
      alertSettingsSaving,
      expandedRequestIds,
      setRequestLimit,
      setRequestPage,
      setErrorGroupLimit,
      setErrorGroupPage,
      setMinLatencyMs,
      setMaxLatencyMs,
      setServerServiceQuery,
      setServerEnvironmentQuery,
      setPathQuery,
      setGroupBy,
      setErrorGroupSort,
      setRefreshToken,
      onServerWindowChange,
      onServerMethodChange,
      onServerStatusClassChange,
      toggleEnv,
      toggleService,
      clearClientFilters,
      copyRunbookCommand,
      saveAlertSettings,
      updateAlertSettingsDraft,
      toggleRequestRow,
      onSortHeader,
      rawItems,
      availableEnvironments,
      availableServices,
      filteredSorted,
      topFailingRoutes,
      recentErrorsPreview,
      displayedErrorGroups,
      grouped,
      sparklineSeries,
      operationalSignals,
      WINDOW_OPTIONS,
      METHOD_OPTIONS,
      STATUS_CLASS_OPTIONS,
      REQUEST_LIMIT_OPTIONS,
      ERROR_GROUP_LIMIT_OPTIONS,
      GROUP_OPTIONS,
      RUNBOOK_ALERTS_CMD,
      RUNBOOK_RETENTION_CMD,
      M5_ALERT_DEFAULTS,
    }),
    [
      hasApiKey,
      windowMinutes,
      method,
      statusClass,
      requestLimit,
      requestPage,
      errorGroupLimit,
      errorGroupPage,
      minLatencyMs,
      maxLatencyMs,
      serverServiceQuery,
      serverEnvironmentQuery,
      pathQuery,
      groupBy,
      sortKey,
      sortDir,
      envTags,
      serviceTags,
      overview,
      requests,
      errorGroups,
      alertSettings,
      errorGroupSort,
      loading,
      errorMessage,
      refreshToken,
      runbookMessage,
      alertSettingsMessage,
      alertSettingsSaving,
      expandedRequestIds,
      onServerWindowChange,
      onServerMethodChange,
      onServerStatusClassChange,
      toggleEnv,
      toggleService,
      clearClientFilters,
      copyRunbookCommand,
      saveAlertSettings,
      updateAlertSettingsDraft,
      toggleRequestRow,
      onSortHeader,
      rawItems,
      availableEnvironments,
      availableServices,
      filteredSorted,
      topFailingRoutes,
      recentErrorsPreview,
      displayedErrorGroups,
      grouped,
      sparklineSeries,
      operationalSignals,
    ],
  );

  return <DashboardDataContext.Provider value={value}>{children}</DashboardDataContext.Provider>;
}
