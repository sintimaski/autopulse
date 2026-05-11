/**
 * Lightweight, privacy-preserving client timestamps for activation funnel review.
 * Values are stored only in sessionStorage on the operator browser (no automatic upload).
 */
const PREFIX = "lx_activation_";

export function recordActivationMilestone(step: "onboarding_view" | "key_issued_view" | "first_event_seen"): void {
  if (typeof window === "undefined") {
    return;
  }
  try {
    const key = `${PREFIX}${step}`;
    if (!window.sessionStorage.getItem(key)) {
      window.sessionStorage.setItem(key, String(Date.now()));
    }
  } catch {
    // ignore private mode / quota
  }
}
