type ScopeResetVariant = "diagnosis" | "logs" | "requests";

type ScopeResetActions = {
  onServerMethodChange: (value: string) => void;
  onServerStatusClassChange: (value: string) => void;
  setPathQuery: (value: string) => void;
  setMinLatencyMs: (value: string) => void;
  setMaxLatencyMs: (value: string) => void;
  setServerEnvironmentQuery?: (value: string) => void;
  setServerServiceQuery?: (value: string) => void;
  setServerEnvironmentTags?: (tags: string[]) => void;
  setServerServiceTags?: (tags: string[]) => void;
  setRequestLimit: (n: number) => void;
  setRequestPage: (n: number) => void;
  setErrorGroupLimit: (n: number) => void;
  setErrorGroupPage: (n: number) => void;
  setErrorGroupSort: (value: "last_seen" | "count") => void;
  setSqlFilterDraft: (value: string) => void;
  setSqlFilterApplied: (value: string) => void;
  setSqlFilterEnabled: (enabled: boolean) => void;
  setCorrelationRequestId: (value: string) => void;
};

export function resetServerScope(actions: ScopeResetActions, variant: ScopeResetVariant): void {
  actions.onServerMethodChange("ALL");
  actions.onServerStatusClassChange("ALL");
  actions.setPathQuery("");
  actions.setMinLatencyMs("");
  actions.setMaxLatencyMs("");
  if (actions.setServerEnvironmentTags && actions.setServerServiceTags) {
    actions.setServerEnvironmentTags([]);
    actions.setServerServiceTags([]);
  } else {
    actions.setServerEnvironmentQuery?.("");
    actions.setServerServiceQuery?.("");
  }
  actions.setSqlFilterDraft("");
  actions.setSqlFilterApplied("");
  actions.setSqlFilterEnabled(false);
  actions.setCorrelationRequestId("");

  if (variant === "diagnosis") {
    actions.setRequestPage(0);
    actions.setErrorGroupPage(0);
    actions.setErrorGroupSort("last_seen");
    actions.setErrorGroupLimit(25);
    return;
  }

  actions.setRequestLimit(100);
  actions.setRequestPage(0);
}
