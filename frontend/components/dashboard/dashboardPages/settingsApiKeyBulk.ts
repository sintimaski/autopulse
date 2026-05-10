import type { DashboardApiKeyItem } from "../dashboardTypes";

export type KeyBulkAction = "" | "rotate" | "revoke";

export function activeApiKeys(apiKeys: DashboardApiKeyItem[]): DashboardApiKeyItem[] {
  return apiKeys.filter((k) => !k.revoked_at);
}

/** Oldest active key by `created_at` (same ordering as Settings bulk rules). */
export function primaryActiveKeyIdFromList(apiKeys: DashboardApiKeyItem[]): string | null {
  const active = activeApiKeys(apiKeys);
  if (active.length === 0) {
    return null;
  }
  const sorted = [...active].sort(
    (a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime(),
  );
  return sorted[0]?.key_id ?? null;
}

export type ResolveBulkTargetsResult =
  | { ok: true; targetIds: string[] }
  | { ok: false; message: string };

/**
 * Computes which key ids to rotate/revoke for bulk actions, including revoke guardrails.
 */
export function resolveApiKeyBulkTargets(
  keyBulkAction: "rotate" | "revoke",
  selectedKeyIds: Set<string>,
  apiKeys: DashboardApiKeyItem[],
): ResolveBulkTargetsResult {
  const activeKeys = activeApiKeys(apiKeys);
  const activeIdSet = new Set(activeKeys.map((k) => k.key_id));
  let targetIds = [...selectedKeyIds].filter((id) => activeIdSet.has(id));

  if (keyBulkAction === "revoke") {
    if (activeKeys.length === 1) {
      return { ok: false, message: "Cannot revoke your only active ingest key." };
    }
    const primaryId = primaryActiveKeyIdFromList(apiKeys);
    if (activeKeys.length > 1 && primaryId) {
      targetIds = targetIds.filter((id) => id !== primaryId);
    }
    if (targetIds.length === 0) {
      return {
        ok: false,
        message:
          "Primary (oldest) active key cannot be bulk-revoked. Deselect it or revoke other keys first.",
      };
    }
    if (activeKeys.length - targetIds.length < 1) {
      return { ok: false, message: "Leave at least one active key. Deselect some keys." };
    }
  }

  return { ok: true, targetIds };
}
