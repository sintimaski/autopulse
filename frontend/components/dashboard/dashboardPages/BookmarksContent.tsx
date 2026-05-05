"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";

import { Bookmark, ExternalLink, Pencil, Trash2 } from "../../../lib/icons";
import {
  deleteDashboardBookmark,
  fetchDashboardBookmarks,
  updateDashboardBookmark,
  type DashboardBookmarkItem,
} from "../bookmarkClient";
import { InlineDataSpinner } from "../../ui/InlineDataSpinner";

function bookmarkHref(b: DashboardBookmarkItem): string {
  const q = b.query_string?.trim() ? `?${b.query_string.trim()}` : "";
  const h = b.hash_fragment?.trim() ? `#${b.hash_fragment.trim()}` : "";
  return `${b.pathname}${q}${h}`;
}

export function BookmarksContent() {
  const [items, setItems] = useState<DashboardBookmarkItem[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [draftTitle, setDraftTitle] = useState("");
  const [draftNotes, setDraftNotes] = useState("");
  const [busyId, setBusyId] = useState<string | null>(null);

  const reload = useCallback(async () => {
    setLoadError(null);
    try {
      const next = await fetchDashboardBookmarks();
      setItems(next);
    } catch (e) {
      setItems([]);
      setLoadError(e instanceof Error ? e.message : "Could not load bookmarks.");
    }
  }, []);

  const didInitialFetch = useRef(false);
  useEffect(() => {
    if (didInitialFetch.current) {
      return;
    }
    didInitialFetch.current = true;
    fetchDashboardBookmarks()
      .then((next) => {
        setItems(next);
        setLoadError(null);
      })
      .catch((e) => {
        setItems([]);
        setLoadError(e instanceof Error ? e.message : "Could not load bookmarks.");
      });
  }, []);

  const startEdit = (b: DashboardBookmarkItem) => {
    setEditingId(b.id);
    setDraftTitle(b.title);
    setDraftNotes(b.notes ?? "");
  };

  const cancelEdit = () => {
    setEditingId(null);
    setDraftTitle("");
    setDraftNotes("");
  };

  const saveEdit = async (id: string) => {
    setBusyId(id);
    try {
      const updated = await updateDashboardBookmark(id, {
        title: draftTitle.trim(),
        notes: draftNotes.trim() || null,
      });
      setItems((prev) => (prev ? prev.map((x) => (x.id === id ? updated : x)) : prev));
      cancelEdit();
    } catch (e) {
      setLoadError(e instanceof Error ? e.message : "Update failed.");
    } finally {
      setBusyId(null);
    }
  };

  const remove = async (id: string) => {
    if (!window.confirm("Delete this bookmark?")) {
      return;
    }
    setBusyId(id);
    try {
      await deleteDashboardBookmark(id);
      setItems((prev) => (prev ? prev.filter((x) => x.id !== id) : prev));
    } catch (e) {
      setLoadError(e instanceof Error ? e.message : "Delete failed.");
    } finally {
      setBusyId(null);
    }
  };

  if (items === null) {
    return <InlineDataSpinner label="Loading bookmarks…" className="rounded-2xl" />;
  }

  return (
    <section className="rounded-2xl bg-white/95 p-6 shadow-sm ring-1 ring-slate-900/[0.06] dark:bg-neutral-900 dark:ring-white/[0.08]">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <h2 className="text-lg font-semibold text-slate-900 dark:text-neutral-50">Bookmarks</h2>
            <p className="mt-1 max-w-2xl text-sm text-slate-600 dark:text-neutral-400">
              Every saved deep link for your account (all projects). Create one from Requests or Diagnosis via the row
              menu → <span className="font-medium text-slate-800 dark:text-neutral-200">Save bookmark…</span>.
            </p>
          </div>
        </div>
        {loadError ? (
          <div
            className="mt-4 rounded-xl border border-amber-200 bg-amber-50/90 px-4 py-3 text-sm text-amber-950 dark:border-amber-900/50 dark:bg-amber-950/35 dark:text-amber-50"
            role="alert"
          >
            {loadError}
          </div>
        ) : null}
        {items.length === 0 ? (
          <p className="mt-8 text-center text-sm text-slate-600 dark:text-neutral-400">No bookmarks yet.</p>
        ) : (
          <ul className="mt-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {items.map((b) => {
              const isEditing = editingId === b.id;
              const busy = busyId === b.id;
              return (
                <li
                  key={b.id}
                  className="flex flex-col rounded-2xl border border-slate-200/90 bg-slate-50/50 p-4 shadow-sm dark:border-neutral-700 dark:bg-neutral-800/40"
                >
                  <div className="flex items-start gap-2">
                    <Bookmark className="mt-0.5 size-4 shrink-0 text-orange-500 dark:text-orange-400" aria-hidden />
                    <div className="min-w-0 flex-1">
                      {isEditing ? (
                        <input
                          value={draftTitle}
                          onChange={(e) => setDraftTitle(e.target.value)}
                          className="w-full rounded-lg border border-slate-200 bg-white px-2 py-1.5 text-sm font-semibold text-slate-900 dark:border-neutral-600 dark:bg-neutral-950 dark:text-neutral-50"
                          maxLength={200}
                          aria-label="Bookmark title"
                        />
                      ) : (
                        <h3 className="text-sm font-semibold text-slate-900 dark:text-neutral-50">{b.title}</h3>
                      )}
                      {b.project_name?.trim() ? (
                        <p className="mt-1 text-xs font-medium text-slate-500 dark:text-neutral-400">
                          Project: <span className="text-slate-800 dark:text-neutral-200">{b.project_name}</span>
                        </p>
                      ) : null}
                      <p className="mt-1 break-all font-mono text-xs text-slate-500 dark:text-neutral-500">{bookmarkHref(b)}</p>
                    </div>
                  </div>
                  {isEditing ? (
                    <label className="mt-3 block text-xs font-medium text-slate-600 dark:text-neutral-400">
                      Notes
                      <textarea
                        value={draftNotes}
                        onChange={(e) => setDraftNotes(e.target.value)}
                        rows={3}
                        className="mt-1 w-full rounded-lg border border-slate-200 bg-white px-2 py-1.5 text-sm text-slate-900 dark:border-neutral-600 dark:bg-neutral-950 dark:text-neutral-100"
                        maxLength={8000}
                      />
                    </label>
                  ) : b.notes ? (
                    <p className="mt-3 text-sm text-slate-600 dark:text-neutral-300">{b.notes}</p>
                  ) : null}
                  <div className="mt-4 flex flex-wrap items-center gap-2 border-t border-slate-200/80 pt-3 dark:border-neutral-700">
                    <Link
                      href={bookmarkHref(b)}
                      className="inline-flex items-center gap-1 rounded-lg bg-orange-600 px-3 py-1.5 text-xs font-semibold text-white shadow-sm hover:bg-orange-500 dark:bg-orange-500 dark:hover:bg-orange-400"
                    >
                      Open
                      <ExternalLink className="size-3.5" aria-hidden />
                    </Link>
                    {isEditing ? (
                      <>
                        <button type="button" className="ap-btn text-xs" disabled={busy} onClick={cancelEdit}>
                          Cancel
                        </button>
                        <button type="button" className="ap-btn-primary text-xs" disabled={busy} onClick={() => void saveEdit(b.id)}>
                          {busy ? "Saving…" : "Save"}
                        </button>
                      </>
                    ) : (
                      <>
                        <button
                          type="button"
                          className="inline-flex items-center gap-1 rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50 dark:border-neutral-600 dark:bg-neutral-900 dark:text-neutral-200 dark:hover:bg-neutral-800"
                          onClick={() => startEdit(b)}
                        >
                          <Pencil className="size-3.5" aria-hidden />
                          Edit
                        </button>
                        <button
                          type="button"
                          className="inline-flex items-center gap-1 rounded-lg border border-rose-200 bg-rose-50 px-2.5 py-1.5 text-xs font-medium text-rose-800 hover:bg-rose-100 dark:border-rose-900/50 dark:bg-rose-950/40 dark:text-rose-200 dark:hover:bg-rose-950/70"
                          disabled={busy}
                          onClick={() => void remove(b.id)}
                        >
                          <Trash2 className="size-3.5" aria-hidden />
                          Delete
                        </button>
                      </>
                    )}
                  </div>
                </li>
              );
            })}
          </ul>
        )}
    </section>
  );
}
