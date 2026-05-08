"use client";

import { useEffect, useId, useRef, useState } from "react";

import { MoreVertical } from "../../lib/icons";

export type RowActionItem = {
  id: string;
  label: string;
  run: () => Promise<string | null> | string | null;
};

type RowActionsMenuProps = {
  items: RowActionItem[];
};

export function getNextActiveMenuIndex(
  currentIndex: number,
  itemCount: number,
  key: "ArrowDown" | "ArrowUp" | "Home" | "End",
): number {
  if (itemCount <= 0) {
    return -1;
  }
  if (key === "Home") {
    return 0;
  }
  if (key === "End") {
    return itemCount - 1;
  }
  if (key === "ArrowDown") {
    return (currentIndex + 1 + itemCount) % itemCount;
  }
  return (currentIndex - 1 + itemCount) % itemCount;
}

export function RowActionsMenu({ items }: RowActionsMenuProps) {
  const [open, setOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(0);
  const [message, setMessage] = useState<string | null>(null);
  const rootRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const messageTimerRef = useRef<number | null>(null);
  const menuId = useId();

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
        triggerRef.current?.focus();
      }
    };
    const onEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        setOpen(false);
        triggerRef.current?.focus();
      }
    };
    window.addEventListener("pointerdown", onPointerDown);
    window.addEventListener("keydown", onEscape);
    return () => {
      window.removeEventListener("pointerdown", onPointerDown);
      window.removeEventListener("keydown", onEscape);
    };
  }, [open]);

  useEffect(() => {
    if (!open) {
      return;
    }
    const buttons = menuRef.current?.querySelectorAll<HTMLButtonElement>('[role="menuitem"]');
    buttons?.[activeIndex]?.focus();
  }, [open, activeIndex]);

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
        ref={triggerRef}
        type="button"
        onClick={() =>
          setOpen((prev) => {
            const next = !prev;
            if (next) {
              setActiveIndex(0);
            }
            return next;
          })
        }
        onKeyDown={(event) => {
          if (event.key === "ArrowDown" || event.key === "ArrowUp") {
            event.preventDefault();
            setOpen(true);
            setActiveIndex(event.key === "ArrowDown" ? 0 : Math.max(items.length - 1, 0));
          }
        }}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls={open ? menuId : undefined}
        className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-slate-200 bg-white text-slate-600 shadow-sm transition-colors hover:border-slate-300 hover:bg-slate-50 hover:text-slate-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-orange-500/40 dark:border-neutral-600 dark:bg-neutral-900 dark:text-neutral-300 dark:hover:border-neutral-500 dark:hover:bg-neutral-800 dark:hover:text-neutral-50 dark:focus-visible:ring-neutral-500/50"
      >
        <MoreVertical className="size-4 shrink-0" strokeWidth={2} aria-hidden />
        <span className="sr-only">Open row actions</span>
      </button>
      {open ? (
        <div
          ref={menuRef}
          id={menuId}
          role="menu"
          aria-orientation="vertical"
          onKeyDown={async (event) => {
            if (event.key === "Tab") {
              setOpen(false);
              return;
            }
            if (
              event.key === "ArrowDown" ||
              event.key === "ArrowUp" ||
              event.key === "Home" ||
              event.key === "End"
            ) {
              event.preventDefault();
              setActiveIndex((prev) =>
                getNextActiveMenuIndex(
                  prev < 0 ? 0 : prev,
                  items.length,
                  event.key as "ArrowDown" | "ArrowUp" | "Home" | "End",
                ),
              );
              return;
            }
            if (event.key !== "Enter" && event.key !== " ") {
              return;
            }
            event.preventDefault();
            const selected = items[activeIndex];
            if (!selected) {
              return;
            }
            const result = await selected.run();
            setOpen(false);
            triggerRef.current?.focus();
            showMessage(result);
          }}
          className="absolute right-0 top-9 z-[120] min-w-[220px] rounded-lg border border-slate-200 bg-white p-1 shadow-lg dark:border-neutral-700 dark:bg-neutral-900"
        >
          {items.map((item, index) => (
            <button
              key={item.id}
              type="button"
              role="menuitem"
              tabIndex={index === activeIndex ? 0 : -1}
              onFocus={() => setActiveIndex(index)}
              onClick={async () => {
                const result = await item.run();
                setOpen(false);
                triggerRef.current?.focus();
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
