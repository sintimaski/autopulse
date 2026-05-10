"use client";

import { useCallback, useState } from "react";

export function useSettingsActiveProject(
  sessionProjectId: string | null,
  setActiveDashboardProject: (nextId: string) => Promise<boolean>,
) {
  const [activeProjectBusy, setActiveProjectBusy] = useState(false);
  const [activeProjectMessage, setActiveProjectMessage] = useState<string | null>(null);

  const onActiveProjectChange = useCallback(
    async (nextId: string) => {
      if (!nextId || nextId === sessionProjectId) {
        return;
      }
      setActiveProjectBusy(true);
      setActiveProjectMessage(null);
      const ok = await setActiveDashboardProject(nextId);
      setActiveProjectBusy(false);
      setActiveProjectMessage(
        ok ? "Switched active project. Charts and keys will refresh." : "Could not switch project. Try again.",
      );
    },
    [sessionProjectId, setActiveDashboardProject],
  );

  return { activeProjectBusy, activeProjectMessage, onActiveProjectChange };
}
