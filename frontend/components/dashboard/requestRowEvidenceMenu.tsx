"use client";

import type { RequestItem } from "./dashboardTypes";
import { buildBookmarkUrl, copyTextToClipboard } from "./clipboard";
import type { RowActionItem } from "./RowActionsMenu";

export function buildRequestEvidenceMenuItems(args: {
  item: RequestItem;
  rowId: string;
  onOpenInModal: () => void;
  onSaveBookmark: () => void;
  /** When set, adds a jump to Requests with `correlation` scoped to this row's `request_id`. */
  correlationTrailHref?: string;
}): RowActionItem[] {
  const { item, rowId, onOpenInModal, onSaveBookmark, correlationTrailHref } = args;
  const requestJson = JSON.stringify(item, null, 2);
  const logText = [
    `timestamp: ${item.timestamp}`,
    `method: ${item.method}`,
    `path: ${item.path}`,
    `status_code: ${item.status_code}`,
    `latency_ms: ${item.latency_ms.toFixed(3)}`,
    `service_name: ${item.service_name}`,
    `environment: ${item.environment}`,
    `request_id: ${item.request_id ?? "N/A"}`,
    item.event_id != null ? `event_id: ${item.event_id}` : null,
    item.received_at?.trim() ? `received_at: ${item.received_at}` : null,
    item.sdk_version?.trim() ? `sdk_version: ${item.sdk_version}` : null,
    item.event_kind?.trim() ? `event_kind: ${item.event_kind}` : null,
    item.trace_id?.trim() ? `trace_id: ${item.trace_id}` : null,
    item.span_id?.trim() ? `span_id: ${item.span_id}` : null,
    "",
    item.log_message?.trim() ? item.log_message : "(no log/error message)",
  ]
    .filter((line): line is string => line != null)
    .join("\n");
  const bookmarkFragment = `request-row:${encodeURIComponent(rowId)}`;

  const items: RowActionItem[] = [
    {
      id: "open-modal",
      label: "Open in modal",
      run: () => {
        onOpenInModal();
        return "Opened in modal.";
      },
    },
    {
      id: "copy-request-json",
      label: "Copy full request as JSON",
      run: async () => {
        const copied = await copyTextToClipboard(requestJson);
        return copied ? "Full request JSON copied." : "Clipboard unavailable. Copy manually.";
      },
    },
    {
      id: "copy-log-text",
      label: "Copy full log as text",
      run: async () => {
        const copied = await copyTextToClipboard(logText);
        return copied ? "Full log text copied." : "Clipboard unavailable. Copy manually.";
      },
    },
    {
      id: "copy-bookmark",
      label: "Copy bookmark link",
      run: async () => {
        const bookmarkUrl = buildBookmarkUrl(bookmarkFragment);
        if (!bookmarkUrl) {
          return "Bookmark link unavailable.";
        }
        const copied = await copyTextToClipboard(bookmarkUrl);
        return copied ? "Bookmark link copied." : "Clipboard unavailable. Copy manually.";
      },
    },
    {
      id: "save-bookmark",
      label: "Save bookmark…",
      run: () => {
        onSaveBookmark();
        return "Name your bookmark…";
      },
    },
  ];
  if (correlationTrailHref) {
    items.push({
      id: "correlation-trail",
      label: "Correlation trail (HTTP + jobs)",
      run: () => {
        if (typeof window !== "undefined") {
          window.location.assign(correlationTrailHref);
        }
        return "Opening Requests with correlation filter…";
      },
    });
  }
  return items;
}
