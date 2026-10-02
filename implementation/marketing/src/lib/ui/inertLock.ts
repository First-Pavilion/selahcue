/**
 * A reference-counted `inert` on the page behind a modal surface (the mobile nav sheet).
 *
 * `aria-modal="true"` asks assistive tech to ignore everything behind the dialog, and a Tab
 * trap keeps keyboard focus inside -- but neither stops a pointer, a screen-reader virtual
 * cursor in a browser that ignores `aria-modal`, or a stray Tab from a focus that has
 * landed on `<body>` (after a click on blank space inside the sheet) from reaching the page
 * underneath. `inert` removes the whole subtree from the tab order and the accessibility
 * tree, so the page behind genuinely is not there while the sheet is open.
 *
 * Same release rules as the scroll lock (`holdLock.ts`): idempotent, generation-checked,
 * released on every close path. A target that was ALREADY inert when we arrived is left
 * inert on release -- we only undo what we did.
 */

import { createHoldLock, type HoldLock } from './holdLock.ts'

export interface InertTarget {
  hasAttribute(name: string): boolean
  setAttribute(name: string, value: string): void
  removeAttribute(name: string): void
}

export type InertLock = HoldLock

export function createInertLock(getTargets: () => Array<InertTarget | null>): InertLock {
  let ours: InertTarget[] = []

  return createHoldLock(
    () => {
      ours = []
      for (const target of getTargets()) {
        if (!target || target.hasAttribute('inert')) continue
        target.setAttribute('inert', '')
        ours.push(target)
      }
    },
    () => {
      for (const target of ours) target.removeAttribute('inert')
      ours = []
    },
  )
}

/** The app root: everything the sheet's hamburger lives in. The sheet itself is teleported
 *  to <body>, outside `#app`, so it stays interactive. */
export const pageInertLock: InertLock = createInertLock(() =>
  typeof document === 'undefined' ? [] : [document.getElementById('app')],
)
