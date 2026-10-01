/**
 * A reference-counted page scroll lock.
 *
 * The mobile nav sheet (and any later modal) must stop the page behind it from
 * scrolling, and -- the part that actually goes wrong -- must ALWAYS give scrolling back.
 * A lock that is taken in an `open()` handler and released in a `close()` handler leaks
 * on every path that skips `close()`: a route change, a component unmount, a viewport
 * that grows past the breakpoint while the sheet is open. The visitor is then left on a
 * page that will not scroll, with nothing on screen to explain it.
 *
 * So the lock is a COUNT (see `holdLock.ts` for the release rules), and the ORIGINAL inline
 * `overflow` values are captured on the first acquire and put back on the last release, so a
 * page that already set its own `overflow` gets it back rather than an empty string.
 *
 * The target list is injected so this is testable under `node --test` with plain objects.
 */

import { createHoldLock, type HoldLock } from './holdLock.ts'

export interface ScrollLockTarget {
  style: { overflow: string }
}

export type ScrollLock = HoldLock

export function createScrollLock(getTargets: () => ScrollLockTarget[]): ScrollLock {
  let saved: Array<{ target: ScrollLockTarget; overflow: string }> = []

  return createHoldLock(
    () => {
      saved = getTargets().map((target) => ({ target, overflow: target.style.overflow }))
      for (const { target } of saved) target.style.overflow = 'hidden'
    },
    () => {
      for (const { target, overflow } of saved) target.style.overflow = overflow
      saved = []
    },
  )
}

/** The app-wide lock: the root element and the body, because browsers differ on which scrolls. */
export const pageScrollLock: ScrollLock = createScrollLock(() =>
  typeof document === 'undefined' ? [] : [document.documentElement, document.body],
)
