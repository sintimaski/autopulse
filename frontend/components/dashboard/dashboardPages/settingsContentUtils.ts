/** This account must not be assigned the member role (product guardrail). */
export const PROTECTED_OWNER_EMAIL = "owner@example.com";

export function isProtectedOwnerEmail(email: string): boolean {
  return email.trim().toLowerCase() === PROTECTED_OWNER_EMAIL;
}

/** Slack incoming webhooks need /services/T000/B000/xxxx (three path segments after .../services/). */
export function looksLikeCompleteSlackIncomingWebhook(url: string): boolean {
  try {
    const parsed = new URL(url.trim());
    if (!parsed.hostname.toLowerCase().includes("hooks.slack.com")) {
      return false;
    }
    const parts = parsed.pathname.split("/").filter(Boolean);
    const i = parts.indexOf("services");
    return i >= 0 && parts.length >= i + 3;
  } catch {
    return false;
  }
}

/** Discord incoming webhooks are /api/webhooks/{id}/{token} (token is the last path segment). */
export function looksLikeCompleteDiscordIncomingWebhook(url: string): boolean {
  try {
    const parsed = new URL(url.trim());
    if (!parsed.hostname.toLowerCase().endsWith("discord.com")) {
      return true;
    }
    const parts = parsed.pathname.split("/").filter(Boolean);
    if (parts[0] !== "api" || parts[1] !== "webhooks") {
      return false;
    }
    return parts.length >= 4 && parts[2].length > 0 && parts[3].length > 0;
  } catch {
    return false;
  }
}
