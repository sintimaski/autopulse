import type { DashboardOnboardingStatusResponse } from "./dashboardTypes";

/**
 * When `/dashboard/bootstrap` fails after an authenticated session exists, we still need a known
 * onboarding shape so `DashboardLayoutClient` does not block the shell forever.
 * Product choice: allow console access with a prominent retry banner; user can still sign out or fix API connectivity.
 */
export function createBootstrapFailureOnboardingFallback(): DashboardOnboardingStatusResponse {
  return {
    session_authenticated: true,
    project_ready: false,
    ingest_key_ready: false,
    first_event_received: false,
    first_diagnostic_signal_ready: false,
    onboarding_completed: true,
    next_recommended_action: "Workspace settings could not be loaded. Use Retry or check API connectivity.",
    current_step: "completed",
  };
}
