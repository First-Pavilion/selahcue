/**
 * Does this box scroll sideways? A table wrapper is only a keyboard-focusable, named
 * scroll region WHILE it overflows; a table that fits needs no tab stop and no region
 * landmark (the page would otherwise carry one extra tab stop and landmark per table).
 * One pixel of slack absorbs sub-pixel rounding.
 */
export function isOverflowing(box: { readonly scrollWidth: number; readonly clientWidth: number }): boolean {
  return box.scrollWidth - box.clientWidth > 1
}
