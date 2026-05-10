"use client";

import { useCallback, useMemo, useState } from "react";

import type { DashboardApiKeyItem } from "../dashboardTypes";

import { resolveApiKeyBulkTargets, type KeyBulkAction } from "./settingsApiKeyBulk";

export function useSettingsApiKeyBulk(
  apiKeys: DashboardApiKeyItem[],
  rotateApiKey: (keyId: string) => Promise<boolean>,
  revokeApiKey: (keyId: string) => Promise<boolean>,
  refreshApiKeys: () => Promise<void>,
  issueApiKey: () => Promise<boolean>,
) {
  const [selectedKeyIds, setSelectedKeyIds] = useState<Set<string>>(new Set());
  const [keyBulkAction, setKeyBulkAction] = useState<KeyBulkAction>("");
  const [apiKeyMessage, setApiKeyMessage] = useState<string | null>(null);

  const activeKeyIds = useMemo(
    () => apiKeys.filter((k) => !k.revoked_at).map((k) => k.key_id),
    [apiKeys],
  );

  const allKeysSelected =
    activeKeyIds.length > 0 && activeKeyIds.every((id) => selectedKeyIds.has(id));

  const toggleKeySelected = useCallback((keyId: string) => {
    setSelectedKeyIds((prev) => {
      const next = new Set(prev);
      if (next.has(keyId)) {
        next.delete(keyId);
      } else {
        next.add(keyId);
      }
      return next;
    });
  }, []);

  const applyKeyBulk = useCallback(async () => {
    if (!keyBulkAction || selectedKeyIds.size === 0) {
      return;
    }
    const resolved = resolveApiKeyBulkTargets(keyBulkAction, selectedKeyIds, apiKeys);
    if (!resolved.ok) {
      setApiKeyMessage(resolved.message);
      return;
    }
    const { targetIds } = resolved;

    const label = keyBulkAction === "rotate" ? "Rotate" : "Revoke";
    if (!window.confirm(`${label} ${targetIds.length} key(s)?`)) {
      return;
    }

    let ok = 0;
    let failed = 0;
    for (const keyId of targetIds) {
      if (keyBulkAction === "rotate") {
        const success = await rotateApiKey(keyId);
        if (success) {
          ok += 1;
        } else {
          failed += 1;
        }
      } else {
        const success = await revokeApiKey(keyId);
        if (success) {
          ok += 1;
        } else {
          failed += 1;
        }
      }
    }
    await refreshApiKeys();
    setSelectedKeyIds(new Set());
    setKeyBulkAction("");
    setApiKeyMessage(
      ok || failed ? `${ok} succeeded${failed ? `, ${failed} failed` : ""}.` : "No changes applied.",
    );
  }, [apiKeys, keyBulkAction, refreshApiKeys, revokeApiKey, rotateApiKey, selectedKeyIds]);

  const issueKey = useCallback(async () => {
    const ok = await issueApiKey();
    setApiKeyMessage(ok ? "New API key issued." : "Failed to issue API key.");
  }, [issueApiKey]);

  const refreshKeys = useCallback(async () => {
    await refreshApiKeys();
    setApiKeyMessage("API keys refreshed.");
  }, [refreshApiKeys]);

  const onToggleSelectAll = useCallback(() => {
    setSelectedKeyIds((prev) => {
      const allSelected = activeKeyIds.length > 0 && activeKeyIds.every((id) => prev.has(id));
      if (allSelected) {
        return new Set();
      }
      return new Set(activeKeyIds);
    });
  }, [activeKeyIds]);

  return {
    selectedKeyIds,
    keyBulkAction,
    setKeyBulkAction,
    apiKeyMessage,
    activeKeyIds,
    allKeysSelected,
    toggleKeySelected,
    applyKeyBulk,
    issueKey,
    refreshKeys,
    onToggleSelectAll,
  };
}
