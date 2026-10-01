/**
 * Responsive layer (GAP-07, ClickUp 17tnw2b0q9g).
 *
 * Two kinds of test live here, and the difference matters:
 *
 *  - BEHAVIOUR of the pure helpers the mobile nav sheet is built from -- the scroll lock and
 *    the focus-trap index. These run the real code against plain objects.
 *  - SOURCE tripwires on what CSS and templates must keep doing. They are lexical, so they
 *    are cheap first-line guards, not the proof: the proof is `scripts/responsive_sweep.py`,
 *    which drives the built site at 320/375/768/1024/1440 in a real browser (including the
 *    sheet's open/Escape/scrim/route-change/resize paths). Each tripwire below says which
 *    sweep check actually carries its weight.
 */
import assert from 'node:assert/strict'
import test, { describe } from 'node:test'
import { readdirSync, readFileSync, statSync } from 'node:fs'
import { join } from 'node:path'

import { MOBILE_MAX_WIDTH, MOBILE_QUERY } from '../src/lib/ui/breakpoints.ts'
import { FOCUSABLE_SELECTOR, nextTrapIndex } from '../src/lib/ui/focusTrap.ts'
import { createScrollLock, type ScrollLockTarget } from '../src/lib/ui/scrollLock.ts'
import { createInertLock, type InertTarget } from '../src/lib/ui/inertLock.ts'

const SRC = new URL('../src/', import.meta.url)
const read = (relative: string) => readFileSync(new URL(relative, SRC), 'utf8')

function walk(dir: string, out: string[] = []): string[] {
  for (const name of readdirSync(dir)) {
    const full = join(dir, name)
    if (statSync(full).isDirectory()) walk(full, out)
    else if (full.endsWith('.vue')) out.push(full)
  }
  return out
}
const SFCS = walk(new URL('.', SRC).pathname)

const target = (overflow = ''): ScrollLockTarget => ({ style: { overflow } })

describe('scroll lock', () => {
  test('locks on the first hold and restores on the last release', () => {
    const html = target()
    const body = target()
    const lock = createScrollLock(() => [html, body])

    const release = lock.acquire()
    assert.equal(html.style.overflow, 'hidden')
    assert.equal(body.style.overflow, 'hidden')
    assert.equal(lock.holds, 1)

    release()
    assert.equal(html.style.overflow, '')
    assert.equal(body.style.overflow, '')
    assert.equal(lock.holds, 0)
  })

  test('puts back the ORIGINAL inline overflow, not an empty string', () => {
    // A page that already set its own `overflow` must get it back. Resetting to '' would be
    // a quiet regression the first time anything else touched these properties.
    const html = target('scroll')
    const body = target('auto')
    const lock = createScrollLock(() => [html, body])
    lock.acquire()()
    assert.equal(html.style.overflow, 'scroll')
    assert.equal(body.style.overflow, 'auto')
  })

  test('overlapping holders do not unlock each other early', () => {
    const body = target()
    const lock = createScrollLock(() => [body])
    const releaseSheet = lock.acquire()
    const releaseDialog = lock.acquire()
    assert.equal(lock.holds, 2)

    releaseSheet()
    assert.equal(body.style.overflow, 'hidden', 'the dialog still holds the lock')
    assert.equal(lock.holds, 1)

    releaseDialog()
    assert.equal(body.style.overflow, '')
    assert.equal(lock.holds, 0)
  })

  test('a release is idempotent -- a close handler AND an unmount hook cannot over-release', () => {
    const body = target()
    const lock = createScrollLock(() => [body])
    const releaseA = lock.acquire()
    const releaseB = lock.acquire()

    releaseA()
    releaseA() // a second call for the SAME hold must not free B's hold
    releaseA()
    assert.equal(lock.holds, 1)
    assert.equal(body.style.overflow, 'hidden')

    releaseB()
    assert.equal(lock.holds, 0)
    assert.equal(body.style.overflow, '')
  })

  test('releaseAll always unlocks, and a stale release afterwards cannot go negative or re-lock', () => {
    const body = target('')
    const lock = createScrollLock(() => [body])
    const stale = lock.acquire()
    lock.acquire()
    lock.releaseAll()
    assert.equal(body.style.overflow, '')
    assert.equal(lock.holds, 0)

    stale() // belongs to a hold releaseAll already dropped
    assert.equal(lock.holds, 0, 'count must not go below zero')
    assert.equal(body.style.overflow, '')

    // and the lock still works afterwards
    const again = lock.acquire()
    assert.equal(body.style.overflow, 'hidden')
    again()
    assert.equal(body.style.overflow, '')
  })

  test('a stale release from BEFORE releaseAll cannot drop a LATER hold (review of #140)', () => {
    // a = acquire(); releaseAll(); b = acquire(); a()
    // The old count-only implementation decremented b's hold here and unlocked the page under
    // a sheet that was still open. A generation id makes `a` a no-op once releaseAll ran.
    const body = target()
    const lock = createScrollLock(() => [body])
    const a = lock.acquire()
    lock.releaseAll()
    assert.equal(body.style.overflow, '')

    const b = lock.acquire()
    assert.equal(body.style.overflow, 'hidden')
    assert.equal(lock.holds, 1)

    a() // stale
    assert.equal(lock.holds, 1, "a's stale release must not touch b's hold")
    assert.equal(body.style.overflow, 'hidden', 'the page was unlocked while b still holds it')

    b()
    assert.equal(lock.holds, 0)
    assert.equal(body.style.overflow, '')
  })

  test('a lock taken after targets changed captures the CURRENT values', () => {
    const body = target('')
    const lock = createScrollLock(() => [body])
    lock.acquire()()
    body.style.overflow = 'clip'
    const release = lock.acquire()
    release()
    assert.equal(body.style.overflow, 'clip')
  })
})

