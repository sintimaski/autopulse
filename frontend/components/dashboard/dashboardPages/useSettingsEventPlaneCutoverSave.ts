"use client";

import { useCallback, useState } from "react";

import { buildApiUrl } from "../dashboardTypes";
import { DASHBOARD_FETCH_TIMEOUT_MS, fetchWithTimeout } from "../dashboardDataFetchUtils";
import { parseEventPlaneCutoverSettings } from "../../../utils/dashboardResponseGuards";

type SetBool = (value: boolean) => void;
type SetMessage = (value: string | null) => void;

export function useSettingsEventPlaneCutoverSave(
  useSnapshotRead: boolean,
  setEventPlaneUseSnapshotRead: SetBool,
  setEventPlaneCutoverMessage: SetMessage,
) {
  const [eventPlaneCutoverSaving, setEventPlaneCutoverSaving] = useState(false);

  const saveEventPlaneCutover = useCallback(async () => {
    setEventPlaneCutoverSaving(true);
    setEventPlaneCutoverMessage(null);
    try {
      const response = await fetchWithTimeout(
        buildApiUrl("/dashboard/event-plane-cutover"),
        {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          credentials: "include",
          body: JSON.stringify({ use_snapshot_read: useSnapshotRead }),
        },
        DASHBOARD_FETCH_TIMEOUT_MS,
      );
      if (!response.ok) {
        throw new Error(`event-plane-cutover update failed (${response.status})`);
      }
      const raw: unknown = await response.json();
      const payload = parseEventPlaneCutoverSettings(raw);
      if (!payload) {
        throw new Error("event-plane-cutover save returned unexpected JSON shape");
      }
      setEventPlaneUseSnapshotRead(Boolean(payload.use_snapshot_read));
      setEventPlaneCutoverMessage("Event Plane cutover saved.");
    } catch {
      setEventPlaneCutoverMessage("Failed to save Event Plane cutover.");
    } finally {
      setEventPlaneCutoverSaving(false);
    }
  }, [setEventPlaneCutoverMessage, setEventPlaneUseSnapshotRead, useSnapshotRead]);

  return { eventPlaneCutoverSaving, saveEventPlaneCutover };
}
