"use client";

import { useLayoutEffect, useRef, type ReactNode } from "react";

type ExpandableTableRowProps = {
  rowId: string;
  open: boolean;
  onToggle: (rowId: string) => void;
  colSpan: number;
  renderSummary: () => ReactNode;
  renderDetails: () => ReactNode;
  summaryClassName?: string;
  detailsRowClassName?: string;
  detailsCellClassName?: string;
};

export function ExpandableTableRow({
  rowId,
  open,
  onToggle,
  colSpan,
  renderSummary,
  renderDetails,
  summaryClassName,
  detailsRowClassName,
  detailsCellClassName,
}: ExpandableTableRowProps) {
  const detailsId = `${rowId}-details`;
  const summaryRef = useRef<HTMLTableRowElement>(null);
  const detailsCellRef = useRef<HTMLTableCellElement>(null);

  useLayoutEffect(() => {
    if (!open || !summaryRef.current) {
      return;
    }
    const summaryRow = summaryRef.current;
    const detailsCell = detailsCellRef.current;
    queueMicrotask(() => {
      summaryRow.scrollIntoView({ block: "nearest", inline: "nearest" });
      detailsCell?.focus({ preventScroll: true });
    });
  }, [open]);

  return (
    <>
      <tr
        ref={summaryRef}
        className={`cursor-pointer outline-none transition-colors focus-within:ring-2 focus-within:ring-sky-400/50 active:brightness-95 dark:focus-within:ring-neutral-500/50 ${summaryClassName ?? ""}`}
        onClick={() => onToggle(rowId)}
      >
        <td className="px-2 py-2 align-top" onClick={(e) => e.stopPropagation()}>
          <button
            type="button"
            aria-expanded={open}
            aria-controls={detailsId}
            onClick={(e) => {
              e.stopPropagation();
              onToggle(rowId);
            }}
            className="inline-flex h-7 w-7 items-center justify-center rounded text-slate-700 outline-none transition-colors hover:bg-slate-200/90 focus-visible:ring-2 focus-visible:ring-sky-400/60 dark:text-neutral-200 dark:hover:bg-neutral-800/90 dark:focus-visible:ring-neutral-500/60"
          >
            <span aria-hidden className={`transition-transform ${open ? "rotate-90" : ""}`}>
              <span className="inline-block text-[1.15em]">▸</span>
            </span>
            <span className="sr-only">{open ? "Collapse row details" : "Expand row details"}</span>
          </button>
        </td>
        {renderSummary()}
      </tr>
      {open ? (
        <tr id={detailsId} className={detailsRowClassName}>
          <td
            ref={detailsCellRef}
            tabIndex={-1}
            colSpan={colSpan}
            className={`scroll-mt-24 outline-none focus:outline-none ${detailsCellClassName ?? ""}`}
          >
            {renderDetails()}
          </td>
        </tr>
      ) : null}
    </>
  );
}