function inertTarget(inert = false): InertTarget & { inert: boolean; calls: string[] } {
  const t = {
    inert,
    calls: [] as string[],
    hasAttribute: (name: string) => name === 'inert' && t.inert,
    setAttribute: (name: string) => {
      if (name === 'inert') t.inert = true
      t.calls.push('set')
    },
    removeAttribute: (name: string) => {
      if (name === 'inert') t.inert = false
      t.calls.push('remove')
    },
  }
  return t
}

describe('inert lock (page behind the sheet)', () => {
  test('makes the target inert while held and restores it on the last release', () => {
    const app = inertTarget()
    const lock = createInertLock(() => [app])
    const release = lock.acquire()
    assert.equal(app.inert, true)
    release()
    assert.equal(app.inert, false)
  })

  test('only undoes what it did: a target that was already inert stays inert', () => {
    const app = inertTarget(true)
    const lock = createInertLock(() => [app])
    lock.acquire()()
    assert.equal(app.inert, true)
    assert.deepEqual(app.calls, [], 'must not touch a target it did not inert')
  })

  test('a missing target (no #app yet) is skipped, not a crash', () => {
    const lock = createInertLock(() => [null])
    assert.doesNotThrow(() => lock.acquire()())
  })

  test('releases are idempotent and a stale release cannot drop a later hold', () => {
    const app = inertTarget()
    const lock = createInertLock(() => [app])
    const a = lock.acquire()
    lock.releaseAll()
    assert.equal(app.inert, false)
    const b = lock.acquire()
    a()
    a()
    assert.equal(app.inert, true, 'stale release un-inerted the page under an open sheet')
    b()
    assert.equal(app.inert, false)
  })
})

describe('focus trap index', () => {
  test('Tab advances and wraps from the last element to the first', () => {
    assert.equal(nextTrapIndex(4, 0, false), 1)
    assert.equal(nextTrapIndex(4, 2, false), 3)
    assert.equal(nextTrapIndex(4, 3, false), 0)
  })

  test('Shift+Tab goes back and wraps from the first element to the last', () => {
    assert.equal(nextTrapIndex(4, 3, true), 2)
    assert.equal(nextTrapIndex(4, 1, true), 0)
    assert.equal(nextTrapIndex(4, 0, true), 3)
  })

  test('focus outside the list is pulled in at the matching end', () => {
    assert.equal(nextTrapIndex(4, -1, false), 0)
    assert.equal(nextTrapIndex(4, -1, true), 3)
    assert.equal(nextTrapIndex(4, 9, false), 0)
  })

  test('nothing focusable means nothing to trap to', () => {
    assert.equal(nextTrapIndex(0, -1, false), null)
    assert.equal(nextTrapIndex(0, 0, true), null)
  })

  test('a single control traps onto itself in both directions', () => {
    assert.equal(nextTrapIndex(1, 0, false), 0)
    assert.equal(nextTrapIndex(1, 0, true), 0)
  })

  test('the focusable selector keeps disabled and tabindex=-1 out', () => {
    assert.match(FOCUSABLE_SELECTOR, /button:not\(\[disabled\]\)/)
    assert.match(FOCUSABLE_SELECTOR, /\[tabindex\]:not\(\[tabindex="-1"\]\)/)
  })
})

