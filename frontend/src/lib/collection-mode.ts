/**
 * "AI 实验共建模式" is a URL flag, not a separate flow.
 *
 * Both entries open the very same experiment workspace; the only difference is
 * whether the contribution panel is active and whether the backend stores a
 * collection session.  Keeping the flag in the URL means the mode survives
 * refreshes, back/forward navigation and shared links, and no experiment page is
 * duplicated.  These helpers are pure so they can be used anywhere.
 */

export const COLLECTION_MODE_PARAM = "mode";
export const COLLECTION_MODE_VALUE = "collection";

/** True when a query string selects the AI co-build entry. */
export function isCollectionMode(params: URLSearchParams | null | undefined): boolean {
  if (!params) return false;
  const value = (params.get(COLLECTION_MODE_PARAM) ?? "").toLowerCase();
  return value === COLLECTION_MODE_VALUE || value === "co-build" || value === "true";
}

/** Append the co-build flag to a link when the mode is active. */
export function withCollectionMode(href: string, enabled: boolean): string {
  if (!enabled) return href;
  const separator = href.includes("?") ? "&" : "?";
  return `${href}${separator}${COLLECTION_MODE_PARAM}=${COLLECTION_MODE_VALUE}`;
}
