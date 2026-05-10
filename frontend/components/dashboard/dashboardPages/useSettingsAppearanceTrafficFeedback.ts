"use client";

import { useCallback, useState } from "react";

export function useSettingsAppearanceTrafficFeedback(
  saveExcludeLumonoxTraffic: (next: boolean) => Promise<boolean>,
) {
  const [themeMessage, setThemeMessage] = useState<string | null>(null);

  const onToggleExcludeLumonoxTraffic = useCallback(
    async (next: boolean) => {
      const ok = await saveExcludeLumonoxTraffic(next);
      setThemeMessage(ok ? "Saved." : "Could not save. Try again.");
    },
    [saveExcludeLumonoxTraffic],
  );

  return { themeMessage, setThemeMessage, onToggleExcludeLumonoxTraffic };
}
