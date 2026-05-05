"use client";

import { useEffect, useRef, useState } from "react";

export type RowActionItem = {
  id: string;
  label: string;
  run: () => Promise<string | null> | string | null;
};

type RowActionsMenuProps = {
  items: RowActionItem[];
};

export function RowActionsMenu({ items }: RowActionsMenuProps) {
  const [open, setOpen] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const rootRef = useRef<HTMLDivElement>(null);
  const messageTimerRef = useRef<number | null>(null);

  useEffect(() => {
    return () => {
      if (messageTimerRef.current !== null) {
        window.clearTimeout(messageTimerRef.current);
      }
    };
  }, []);

  useEffect(() => {
    if (!open) {
      return;
    }
    const onPointerDown = (event: PointerEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    const onEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setOpen(false);
      }
    };
    window.addEventListener("pointerdown", onPointerDown);
    window.addEventListener("keydown", onEscape);
    return () => {
      window.removeEventListener("pointerdown", onPointerDown);
      window.removeEventListener("keydown", onEscape);
    };
  }, [open]);

  const showMessage = (next: string | null) => {
    setMessage(next);
    if (messageTimerRef.current !== null) {
      window.clearTimeout(messageTimerRef.current);
      messageTimerRef.current = null;
    }
    if (next) {
      messageTimerRef.current = window.setTimeout(() => {
        setMessage(null);
        messageTimerRef.current = null;
      }, 2200);
    }
  };

  return (
    <div ref={rootRef} className="relative inline-flex items-center">
      <button
        type="button"
        onClick={() => setOpen((prev) => !prev)}
        aria-haspopup="menu"
        aria-expanded={open}
        className="inline-flex h-8 w-8 items-center justify-center rounded-md border border-slate-300 bg-white text-base font-semibold text-slate-700 shadow-sm transition-colors hover:bg-slate-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-orange-500/40 dark:border-neutral-700 dark:bg-neutral-900 dark:text-neutral-200 dark:hover:bg-neutral-800 dark:focus-visible:ring-neutral-500/50"
      >
        <span aria-hidden>...</span>
        <span className="sr-only">Open row actions</span>
      </button>
      {open ? (
        <div
          role="menu"
          className="absolute right-0 top-9 z-[120] min-w-[220px] rounded-lg border border-slate-200 bg-white p-1 shadow-lg dark:border-neutral-700 dark:bg-neutral-900"
        >
          {items.map((item) => (
            <button
              key={item.id}
              type="button"
              role="menuitem"
              onClick={async () => {
                const result = await item.run();
                setOpen(false);
                showMessage(result);
              }}
              className="block w-full rounded-md px-3 py-2 text-left text-sm text-slate-700 hover:bg-slate-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-orange-500/35 dark:text-neutral-200 dark:hover:bg-neutral-800 dark:focus-visible:ring-neutral-500/40"
            >
              {item.label}
            </button>
          ))}
        </div>
      ) : null}
      {message ? (
        <span
          className="absolute right-0 top-full z-[121] mt-1 max-w-[min(18rem,calc(100vw-2rem)))] rounded-md border border-slate-200 bg-white px-2 py-1.5 text-xs text-slate-700 shadow-md dark:border-neutral-600 dark:bg-neutral-900 dark:text-neutral-200"
          role="status"
          aria-live="polite"
        >
          {message}
        </span>
      ) : null}
    </div>
  );
}
