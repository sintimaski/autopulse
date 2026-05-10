"use client";

import { useCallback, useMemo, useState } from "react";

import type { RetentionSettings } from "../dashboardTypes";

export function useSettingsRetentionPolicy(
  retentionSettings: RetentionSettings | null,
  saveRetentionSettings: (draft: RetentionSettings) => Promise<boolean>,
) {
  const [retentionDraft, setRetentionDraft] = useState<RetentionSettings | null>(null);
  const [retentionMessage, setRetentionMessage] = useState<string | null>(null);

  const effectiveRetentionDraft = useMemo(
    () => retentionDraft ?? retentionSettings,
    [retentionDraft, retentionSettings],
  );

  const saveRetention = useCallback(async () => {
    const draft = retentionDraft ?? retentionSettings;
    if (!draft) {
      return;
    }
    const ok = await saveRetentionSettings(draft);
    setRetentionMessage(ok ? "Retention settings saved." : "Failed to save retention settings.");
  }, [retentionDraft, retentionSettings, saveRetentionSettings]);

  return {
    effectiveRetentionDraft,
    retentionMessage,
    setRetentionDraft,
    saveRetention,
  };
}
