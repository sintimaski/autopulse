/** Wrap WHERE fragments for log-query validation (same grammar as SQL log queries). */
export function wrapEventSqlWhereForValidate(whereFragment: string): string {
  const t = whereFragment.trim();
  if (!t) {
    return "";
  }
  return `SELECT * FROM events WHERE ${t} ORDER BY timestamp DESC LIMIT 100`;
}
