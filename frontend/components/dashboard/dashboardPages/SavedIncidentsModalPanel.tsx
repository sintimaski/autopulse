"use client";

import { useCallback, useEffect, useState } from "react";

import { ClipboardList, ExternalLink, Pencil, Plus, Trash2 } from "../../../lib/icons";
import { dashboardSessionFetch, dashboardSessionJsonPatch } from "../dashboardSessionFetch";
import { InlineDataSpinner } from "../../ui/InlineDataSpinner";

type IncidentShareListRow = {
  id: string;
  title: string | null;
  created_at: string;
  updated_at: string;
  expires_at: string;
  access_mode: string;
};

function parseListPayload(raw: unknown): IncidentShareListRow[] {
  if (!Array.isArray(raw)) {
    return [];
  }
  const rows: IncidentShareListRow[] = [];
  for (const item of raw) {
    if (typeof item !== "object" || item === null) {
      continue;
    }
    const rec = item as Record<string, unknown>;
    const id = typeof rec.id === "string" ? rec.id : "";
    const created_at = typeof rec.created_at === "string" ? rec.created_at : "";
    const updated_at = typeof rec.updated_at === "string" ? rec.updated_at : "";
    const expires_at = typeof rec.expires_at === "string" ? rec.expires_at : "";
    const access_mode = typeof rec.access_mode === "string" ? rec.access_mode : "";
    const title =
      rec.title === null || rec.title === undefined
        ? null
        : typeof rec.title === "string"
          ? rec.title
          : null;
    if (!id || !created_at || !updated_at || !expires_at || !access_mode) {
      continue;
    }
    rows.push({ id, title, created_at, updated_at, expires_at, access_mode });
  }
  return rows;
}

export type SavedIncidentsModalPanelProps = {
  /** When true, refetches the list (modal is shown). */
  modalOpen: boolean;
  /** Disables the New notebook control while a server-backed notebook is being created. */
  creatingNewNotebook?: boolean;
  onOpenSaved: (id: string) => void;
  onNewIncident: () => void;
};

