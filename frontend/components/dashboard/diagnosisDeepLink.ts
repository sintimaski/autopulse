export function parseErrorGroupHash(hash: string): string | null {
  if (!hash.startsWith("#error-group:")) {
    return null;
  }
  const encoded = hash.slice("#error-group:".length);
  if (!encoded) {
    return null;
  }
  try {
    const decoded = decodeURIComponent(encoded);
    return decoded || null;
  } catch {
    return null;
  }
}

export function nextDeepLinkRetryAction(params: {
  targetGroupKey: string;
  lastRetriedKey: string | null;
  errorGroupPage: number;
  errorGroupLimit: number;
}): "none" | "reset_page" | "expand_limit" {
  const { targetGroupKey, lastRetriedKey, errorGroupPage, errorGroupLimit } = params;
  if (targetGroupKey.length === 0 || lastRetriedKey === targetGroupKey) {
    return "none";
  }
  if (errorGroupPage > 0) {
    return "reset_page";
  }
  if (errorGroupLimit < 50) {
    return "expand_limit";
  }
  return "none";
}

export function isDiagnosisScopePartial(params: {
  requestSampleCount: number;
  requestTotalCount: number;
  requestOffset: number;
  errorGroupSampleCount: number;
  errorGroupTotalCount: number;
  errorGroupPage: number;
  hasScopeNarrowing: boolean;
}): boolean {
  const {
    requestSampleCount,
    requestTotalCount,
    requestOffset,
    errorGroupSampleCount,
    errorGroupTotalCount,
    errorGroupPage,
    hasScopeNarrowing,
  } = params;
  const requestSamplePartial = requestTotalCount > requestSampleCount || requestOffset > 0;
  const errorGroupsPartial = errorGroupTotalCount > errorGroupSampleCount || errorGroupPage > 0;
  return requestSamplePartial || errorGroupsPartial || hasScopeNarrowing;
}
