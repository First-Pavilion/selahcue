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
 * So the lock is a COUNT, not a flag, and every `acquire()` returns its own idempotent
 * `release`:
 *
 *  - two overlapping holders (a nav sheet and a dialog) do not unlock each other early,
 *  - releasing twice (a close handler AND an unmount hook) cannot drive the count
 *    negative and unlock someone else's hold,
 *  - the ORIGINAL inline `overflow` values are captured on the first acquire and put back
 *    on the last release, so a page that already set its own `overflow` gets it back
 *    rather than an empty string.
 *
 * The target list is injected so this is testable under `node --test` with plain objects.
 */

export interface ScrollLockTarget {
  style: { overflow: string }
}

export interface ScrollLock {
  /** Take a hold. Returns an idempotent release for exactly this hold. */
  acquire(): () => void
  /** Number of live holds. Exposed for tests and for the sweep's assertions. */
  readonly holds: number
  /** Drop every hold at once. The escape hatch for "something is wrong, unlock". */
  releaseAll(): void
}

export function createScrollLock(getTargets: () => ScrollLockTarget[]): ScrollLock {
  let holds = 0
  let saved: Array<{ target: ScrollLockTarget; overflow: string }> = []

  const lockTargets = () => {
    saved = getTargets().map((target) => ({ target, overflow: target.style.overflow }))
    for (const { target } of saved) target.style.overflow = 'hidden'
  }

  const unlockTargets = () => {
    for (const { target, overflow } of saved) target.style.overflow = overflow
    saved = []
  }

  return {
    acquire() {
      if (holds === 0) lockTargets()
      holds += 1
      let released = false
      return () => {
        if (released) return
        released = true
        // `releaseAll` may already have zeroed the count; never go below it.
        if (holds === 0) return
        holds -= 1
        if (holds === 0) unlockTargets()
      }
    },
    get holds() {
      return holds
    },
    releaseAll() {
      holds = 0
      unlockTargets()
    },
  }
}

/** The app-wide lock: the root element and the body, because browsers differ on which scrolls. */
export const pageScrollLock: ScrollLock = createScrollLock(() =>
  typeof document === 'undefined' ? [] : [document.documentElement, document.body],
)