describe('breakpoints', () => {
  test('mobile is strictly below 768 and the ranges are complementary (design 8a)', () => {
    // `767.98px`, not `767px`: at a fractional viewport width (browser zoom gives 767.5px)
    // `max-width: 767px` and `min-width: 768px` BOTH miss, and the page gets half of each layout.
    assert.equal(MOBILE_MAX_WIDTH, 767.98)
    assert.equal(MOBILE_QUERY, '(max-width: 767.98px)')
  })

  test('every media query that ends a range just below a breakpoint uses the .98 form', () => {
    // The sweep renders 767/768 and 1199/1200 in a real browser; this is the cheap tripwire
    // that keeps the whole-pixel form (and the old `768px` off-by-one) out of the source.
    const offenders: string[] = []
    for (const file of SFCS) {
      for (const line of readFileSync(file, 'utf8').split('\n')) {
        if (!line.includes('@media')) continue
        if (/max-width:\s*(767|1023|1099|1199|1024|768)px/.test(line)) offenders.push(`${file}: ${line.trim()}`)
      }
    }
    for (const css of ['assets/styles/main.css', 'assets/styles/auth.css']) {
      for (const line of read(css).split('\n')) {
        if (line.includes('@media') && /max-width:\s*(767|1023|1099|1199|1024|768)px/.test(line)) offenders.push(`${css}: ${line.trim()}`)
      }
    }
    assert.deepEqual(offenders, [])
  })

  test('the JS mobile query is the exact complement of the CSS tablet start (768)', () => {
    const navbar = read('components/Navbar.vue')
    assert.match(navbar, /@media \(min-width: 768px\)/)
    assert.equal(MOBILE_MAX_WIDTH + 0.02, 768)
  })

  test('main.css steps --page-gutter 24 -> 48 -> 20 at the design breakpoints', () => {
    const tokens = read('assets/styles/tokens.css')
    const main = read('assets/styles/main.css')
    assert.match(tokens, /--page-gutter:\s*24px/)
    const tablet = main.match(/@media \(max-width: 1199\.98px\)\s*\{[^}]*\}/)?.[0] ?? ''
    const mobile = main.match(/@media \(max-width: 767\.98px\)\s*\{[^}]*\}/)?.[0] ?? ''
    assert.match(tablet, /--page-gutter:\s*48px/)
    assert.match(mobile, /--page-gutter:\s*20px/)
    assert.match(mobile, /--font-h1:\s*700 36px\/40px/)
  })

  test('the footer takes its mobile layout from JS state, not a second CSS breakpoint', () => {
    // Footer collapse behaviour (JS) and stacked layout (CSS) must flip together. The
    // layout is keyed on `.is-mobile`, which Footer.vue sets from MOBILE_QUERY.
    const footer = read('components/Footer.vue')
    assert.match(footer, /import \{ MOBILE_QUERY \} from '@\/lib\/ui\/breakpoints\.ts'/)
    assert.match(footer, /'is-mobile': isMobile/)
    const style = footer.slice(footer.indexOf('<style'))
    assert.equal(/@media \(max-width: 7\d\d(\.98)?px\)/.test(style), false, 'a hand-typed mobile breakpoint crept back into Footer.vue')
  })
})

