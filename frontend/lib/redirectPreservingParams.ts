/**
 * Shared helper for server-side redirect stub routes.
 *
 * Next.js passes `searchParams` as a prop to server page components. This
 * builds a target URL that preserves the incoming query params so legacy
 * URLs forward cleanly to their canonical destination.
 *
 * `extraParams` is merged on top of the incoming params (e.g. a stub that
 * always wants `saved_incidents=1` set) — an incoming value for the same key
 * is overridden, and the extra param is never duplicated.
 */
export function redirectTargetPreservingParams(
  target: string,
  searchParams?: Record<string, string | string[] | undefined>,
  extraParams?: Record<string, string>,
): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(searchParams ?? {})) {
    if (Array.isArray(value)) {
      for (const item of value) {
        params.append(key, item);
      }
    } else if (typeof value === "string") {
      params.set(key, value);
    }
  }
  for (const [key, value] of Object.entries(extraParams ?? {})) {
    params.set(key, value);
  }
  const qs = params.toString();
  return qs ? `${target}?${qs}` : target;
}
