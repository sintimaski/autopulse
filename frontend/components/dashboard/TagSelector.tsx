"use client";

type Accent = "sky" | "violet" | "slate";

const accentStyles: Record<Accent, { on: string; off: string }> = {
  sky: {
    on: "border-sky-500 bg-sky-600 text-white shadow-sm dark:border-sky-700 dark:bg-sky-950/60 dark:text-sky-100",
    off: "border-slate-200 bg-white text-slate-700 hover:border-sky-300 hover:bg-sky-50 dark:border-neutral-600 dark:bg-neutral-900 dark:text-neutral-200 dark:hover:border-sky-700 dark:hover:bg-sky-950/30",
  },
  violet: {
    on: "border-violet-500 bg-violet-600 text-white shadow-sm dark:border-violet-700 dark:bg-violet-950/60 dark:text-violet-100",
    off: "border-slate-200 bg-white text-slate-700 hover:border-violet-300 hover:bg-violet-50 dark:border-neutral-600 dark:bg-neutral-900 dark:text-neutral-200 dark:hover:border-violet-700 dark:hover:bg-violet-950/30",
  },
  slate: {
    on: "border-slate-500 bg-slate-700 text-white shadow-sm dark:border-neutral-500 dark:bg-neutral-700 dark:text-neutral-100",
    off: "border-slate-200 bg-white text-slate-700 hover:border-slate-300 hover:bg-slate-50 dark:border-neutral-600 dark:bg-neutral-900 dark:text-neutral-200 dark:hover:border-neutral-500 dark:hover:bg-neutral-800",
  },
};

type TagSelectorProps = {
  id: string;
  label: string;
  options: string[];
  selected: Set<string>;
  onToggle: (value: string) => void;
  emptyText: string;
  accent?: Accent;
  helperText?: string;
};

export function TagSelector({
  id,
  label,
  options,
  selected,
  onToggle,
  emptyText,
  accent = "slate",
  helperText,
}: TagSelectorProps) {
  const style = accentStyles[accent];
  return (
    <div role="group" aria-labelledby={`${id}-label`} className="space-y-2">
      <div className="flex flex-wrap items-center gap-2">
        <p id={`${id}-label`} className="text-sm font-semibold text-slate-700 dark:text-neutral-200">
          {label}
        </p>
        <span className="rounded-full bg-slate-200 px-2 py-0.5 text-xs font-medium text-slate-700 dark:bg-neutral-700 dark:text-neutral-200">
          {selected.size} selected
        </span>
      </div>
      {helperText ? <p className="text-xs text-slate-500 dark:text-neutral-400">{helperText}</p> : null}
      <div className="flex flex-wrap gap-2">
        {options.length === 0 ? (
          <p className="text-sm text-slate-500 dark:text-neutral-400">{emptyText}</p>
        ) : (
          options.map((option) => {
            const isSelected = selected.has(option);
            return (
              <button
                key={option}
                type="button"
                aria-pressed={isSelected}
                onClick={() => onToggle(option)}
                className={`rounded-full border px-3 py-1.5 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500/40 dark:focus-visible:ring-neutral-500/50 ${
                  isSelected ? style.on : style.off
                }`}
              >
                {option}
              </button>
            );
          })
        )}
      </div>
    </div>
  );
}