describe('page containers use the responsive gutter', () => {
  test('no view or shell container hard-codes 24px side padding', () => {
    // A hard-coded `padding: 0 24px` on a container is exactly what kept every page at a
    // desktop gutter on a phone. The sweep's "within 8px of the screen edge" check is what
    // would catch a missing gutter in the browser; this catches the regression at the source.
    const offenders = SFCS.filter((file) => {
      if (!/[/\\](views|components)[/\\]/.test(file)) return false
      const css = readFileSync(file, 'utf8').split('<style')[1] ?? ''
      return /\.container\b[^{]*\{[^}]*padding:\s*0\s+24px/.test(css)
    })
    assert.deepEqual(offenders, [])
  })
})

describe('mobile nav sheet wiring (Navbar.vue)', () => {
  const navbar = read('components/Navbar.vue')

  test('every way of closing goes through closeMobileMenu, which releases the lock', () => {
    // The sweep proves each close path in a browser (Escape, close button, scrim, link tap,
    // history navigation, viewport growing past 768). This pins the structure that makes
    // that true: one closer, and the ONLY write of `isMobileMenuOpen = false` is inside it.
    const writes = navbar.match(/isMobileMenuOpen\.value\s*=\s*false/g) ?? []
    assert.equal(writes.length, 1, 'only closeMobileMenu may set isMobileMenuOpen to false')

    const closer = navbar.slice(navbar.indexOf('const closeMobileMenu'), navbar.indexOf('const toggleMobileMenu'))
    assert.match(closer, /releaseScrollLock\?\.\(\)/)
    assert.match(closer, /isMobileMenuOpen\.value\s*=\s*false/)
  })

  test('the lock is taken only in openMobileMenu', () => {
    assert.equal((navbar.match(/pageScrollLock\.acquire\(\)/g) ?? []).length, 1)
    const opener = navbar.slice(navbar.indexOf('const openMobileMenu'), navbar.indexOf('const closeMobileMenu'))
    assert.match(opener, /pageScrollLock\.acquire\(\)/)
  })

  test('route change, breakpoint change, pagehide and unmount all close the sheet', () => {
    assert.match(navbar, /watch\(\s*\(\)\s*=>\s*route\.fullPath/)
    assert.match(navbar, /handleBreakpointChange/)
    assert.match(navbar, /addEventListener\('pagehide'/)
    const unmount = navbar.slice(navbar.indexOf('onBeforeUnmount'))
    assert.match(unmount, /closeMobileMenu\(/)
  })

  test('every listener added on mount is removed on unmount (no leak)', () => {
    const adds = navbar.match(/(?:window|mobileQuery)\.addEventListener\('(\w+)'/g) ?? []
    assert.ok(adds.length >= 3)
    const unmount = navbar.slice(navbar.indexOf('onBeforeUnmount'))
    for (const added of adds) {
      const event = added.match(/'(\w+)'/)![1]
      assert.match(unmount, new RegExp(`removeEventListener\\('${event}'`), `${event} listener is never removed`)
    }
  })

  test('the toggle and sheet carry the ARIA the design asks for', () => {
    assert.match(navbar, /:aria-expanded="isMobileMenuOpen"/)
    assert.match(navbar, /aria-controls="mobile-nav-sheet"/)
    assert.match(navbar, /role="dialog" aria-modal="true"/)
    assert.match(navbar, /event\.key === 'Escape'/)
  })

  test('the sheet is teleported out of the (backdrop-filtered) header', () => {
    // A `backdrop-filter` ancestor makes `position: fixed` relative to it, which clips the
    // sheet to the 68px bar. The sweep opens the sheet after scrolling to prove it covers
    // the viewport; this is the structural reason it does.
    assert.match(navbar, /<Teleport to="body">/)
  })
})

describe('every route is covered by the responsive sweep', () => {
  test('router paths and the sweep ROUTES list agree', () => {
    const router = read('router/index.ts')
    const sweep = readFileSync(new URL('../scripts/responsive_sweep.py', import.meta.url), 'utf8')

    const routerPaths = [...router.matchAll(/\{\s*path:\s*'([^']+)'/g)].map((m) => m[1])
    assert.ok(routerPaths.length > 30, 'router parse found suspiciously few routes')

    const sweepPaths = [...sweep.matchAll(/^\s*\("([^"]+)",\s*(?:True|False)\),/gm)].map((m) => m[1].split('?')[0])

    const missing = routerPaths.filter((path) => {
      if (path === '/:pathMatch(.*)*') return !sweepPaths.some((p) => p.includes('does-not-exist'))
      if (path.includes(':id')) return !sweepPaths.some((p) => p.startsWith(path.split(':')[0]))
      return !sweepPaths.includes(path)
    })
    assert.deepEqual(missing, [], 'a route exists that the responsive sweep never renders')
  })
})
