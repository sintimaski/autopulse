"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import type { DashboardApiKeyItem } from "../dashboardTypes";

import { resolveApiKeyBulkTargets, type KeyBulkAction } from "./settingsApiKeyBulk";

/** How long the inline "Confirm" affordance stays armed before reverting. */
const CONFIRM_WINDOW_MS = 4000;

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
  // Two-click inline confirm: first Apply arms this, second Apply runs it.
  const [keyBulkConfirmCount, setKeyBulkConfirmCount] = useState<number | null>(null);
  const confirmTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const cancelKeyBulkConfirm = useCallback(() => {
    if (confirmTimerRef.current) {
      clearTimeout(confirmTimerRef.current);
      confirmTimerRef.current = null;
    }
    setKeyBulkConfirmCount(null);
  }, []);

  useEffect(() => {
    return () => {
      if (confirmTimerRef.current) {
        clearTimeout(confirmTimerRef.current);
      }
    };
  }, []);

  const activeKeyIds = useMemo(
    () => apiKeys.filter((k) => !k.revoked_at).map((k) => k.key_id),
    [apiKeys],
  );

  const allKeysSelected =
    activeKeyIds.length > 0 && activeKeyIds.every((id) => selectedKeyIds.has(id));

  const toggleKeySelected = useCallback(
    (keyId: string) => {
      cancelKeyBulkConfirm();
      setSelectedKeyIds((prev) => {
        const next = new Set(prev);
        if (next.has(keyId)) {
          next.delete(keyId);
        } else {
          next.add(keyId);
        }
        return next;
      });
    },
    [cancelKeyBulkConfirm],
  );

  // Changing the chosen action invalidates any armed inline confirm.
  const changeKeyBulkAction = useCallback(
    (next: KeyBulkAction) => {
      cancelKeyBulkConfirm();
      setKeyBulkAction(next);
    },
    [cancelKeyBulkConfirm],
  );

  const applyKeyBulk = useCallback(async () => {
    if (!keyBulkAction || selectedKeyIds.size === 0) {
      return;
    }
    const resolved = resolveApiKeyBulkTargets(keyBulkAction, selectedKeyIds, apiKeys);
    if (!resolved.ok) {
      setApiKeyMessage(resolved.message);
      cancelKeyBulkConfirm();
      return;
    }
    const { targetIds } = resolved;

    // First Apply click arms the inline confirm; second click within the
    // window actually runs the bulk action. Non-blocking, no window.confirm.
    if (keyBulkConfirmCount !== targetIds.length) {
      setKeyBulkConfirmCount(targetIds.length);
      if (confirmTimerRef.current) {
        clearTimeout(confirmTimerRef.current);
      }
      confirmTimerRef.current = setTimeout(() => {
        confirmTimerRef.current = null;
        setKeyBulkConfirmCount(null);
      }, CONFIRM_WINDOW_MS);
      return;
    }
    cancelKeyBulkConfirm();

    let ok = 0;
    const failedIds: string[] = [];
    for (const keyId of targetIds) {
      const success =
        keyBulkAction === "rotate" ? await rotateApiKey(keyId) : await revokeApiKey(keyId);
      if (success) {
        ok += 1;
      } else {
        failedIds.push(keyId);
      }
    }
    await refreshApiKeys();
    setSelectedKeyIds(new Set());
    setKeyBulkAction("");
    if (!ok && failedIds.length === 0) {
      setApiKeyMessage("No changes applied.");
    } else {
      const failedText = failedIds.length
        ? `, ${failedIds.length} failed (${failedIds.join(", ")})`
        : "";
      setApiKeyMessage(`${ok} succeeded${failedText}.`);
    }
  }, [
    apiKeys,
    cancelKeyBulkConfirm,
    keyBulkAction,
    keyBulkConfirmCount,
    refreshApiKeys,
    revokeApiKey,
    rotateApiKey,
    selectedKeyIds,
  ]);

  const issueKey = useCallback(async () => {
    const ok = await issueApiKey();
    setApiKeyMessage(ok ? "New API key issued." : "Failed to issue API key.");
  }, [issueApiKey]);

  const refreshKeys = useCallback(async () => {
    await refreshApiKeys();
    setApiKeyMessage("API keys refreshed.");
  }, [refreshApiKeys]);

  const onToggleSelectAll = useCallback(() => {
    cancelKeyBulkConfirm();
    setSelectedKeyIds((prev) => {
      const allSelected = activeKeyIds.length > 0 && activeKeyIds.every((id) => prev.has(id));
      if (allSelected) {
        return new Set();
      }
      return new Set(activeKeyIds);
    });
  }, [activeKeyIds, cancelKeyBulkConfirm]);

  return {
    selectedKeyIds,
    keyBulkAction,
    setKeyBulkAction: changeKeyBulkAction,
    apiKeyMessage,
    activeKeyIds,
    allKeysSelected,
    toggleKeySelected,
    applyKeyBulk,
    keyBulkConfirmCount,
    cancelKeyBulkConfirm,
    issueKey,
    refreshKeys,
    onToggleSelectAll,
  };
}
