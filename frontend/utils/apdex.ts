/** Standard Apdex thresholds (ms): satisfied bucket and tolerating bucket. */
export const APDEX_THRESHOLDS_MS = { satisfied: 300, tolerated: 1200 } as const;

/**
 * Apdex score from raw latency samples (one sample per satisfied/tolerating/frustrated request).
 * Returns 1 when there are no samples (neutral default for empty windows).
 */
export function apdexScoreFromLatenciesMs(latenciesMs: number[]): number {
  if (!latenciesMs.length) {
    return 1;
  }
  const { satisfied, tolerated } = APDEX_THRESHOLDS_MS;
  let sum = 0;
  for (const ms of latenciesMs) {
    if (ms <= satisfied) {
      sum += 1;
    } else if (ms <= tolerated) {
      sum += 0.5;
    }
  }
  return sum / latenciesMs.length;
}
