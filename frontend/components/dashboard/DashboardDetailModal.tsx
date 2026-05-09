"use client";

import { useEffect, useId, useRef, type ReactNode } from "react";

import { emitRumEvent } from "../../lib/rumRuntime";
import { sanitizeRumText } from "../../lib/rumSanitize";
import { X } from "../../lib/icons";

type DashboardDetailModalProps = {
  open: boolean;
  title: string;
  onClose: () => void;
  children: ReactNode;
  /** Wider layout for evidence tables / long paths */
  size?: "md" | "lg";
};

export function DashboardDetailModal({ open, title, onClose, children, size = "lg" }: DashboardDetailModalProps) {
  const dialogRef = useRef<HTMLDivElement>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const restoreFocusRef = useRef<HTMLElement | null>(null);
  const titleId = useId();

  const getFocusableElements = () => {
    const dialog = dialogRef.current;
    if (!dialog) {
      return [];
    }
    const nodes = dialog.querySelectorAll<HTMLElement>(
      'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])',
    );
    return Array.from(nodes).filter(
      (node) => !node.hasAttribute("disabled") && node.getAttribute("aria-hidden") !== "true",
    );
  };

  useEffect(() => {
    if (!open) {
      return;
    }
    emitRumEvent("modal_lifecycle", {
      phase: "open",
      title_len: title.length,
      title_snip: sanitizeRumText(title.slice(0, 64)),
    });
    return () => {
      emitRumEvent("modal_lifecycle", {
        phase: "close",
        title_len: title.length,
      });
    };
  }, [open, title]);

  useEffect(() => {
    if (!open) {
      return;
    }
    restoreFocusRef.current =
      document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    queueMicrotask(() => {
      const focusables = getFocusableElements();
      if (focusables.length > 0) {
        focusables[0]?.focus();
        return;
      }
      closeButtonRef.current?.focus();
    });
    return () => {
      document.body.style.overflow = prev;
      restoreFocusRef.current?.focus();
      restoreFocusRef.current = null;
    };
  }, [open]);

  useEffect(() => {
    if (!open) {
      return;
    }
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        onClose();
        return;
      }
      if (e.key !== "Tab") {
        return;
      }
      const focusables = getFocusableElements();
      if (focusables.length === 0) {
        e.preventDefault();
        return;
      }
      const first = focusables[0];
      const last = focusables[focusables.length - 1];
      const active = document.activeElement as HTMLElement | null;
      if (e.shiftKey && active === first) {
        e.preventDefault();
        last?.focus();
      } else if (!e.shiftKey && active === last) {
        e.preventDefault();
        first?.focus();
      }
    };
    const dialogNode = dialogRef.current;
    dialogNode?.addEventListener("keydown", onKey);
    return () => dialogNode?.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) {
    return null;
  }

  const maxW = size === "lg" ? "max-w-4xl" : "max-w-lg";

  return (
    <div
      className="fixed inset-0 z-[100] flex items-end justify-center p-0 sm:items-center sm:p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby={titleId}
    >
      <div
        className="absolute inset-0 bg-slate-950/55 backdrop-blur-[1px] dark:bg-black/60"
        aria-hidden="true"
        onClick={onClose}
      />
      <div
        ref={dialogRef}
        tabIndex={-1}
        className={`relative flex max-h-[min(92vh,880px)] w-full ${maxW} flex-col overflow-hidden rounded-t-2xl border border-slate-200 bg-white shadow-2xl dark:border-neutral-700 dark:bg-neutral-900 sm:rounded-2xl`}
      >
        <div className="flex shrink-0 items-center justify-between gap-3 border-b border-slate-200 px-4 py-3 dark:border-neutral-700 sm:px-5">
          <h2 id={titleId} className="min-w-0 truncate text-base font-semibold text-slate-900 dark:text-neutral-50">
            {title}
          </h2>
          <button
            ref={closeButtonRef}
            type="button"
            onClick={onClose}
            className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-slate-200 bg-slate-50 text-slate-700 transition-colors hover:bg-slate-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-orange-500/40 dark:border-neutral-600 dark:bg-neutral-800 dark:text-neutral-200 dark:hover:bg-neutral-700"
            aria-label="Close"
          >
            <X className="size-4" aria-hidden />
          </button>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto overflow-x-hidden px-4 py-4 sm:px-5 sm:py-5">{children}</div>
      </div>
    </div>
  );
}
