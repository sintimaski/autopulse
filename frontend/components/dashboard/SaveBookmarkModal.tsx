"use client";

import { useState } from "react";

import { createDashboardBookmark } from "./bookmarkClient";
import { DashboardDetailModal } from "./DashboardDetailModal";
import { stripDashboardBookmarkQueryString } from "./dashboardQueryState";

type SaveBookmarkModalProps = {
  open: boolean;
  onClose: () => void;
  defaultTitle: string;
  pathname: string;
  queryString: string;
  hashFragment: string;
  onSaved?: () => void;
};

type SaveBookmarkModalBodyProps = Omit<SaveBookmarkModalProps, "open">;

function SaveBookmarkModalBody({
  onClose,
  defaultTitle,
  pathname,
  queryString,
  hashFragment,
  onSaved,
}: SaveBookmarkModalBodyProps) {
  const [title, setTitle] = useState(defaultTitle);
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async () => {
    setBusy(true);
    setError(null);
    try {
      await createDashboardBookmark({
        title: title.trim() || defaultTitle,
        pathname,
        query_string: stripDashboardBookmarkQueryString(queryString) || null,
        hash_fragment: hashFragment || null,
        notes: notes.trim() || null,
      });
      onSaved?.();
      onClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not save bookmark.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex flex-col gap-4">
        <p className="text-sm text-slate-600 dark:text-neutral-400">
          Saved to your account for this project. Open it anytime from{" "}
          <span className="font-medium text-slate-800 dark:text-neutral-200">Bookmarks</span> in the sidebar.
        </p>
        <label className="block text-sm font-medium text-slate-700 dark:text-neutral-200">
          Title
          <input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            className="mt-1.5 w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm outline-none focus:ring-2 focus:ring-orange-500/35 dark:border-neutral-600 dark:bg-neutral-950 dark:text-neutral-100 dark:focus:ring-neutral-500/40"
            maxLength={200}
            autoFocus
          />
        </label>
        <label className="block text-sm font-medium text-slate-700 dark:text-neutral-200">
          Notes <span className="font-normal text-slate-500 dark:text-neutral-500">(optional)</span>
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            rows={3}
            className="mt-1.5 w-full resize-y rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm outline-none focus:ring-2 focus:ring-orange-500/35 dark:border-neutral-600 dark:bg-neutral-950 dark:text-neutral-100 dark:focus:ring-neutral-500/40"
            maxLength={8000}
          />
        </label>
        {error ? (
          <p className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-900 dark:border-rose-900/50 dark:bg-rose-950/40 dark:text-rose-100" role="alert">
            {error}
          </p>
        ) : null}
        <div className="flex flex-wrap justify-end gap-2 pt-1">
          <button
            type="button"
            onClick={onClose}
            className="inline-flex items-center justify-center rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-800 transition-colors hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-orange-500/35 disabled:opacity-50 dark:border-neutral-600 dark:bg-neutral-800 dark:text-neutral-100 dark:hover:bg-neutral-700"
            disabled={busy}
          >
            Cancel
          </button>
          <button type="button" onClick={() => void submit()} className="ap-btn-primary" disabled={busy}>
            {busy ? "Saving…" : "Save"}
          </button>
        </div>
      </div>
  );
}

export function SaveBookmarkModal({
  open,
  onClose,
  defaultTitle,
  pathname,
  queryString,
  hashFragment,
  onSaved,
}: SaveBookmarkModalProps) {
  return (
    <DashboardDetailModal open={open} title="Save bookmark" onClose={onClose} size="md">
      {open ? (
        <SaveBookmarkModalBody
          key={`${defaultTitle}|${hashFragment}|${pathname}`}
          onClose={onClose}
          defaultTitle={defaultTitle}
          pathname={pathname}
          queryString={queryString}
          hashFragment={hashFragment}
          onSaved={onSaved}
        />
      ) : null}
    </DashboardDetailModal>
  );
}
