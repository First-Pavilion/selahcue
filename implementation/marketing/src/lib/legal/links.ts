/**
 * Which link targets a legal document is allowed to contain.
 *
 * The generator refuses any markdown link that fails this check, and the renderer asks it
 * again before emitting an `<a>`, so a bad target has to get past two independent gates.
 * Anything that is not on the list below never becomes a link at all.
 *
 *   /path              same-site (but not protocol-relative `//host`, and no backslash —
 *                      browsers treat `/\host` as `//host`)
 *   https://host/...   external, always https
 *   mailto:a@b         a plain address; no `?subject=` or other header smuggling
 */
export type HrefKind = 'internal' | 'external' | 'mailto'

export function classifyHref(href: string): HrefKind | null {
  if (href.startsWith('/') && !href.startsWith('//') && !href.includes('\\')) return 'internal'
  if (/^https:\/\/[^\s/?#]+/i.test(href) && !/\s/.test(href)) return 'external'
  if (/^mailto:[^\s@/?#:]+@[^\s@/?#:]+$/i.test(href)) return 'mailto'
  return null
}
