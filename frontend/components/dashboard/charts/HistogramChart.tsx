"use client";

type HistogramBucket = {
  label: string;
  count: number;
};

export function HistogramChart({
  buckets,
  barColor = "bg-sky-500/80 dark:bg-sky-400/80",
  onBucketClick,
}: {
  buckets: HistogramBucket[];
  barColor?: string;
  onBucketClick?: (bucket: HistogramBucket) => void;
}) {
  if (!buckets.length) {
    return <p className="text-sm text-slate-500 dark:text-neutral-400">No distribution data available.</p>;
  }
  let max = 1;
  for (const bucket of buckets) {
    if (bucket.count > max) {
      max = bucket.count;
    }
  }
  return (
    <div className="space-y-2">
      <ul className="space-y-1.5">
        {buckets.map((bucket) => {
          const width = Math.max(3, Math.round((bucket.count / max) * 100));
          return (
            <li
              key={bucket.label}
              title={`${bucket.label}: ${bucket.count} requests`}
              onClick={onBucketClick ? () => onBucketClick(bucket) : undefined}
              className={`grid grid-cols-[90px_1fr_auto] items-center gap-2 ${onBucketClick ? "cursor-pointer rounded px-1 py-0.5 hover:bg-slate-100/70 dark:hover:bg-neutral-800/60" : ""}`}
            >
              <span className="text-[11px] text-slate-600 dark:text-neutral-300">{bucket.label}</span>
              <div className="h-2 rounded-full bg-slate-200/80 dark:bg-neutral-800">
                <div className={`h-2 rounded-full ${barColor}`} style={{ width: `${width}%` }} />
              </div>
              <span className="text-[11px] tabular-nums text-slate-700 dark:text-neutral-300">
                {bucket.count}
              </span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

export type { HistogramBucket };
