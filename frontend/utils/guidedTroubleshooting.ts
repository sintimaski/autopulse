export type GuidedTroubleshootingInput = {
  errorSpikeCandidate: boolean;
  outageCandidate: boolean;
  topFailingRouteCount: number;
  hasFailedDispatch: boolean;
  failedDispatchReason: string | null;
  archivalStatus: "idle" | "running" | "failed" | null;
  archivalError: string | null;
};

export type GuidedTroubleshootingHint = {
  id: string;
  title: string;
};

export function buildGuidedTroubleshootingHints(
  input: GuidedTroubleshootingInput,
): GuidedTroubleshootingHint[] {
  const hints: GuidedTroubleshootingHint[] = [];
  if (input.errorSpikeCandidate) {
    hints.push({ id: "error-spike", title: "Error spike candidate" });
  }
  if (input.outageCandidate) {
    hints.push({ id: "outage", title: "Possible outage candidate" });
  }
  if (input.topFailingRouteCount > 0) {
    hints.push({ id: "high-5xx-route", title: "High 5xx route concentration" });
  }
  if (input.hasFailedDispatch) {
    hints.push({
      id: "alert-delivery",
      title: input.failedDispatchReason
        ? `Alert delivery failure (${input.failedDispatchReason})`
        : "Alert delivery failure",
    });
  }
  if (input.archivalStatus === "failed") {
    hints.push({
      id: "retention-backlog",
      title: input.archivalError
        ? `Retention archival needs attention (${input.archivalError})`
        : "Retention archival needs attention",
    });
  }
  if (hints.length === 0) {
    hints.push({ id: "healthy", title: "No urgent incident pattern detected" });
  }
  return hints;
}