export function SavedIncidentsModalPanel({
  modalOpen,
  creatingNewNotebook = false,
  onOpenSaved,
  onNewIncident,
}: SavedIncidentsModalPanelProps) {
  const [items, setItems] = useState<IncidentShareListRow[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [draftTitle, setDraftTitle] = useState("");
  const [busyId, setBusyId] = useState<string | null>(null);

  const reload = useCallback(async () => {
    setLoadError(null);
    try {
      const res = await dashboardSessionFetch("/dashboard/incident-shares?limit=100");
      if (!res.ok) {
        const raw: unknown = await res.json().catch(() => ({}));
        const detail =
          typeof raw === "object" && raw && "detail" in raw && typeof (raw as { detail: unknown }).detail === "string"
            ? (raw as { detail: string }).detail
            : `Could not load incidents (${res.status})`;
        throw new Error(detail);
      }
      const raw: unknown = await res.json();
      setItems(parseListPayload(raw));
    } catch (e) {
      setItems([]);
      setLoadError(e instanceof Error ? e.message : "Could not load incidents.");
    }
  }, []);

  useEffect(() => {
    if (!modalOpen) {
      return;
    }
    queueMicrotask(() => {
      setItems(null);
      setEditingId(null);
      setDraftTitle("");
      void reload();
    });
  }, [modalOpen, reload]);

  const startEdit = (row: IncidentShareListRow) => {
    setEditingId(row.id);
    setDraftTitle(row.title ?? "");
  };

  const cancelEdit = () => {
    setEditingId(null);
    setDraftTitle("");
  };

  const saveEdit = async (id: string) => {
    setBusyId(id);
    try {
      const res = await dashboardSessionJsonPatch(`/dashboard/incident-shares/${id}`, {
        title: draftTitle.trim() || null,
      });
      if (!res.ok) {
        const raw: unknown = await res.json().catch(() => ({}));
        const detail =
          typeof raw === "object" && raw && "detail" in raw && typeof (raw as { detail: unknown }).detail === "string"
            ? (raw as { detail: string }).detail
            : `Update failed (${res.status})`;
        throw new Error(detail);
      }
      await reload();
      cancelEdit();
    } catch (e) {
      setLoadError(e instanceof Error ? e.message : "Update failed.");
    } finally {
      setBusyId(null);
    }
  };

  const remove = async (id: string) => {
    if (!window.confirm("Delete this saved incident? It will no longer appear here or for share redemption.")) {
      return;
    }
    setBusyId(id);
    try {
      const res = await dashboardSessionFetch(`/dashboard/incident-shares/${id}`, { method: "DELETE" });
      if (!res.ok && res.status !== 204) {
        const raw: unknown = await res.json().catch(() => ({}));
        const detail =
          typeof raw === "object" && raw && "detail" in raw && typeof (raw as { detail: unknown }).detail === "string"
            ? (raw as { detail: string }).detail
            : `Delete failed (${res.status})`;
        throw new Error(detail);
      }
      setItems((prev) => (prev ? prev.filter((x) => x.id !== id) : prev));
    } catch (e) {
      setLoadError(e instanceof Error ? e.message : "Delete failed.");
    } finally {
      setBusyId(null);
    }
  };

  if (items === null) {
    return <InlineDataSpinner label="Loading saved incidents…" className="rounded-xl py-8" />;
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <p className="max-w-2xl text-sm text-slate-600 dark:text-neutral-400">
          Server-backed workbooks for this project. Use <span className="font-medium text-slate-800 dark:text-neutral-200">Publish</span>{" "}
          in the notebook to add rows. Opening one applies its scope and cells below.
        </p>
        <button
          type="button"
          disabled={creatingNewNotebook}
          onClick={onNewIncident}
          className="inline-flex shrink-0 items-center gap-2 self-start rounded-xl bg-orange-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-orange-500 disabled:cursor-not-allowed disabled:opacity-60 dark:bg-orange-500 dark:hover:bg-orange-400"
        >
          <Plus className="size-4" aria-hidden />
          {creatingNewNotebook ? "Creating…" : "New notebook"}
        </button>
      </div>
      {loadError ? (
        <div
          className="rounded-xl border border-amber-200 bg-amber-50/90 px-4 py-3 text-sm text-amber-950 dark:border-amber-900/50 dark:bg-amber-950/35 dark:text-amber-50"
          role="alert"
        >
          {loadError}
        </div>
      ) : null}
      {items.length === 0 ? (
        <p className="py-6 text-center text-sm text-slate-600 dark:text-neutral-400">
          No saved incidents yet. Publish a workbook from this page to store it on the server.
        </p>
      ) : (
        <ul className="grid gap-3 sm:grid-cols-2">
          {items.map((row) => {
            const isEditing = editingId === row.id;
            const busy = busyId === row.id;
            const label = row.title?.trim() || "Untitled incident";
            return (
              <li
                key={row.id}
                className="flex flex-col rounded-xl border border-slate-200/90 bg-slate-50/50 p-3 shadow-sm dark:border-neutral-700 dark:bg-neutral-800/40"
              >
                <div className="flex items-start gap-2">
                  <ClipboardList className="mt-0.5 size-4 shrink-0 text-orange-500 dark:text-orange-400" aria-hidden />
                  <div className="min-w-0 flex-1">
                    {isEditing ? (
                      <input
                        value={draftTitle}
                        onChange={(e) => setDraftTitle(e.target.value)}
                        className="w-full rounded-lg border border-slate-200 bg-white px-2 py-1.5 text-sm font-semibold text-slate-900 dark:border-neutral-600 dark:bg-neutral-950 dark:text-neutral-50"
                        maxLength={200}
                        placeholder="Title"
                        aria-label="Incident title"
                      />
                    ) : (
                      <h3 className="text-sm font-semibold text-slate-900 dark:text-neutral-50">{label}</h3>
                    )}
                    <p className="mt-1 font-mono text-[11px] text-slate-500 dark:text-neutral-500">
                      Updated {row.updated_at.slice(0, 19)}Z · Expires {row.expires_at.slice(0, 10)}
                    </p>
                    <p className="mt-0.5 text-[11px] text-slate-500 dark:text-neutral-500">
                      Access: <span className="font-medium text-slate-700 dark:text-neutral-300">{row.access_mode}</span>
                    </p>
                  </div>
                </div>
                <div className="mt-3 flex flex-wrap items-center gap-2 border-t border-slate-200/80 pt-2 dark:border-neutral-700">
                  <button
                    type="button"
                    onClick={() => onOpenSaved(row.id)}
                    className="inline-flex items-center gap-1 rounded-lg bg-orange-600 px-3 py-1.5 text-xs font-semibold text-white shadow-sm hover:bg-orange-500 dark:bg-orange-500 dark:hover:bg-orange-400"
                  >
                    Open
                    <ExternalLink className="size-3.5" aria-hidden />
                  </button>
                  {isEditing ? (
                    <>
                      <button type="button" className="ap-btn text-xs" disabled={busy} onClick={cancelEdit}>
                        Cancel
                      </button>
                      <button type="button" className="ap-btn-primary text-xs" disabled={busy} onClick={() => void saveEdit(row.id)}>
                        {busy ? "Saving…" : "Save"}
                      </button>
                    </>
                  ) : (
                    <>
                      <button
                        type="button"
                        className="inline-flex items-center gap-1 rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50 dark:border-neutral-600 dark:bg-neutral-900 dark:text-neutral-200 dark:hover:bg-neutral-800"
                        onClick={() => startEdit(row)}
                      >
                        <Pencil className="size-3.5" aria-hidden />
                        Rename
                      </button>
                      <button
                        type="button"
                        className="inline-flex items-center gap-1 rounded-lg border border-rose-200 bg-rose-50 px-2.5 py-1.5 text-xs font-medium text-rose-800 hover:bg-rose-100 dark:border-rose-900/50 dark:bg-rose-950/40 dark:text-rose-200 dark:hover:bg-rose-950/70"
                        disabled={busy}
                        onClick={() => void remove(row.id)}
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
    </div>
  );
}
