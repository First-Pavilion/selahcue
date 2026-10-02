/**
 * Put a deep-linked section back in the right place once the web fonts have loaded.
 *
 * On a cold load with a #hash the router scrolls to the anchor immediately. The page then
 * repaints in Inter (Google Fonts, `display=swap`), the text reflows, and content above the
 * anchor changes height, so the section ends up 70-80px below the navbar instead of the
 * intended 16px. This corrects that ONCE, after `document.fonts.ready`:
 *
 *  - one shot: a single promise chain, no timers, no retry;
 *  - cold load only: it is started once at startup, so later in-app navigation never uses it
 *    (the fonts are already in by then);
 *  - never fights the reader: if they used the wheel, touch, keyboard or pointer, or the hash
 *    changed, while the fonts were loading, it does nothing;
 *  - bounded: if the fonts take longer than `deadlineMs` it does nothing (a late jump is worse
 *    than a slightly low anchor), and if they were already loaded there is nothing to correct;
 *  - leaves nothing behind: the input listeners are removed on every exit path.
 *
 * Pure and dependency-injected so `node --test` can drive it; `reanchorForBrowser` is the real
 * binding, called from `main.ts`.
 */
import { isAnchoredRoute, siteScrollBehavior } from '../router/scroll.ts'

export type ReanchorOutcome =
  | 'reapplied'
  | 'no-hash'
  | 'not-anchored'
  | 'no-fonts'
  | 'fonts-already-loaded'
  | 'fonts-failed'
  | 'user-moved'
  | 'hash-changed'
  | 'too-late'
  | 'reapply-failed'

export interface ReanchorDeps {
  hash(): string
  fontsStatus(): string | undefined
  fontsReady(): Promise<unknown> | undefined
  now(): number
  /** Subscribe to "the reader moved the page". Returns the unsubscribe. */
  onUserInput(handler: () => void): () => void
  reapply(): void
  deadlineMs?: number
}

export const REANCHOR_DEADLINE_MS = 3000

export async function reanchorAfterFonts(d: ReanchorDeps): Promise<ReanchorOutcome> {
  const hash = d.hash()
  if (hash === '' || hash === '#') return 'no-hash'
  const ready = d.fontsReady()
  if (!ready) return 'no-fonts'
  if (d.fontsStatus() === 'loaded') return 'fonts-already-loaded'

  const started = d.now()
  let moved = false
  const unsubscribe = d.onUserInput(() => {
    moved = true
  })
  try {
    try {
      await ready
    } catch {
      return 'fonts-failed'
    }
    if (moved) return 'user-moved'
    if (d.hash() !== hash) return 'hash-changed'
    if (d.now() - started > (d.deadlineMs ?? REANCHOR_DEADLINE_MS)) return 'too-late'
    try {
      d.reapply()
    } catch {
      return 'reapply-failed'
    }
    return 'reapplied'
  } finally {
    unsubscribe()
  }
}

/** `scrollTo` top for an element: where it is now, plus how far the page is scrolled, minus the clearance. */
export function anchorScrollTop(elementTop: number, scrollY: number, clearance: number): number {
  return Math.max(0, elementTop + scrollY - clearance)
}

const INPUT_EVENTS = ['wheel', 'touchstart', 'keydown', 'pointerdown'] as const

/** The real browser. `route.name` decides whether the anchor clearance applies (router/scroll.ts). */
export function reanchorForBrowser(route: { name?: unknown }): Promise<ReanchorOutcome> {
  // Only the pages whose anchors sit below the navbar (blog, docs, support); other pages keep
  // exactly the scroll the router gave them.
  if (!isAnchoredRoute(route.name)) return Promise.resolve('not-anchored')
  return reanchorAfterFonts({
    hash: () => window.location.hash,
    fontsStatus: () => document.fonts?.status,
    fontsReady: () => document.fonts?.ready,
    now: () => performance.now(),
    onUserInput: (handler) => {
      for (const type of INPUT_EVENTS) window.addEventListener(type, handler, { passive: true, capture: true })
      return () => {
        for (const type of INPUT_EVENTS) window.removeEventListener(type, handler, { capture: true })
      }
    },
    reapply: () => {
      const position = siteScrollBehavior({ hash: window.location.hash, name: route.name })
      if (!('el' in position)) return
      const target = document.querySelector(position.el)
      if (!target) return
      // `instant`, not the router's smooth: this is a correction, not a navigation.
      window.scrollTo({
        top: anchorScrollTop(target.getBoundingClientRect().top, window.scrollY, position.top),
        behavior: 'instant',
      })
    },
  })
}
