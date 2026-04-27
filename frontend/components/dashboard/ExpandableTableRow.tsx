"use client";

import type { ReactNode } from "react";

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

  return (
    <>
      <tr
        role="button"
        tabIndex={0}
        aria-expanded={open}
        aria-controls={detailsId}
        onClick={() => onToggle(rowId)}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            onToggle(rowId);
          }
        }}
        className={`cursor-pointer outline-none focus-visible:ring-2 focus-visible:ring-sky-400/60 dark:focus-visible:ring-neutral-500/60 ${summaryClassName ?? ""}`}
      >
        <td className="px-2 py-2 align-top">
          <span className="inline-flex h-6 w-6 items-center justify-center text-slate-700 dark:text-neutral-200">
            <span aria-hidden className={`transition-transform ${open ? "rotate-90" : ""}`}>
              <span className="inline-block text-[1.15em]">▸</span>
            </span>
          </span>
          <span className="sr-only">{open ? "Collapse row details" : "Expand row details"}</span>
        </td>
        {renderSummary()}
      </tr>
      {open ? (
        <tr id={detailsId} className={detailsRowClassName}>
          <td colSpan={colSpan} className={detailsCellClassName}>
            {renderDetails()}
          </td>
        </tr>
      ) : null}
    </>
  );
}
