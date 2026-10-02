/**
 * A reference-counted hold with safe, idempotent, generation-checked releases.
 *
 * Two things in the mobile nav need "apply on first hold, undo on last release, and NEVER
 * leave it applied": the page scroll lock and `inert` on the page behind the sheet. Both are
 * built on this so the release rules are written -- and tested -- once.
 *
 * Every `acquire()` returns its own `release`, which is:
 *
 *  - IDEMPOTENT: a close handler AND an unmount hook can both call it; the second call is a
 *    no-op, so it cannot free a different holder's hold.
 *  - GENERATION-CHECKED: `releaseAll()` bumps a generation, so a release handed out BEFORE it
 *    becomes a no-op. Without that, `a = acquire(); releaseAll(); b = acquire(); a()` would
 *    decrement b's hold and unlock the page under a sheet that is still open (found in
 *    review of PR #140). A stale release must never touch a later hold.
 */

export interface HoldLock {
  /** Take a hold. Returns an idempotent release for exactly this hold. */
  acquire(): () => void
  /** Number of live holds. Exposed for tests and for the sweep's assertions. */
  readonly holds: number
  /** Drop every hold at once and invalidate every release handed out so far. */
  releaseAll(): void
}

export function createHoldLock(onFirst: () => void, onLast: () => void): HoldLock {
  let holds = 0
  let generation = 0

  return {
    acquire() {
      if (holds === 0) onFirst()
      holds += 1
      const mine = generation
      let released = false
      return () => {
        if (released) return
        released = true
        // A hold from before `releaseAll` was already dropped by it. Touching the count now
        // would take a LATER holder's hold away.
        if (mine !== generation) return
        holds -= 1
        if (holds === 0) onLast()
      }
    },
    get holds() {
      return holds
    },
    releaseAll() {
      generation += 1
      if (holds > 0) {
        holds = 0
        onLast()
      }
    },
  }
}
