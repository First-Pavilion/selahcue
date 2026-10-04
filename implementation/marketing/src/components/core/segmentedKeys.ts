/**
 * The keyboard rules of a segmented control that behaves as a radio group (WAI-ARIA "radio group"):
 * the arrow keys move the choice, Home and End jump to the ends, and a disabled option is skipped.
 *
 * Pure, so node can test the one decision that is easy to get subtly wrong (wrap-around, skipping a
 * disabled option, a lone option): `tests/corePages.test.ts`. `SegmentedToggle.vue` calls it.
 */

/**
 * The index the choice should move to for this key, or `null` when the key means nothing here
 * (Tab, Enter, a letter): the caller then leaves the event alone.
 *
 * `enabled[i]` is false for a disabled option. When no OTHER option is enabled the current index is
 * returned, so the choice never moves to something that cannot be chosen.
 */
export function nextIndex(key: string, current: number, enabled: readonly boolean[]): number | null {
  const count = enabled.length
  if (count === 0) return null
  const isEnabled = (i: number): boolean => enabled[i] === true

  if (key === 'Home') {
    const first = enabled.findIndex((e) => e)
    return first === -1 ? null : first
  }
  if (key === 'End') {
    const last = enabled.lastIndexOf(true)
    return last === -1 ? null : last
  }

  const step = key === 'ArrowRight' || key === 'ArrowDown' ? 1 : key === 'ArrowLeft' || key === 'ArrowUp' ? -1 : 0
  if (step === 0) return null

  for (let n = 1; n <= count; n++) {
    const i = (((current + step * n) % count) + count) % count
    if (isEnabled(i)) return i
  }
  return current
}
