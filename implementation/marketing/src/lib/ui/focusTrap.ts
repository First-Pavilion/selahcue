/**
 * Pure helpers for keeping Tab inside an open modal surface (the mobile nav sheet).
 *
 * The DOM-facing code gathers the focusable elements and the currently focused one; the
 * decision "where should focus go now?" is a pure function so it can be tested without a
 * browser.
 */

/** Elements a keyboard user can land on. Disabled controls and negative tabindex are out. */
export const FOCUSABLE_SELECTOR =
  'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'

/**
 * Given `count` focusable elements and the index of the one that has focus (`-1` when
 * focus is outside the list), return the index Tab / Shift+Tab should move to, wrapping at
 * both ends. Returns `null` when there is nothing to trap to (no focusable elements), in
 * which case the caller should simply prevent the default and keep focus where it is.
 */
export function nextTrapIndex(count: number, current: number, backwards: boolean): number | null {
  if (count <= 0) return null
  if (current < 0 || current >= count) return backwards ? count - 1 : 0
  if (backwards) return current === 0 ? count - 1 : current - 1
  return current === count - 1 ? 0 : current + 1
}
