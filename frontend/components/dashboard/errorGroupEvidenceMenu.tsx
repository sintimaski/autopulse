"use client";

import type { ErrorGroupItem } from "./dashboardTypes";
import { buildBookmarkUrl, copyTextToClipboard } from "./clipboard";
import type { RowActionItem } from "./RowActionsMenu";

export function buildErrorGroupEvidenceMenuItems(args: {
  item: ErrorGroupItem;
  onOpenInModal: () => void;
  onSaveBookmark: () => void;
}): RowActionItem[] {
  const { item, onOpenInModal, onSaveBookmark } = args;
  const errorJson = JSON.stringify(item, null, 2);
  const errorText = [
    `exception_type: ${item.exception_type ?? "(unknown)"}`,
    `message: ${item.message ?? "(no message)"}`,
    `path: ${item.path}`,
    `count: ${item.count}`,
    `first_seen: ${item.first_seen}`,
    `last_seen: ${item.last_seen}`,
    "",
    item.sample_stack_trace ?? "(no stack trace)",
  ].join("\n");
  const bookmarkFragment = `error-group:${encodeURIComponent(item.group_key)}`;

  return [
    {
      id: "open-modal",
      label: "Open in modal",
      run: () => {
        onOpenInModal();
        return "Opened in modal.";
      },
    },
    {
      id: "copy-error-json",
      label: "Copy full error group as JSON",
      run: async () => {
        const copied = await copyTextToClipboard(errorJson);
        return copied ? "Full error group JSON copied." : "Clipboard unavailable. Copy manually.";
      },
    },
    {
      id: "copy-error-text",
      label: "Copy full error as text",
      run: async () => {
        const copied = await copyTextToClipboard(errorText);
        return copied ? "Full error text copied." : "Clipboard unavailable. Copy manually.";
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
}
