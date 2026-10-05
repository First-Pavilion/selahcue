/**
 * The Account page's "Sign out" (ClickUp 17tnw2b2cbr).
 *
 * The button was `<UiButton to="/signin">Sign Out</UiButton>`: a router link. It never called
 * the `logout` mutation, so the server session, the HttpOnly cookie and the browser's session
 * hint all survived, and a visitor who pressed it believed they were signed out when they were
 * not. On a shared church-office PC that is the worst lie this UI could tell.
 *
 * Four groups:
 *
 *   1. THE FLOW (`lib/auth/signOutFlow.ts`), with a fake server and a fake router. This is where
 *      the honesty rules live: one request however many presses, "Signing out…" held through the
 *      navigation, a failed revocation reported as a failure, (the reverse) a failed NAVIGATION
 *      never reported as one, and a visitor who leaves the page mid-request not being dragged back.
 *   2. THE WIRING (`lib/auth/useSignOut.ts`), against a real router: it lands where it was told,
 *      and it stops navigating once the page that asked has gone.
 *   3. THE MARKUP the real `AccountView.vue` renders, server-rendered with a real router: a real
 *      <button> (not a link), the shared wording, disabled while pending, a polite announcement
 *      of the pending state, an announced message on failure.
 *   4. PARITY with the navbar, whose copy this page must not drift from. `Navbar.vue` is not
 *      edited by this ticket (shared chrome), so it keeps its own copy of the strings until it
 *      adopts `useSignOut` (17tnw2b2ka8); this group fails if the two ever disagree, and it pins
 *      the one difference that is allowed to exist until then.
 *
 * What none of this can see (a real click, a real request, storage, the route guard afterwards,
 * focus) is asserted in a browser by the `account-signout*` scenarios in
 * `scripts/auth_pages_headless.py`.
 *
 * EVERY TEST THAT HOLDS A REQUEST CANNOT STALL THE RUN. Node's test runner has no default timeout,
 * and these tests wait on promises they release by hand: with the guard they protect removed, an
 * awaited second press waits on a gate nobody opens, the file never finishes, and a CI job stalls
 * with no message (Cody, round 1). So the second press is never awaited before the assertion that
 * catches it, the gate is released in a `finally`, and each test carries a timeout as the last
 * resort.
 *
 * EVERY PREDICATE HERE HAS ONE DEFINITION and its positive control consumes THAT definition: a
 * check that has never been seen to fail on the fault it names is decoration.
 */
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test, { after, before, describe } from 'node:test'

import { createApp, effectScope } from 'vue'
import { createMemoryHistory, createRouter } from 'vue-router'
import type { ViteDevServer } from 'vite'

import {
  SIGN_OUT_FAILED,
  SIGN_OUT_LABEL,
  SIGN_OUT_PENDING_LABEL,
  createSignOutFlow,
  type SignOutDeps,
} from '../src/lib/auth/signOutFlow.ts'
import { useSignOut } from '../src/lib/auth/useSignOut.ts'
import { renderView, startViewServer, textOf } from './fixtures/viewRender.ts'

/** The last resort: a hung test fails after this long instead of stalling the run. */
const BOUND = { timeout: 5_000 }

// --------------------------------------------------------------------------- 1. the flow

/** A promise the test settles by hand, so "while the request is in flight" is a state it can stand in. */
function deferred<T = void>() {
  let resolve!: (value: T) => void
  let reject!: (reason: unknown) => void
  const promise = new Promise<T>((res, rej) => {
    resolve = res
    reject = rej
  })
  return { promise, resolve, reject }
}

/** Let queued microtasks run, so a `.then` that follows an `await` has happened. */
const settle = () => new Promise<void>((resolve) => setImmediate(resolve))

function harness(overrides: Partial<SignOutDeps> = {}) {
  const log = { revoke: 0, navigate: [] as string[], hard: [] as string[] }
  const deps: SignOutDeps = {
    landing: '/signin',
    revoke: async () => {
      log.revoke += 1
    },
    navigate: async (to) => {
      log.navigate.push(to)
    },
    hardNavigate: (to) => {
      log.hard.push(to)
    },
    ...overrides,
  }
  return { log, flow: createSignOutFlow(deps), deps }
}

describe('the sign-out flow', () => {
  test('a successful sign-out sends one request and lands on the landing page', BOUND, async () => {
    const { log, flow } = harness()
    const finished = await flow.run()
    assert.equal(finished, true)
    assert.equal(log.revoke, 1)
    assert.deepEqual(log.navigate, ['/signin'])
    assert.equal(flow.error.value, '')
    assert.deepEqual(log.hard, [], 'a navigation that worked needs no full page load')
  })

  test('while the request is in flight it is pending, and a second press sends no second request', BOUND, async () => {
    const held = deferred()
    const { log, flow } = harness({
      revoke: async () => {
        log.revoke += 1
        await held.promise
      },
    })
    try {
      const first = flow.run()
      assert.equal(flow.pending.value, true, 'pending from the moment of the press')
      // NOT awaited here. With the re-entry guard gone this press would wait on `held` as well,
      // and an awaited call would stall the test instead of failing it.
      const second = flow.run()
      await settle()
      assert.equal(log.revoke, 1, 'the second press sent nothing')
      held.resolve()
      assert.equal(await first, true)
      assert.equal(await second, false, 'and the second press is refused')
      assert.equal(log.revoke, 1)
    } finally {
      held.resolve()
    }
  })

  test('it stays pending through the navigation, so the page is not pressable in the gap', BOUND, async () => {
    // `/signin` is a lazy route. On a slow connection the session is already revoked and the
    // page is still showing; a button that came back to life in that gap would let a second
    // request go out for a session that no longer exists.
    const navigation = deferred()
    const { log, flow } = harness({
      navigate: async (to) => {
        log.navigate.push(to)
        await navigation.promise
      },
    })
    try {
      const run = flow.run()
      await settle()
      assert.deepEqual(log.navigate, ['/signin'], 'the revocation finished and navigation began')
      assert.equal(flow.pending.value, true, 'still "Signing out…" while the next page loads')
      const second = flow.run() // not awaited: see the file header
      await settle()
      assert.equal(log.revoke, 1, 'a press in the gap sent nothing')
      navigation.resolve()
      await run
      assert.equal(await second, false)
      assert.equal(flow.pending.value, false, 'settled once the navigation has')
    } finally {
      navigation.resolve()
    }
  })

  test('a failed revocation is reported, nothing is navigated, and the button is usable again', BOUND, async () => {
    let failing = true
    const held = deferred()
    const { log, flow } = harness({
      revoke: async () => {
        log.revoke += 1
        if (failing) throw new TypeError('Failed to fetch')
        await held.promise
      },
    })
    try {
      const finished = await flow.run()
      assert.equal(finished, false)
      assert.equal(flow.error.value, SIGN_OUT_FAILED)
      assert.equal(flow.pending.value, false, 'back to "Sign out", not stuck on "Signing out…"')
      assert.deepEqual(log.navigate, [], 'the visitor stays where they are: they are NOT signed out')
      assert.deepEqual(log.hard, [])

      // Retry on the SAME flow: a second request goes out, and the old failure is not shown beside it.
      failing = false
      const retry = flow.run()
      assert.equal(flow.error.value, '', 'a stale failure is not shown beside a fresh attempt')
      assert.equal(flow.pending.value, true)
      held.resolve()
      assert.equal(await retry, true)
      assert.equal(log.revoke, 2)
      assert.deepEqual(log.navigate, ['/signin'])
    } finally {
      held.resolve()
    }
  })

  test('a navigation that fails AFTER the session was revoked is not reported as a failed sign-out', BOUND, async () => {
    // The defect `Navbar.vue` records (PR #17, HIGH-1): a rejected `router.push` (a chunk a
    // deploy removed) used to be reported as "We couldn't sign you out", over a revocation the
    // server had already performed. That tells someone on a shared machine their session is
    // still live when it is not.
    const { log, flow } = harness({
      navigate: async () => {
        throw new Error('Failed to fetch dynamically imported module')
      },
    })
    const finished = await flow.run()
    assert.equal(finished, true, 'they ARE signed out')
    assert.equal(flow.error.value, '', 'so no failure is shown')
    assert.deepEqual(log.hard, ['/signin'], 'a full document load gets them there instead')
  })

  test('the positive control: the failure message is the shared one, not an empty string', BOUND, () => {
    // Every "no error" assertion above would pass if SIGN_OUT_FAILED were ''.
    assert.match(SIGN_OUT_FAILED, /couldn't sign you out/i)
    assert.ok(SIGN_OUT_FAILED.length > 20)
  })
})

describe('leaving the page while the request is in flight (Shadow LOW-2, Quinn 3)', () => {
  // The visitor pressed Sign out, then clicked Pricing before the reply. The request is NOT
  // cancelled (a logout that may already have landed must not be abandoned), so the session is
  // revoked either way. What the late reply must not do is act for a page that is gone: a
  // success pulling them off the page they chose, or a failure written to a message nobody sees.

  test('a late success has revoked the session but does not navigate', BOUND, async () => {
    const held = deferred()
    const { log, flow } = harness({
      revoke: async () => {
        log.revoke += 1
        await held.promise
      },
    })
    try {
      const run = flow.run()
      flow.dispose() // the page unmounted
      held.resolve()
      assert.equal(await run, true, 'they ARE signed out')
      assert.equal(log.revoke, 1, 'the request was not cancelled or repeated')
      assert.deepEqual(log.navigate, [], 'and they stay on the page they went to')
      assert.deepEqual(log.hard, [])
    } finally {
      held.resolve()
    }
  })

  test('a late failure writes no state and navigates nowhere', BOUND, async () => {
    const held = deferred()
    const { log, flow } = harness({
      revoke: async () => {
        log.revoke += 1
        await held.promise
        throw new TypeError('Failed to fetch')
      },
    })
    try {
      const run = flow.run()
      flow.dispose()
      held.resolve()
      assert.equal(await run, false, 'they are NOT signed out')
      assert.equal(flow.error.value, '', 'no message is written to a page that is gone')
      assert.deepEqual(log.navigate, [])
    } finally {
      held.resolve()
    }
  })

  test('the control: a flow whose page is still there navigates on the same late success', BOUND, async () => {
    const held = deferred()
    const { log, flow } = harness({
      revoke: async () => {
        log.revoke += 1
        await held.promise
      },
    })
    try {
      const run = flow.run()
      held.resolve()
      assert.equal(await run, true)
      assert.deepEqual(log.navigate, ['/signin'], 'without this, the two tests above would pass for a flow that never navigates')
    } finally {
      held.resolve()
    }
  })
})

// --------------------------------------------------------------------------- 2. the wiring

/**
 * `useSignOut` the way a component calls it: inside an effect scope (a component's setup runs in
 * one, and unmounting stops it) with the app's provides reachable, against a real router on
 * memory history. Only the revocation is replaced, because that is the one thing that would reach
 * a network. Nothing in the node suite imported this module before, so a wiring fault (the wrong
 * router call, no unmount hook) was caught only by the browser scenarios.
 */
async function wired(revoke: () => Promise<void>) {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/:p(.*)*', component: { render: () => null } }],
  })
  await router.push('/account')
  await router.isReady()
  const app = createApp({ render: () => null })
  app.use(router)
  const scope = effectScope()
  const flow = app.runWithContext(() => scope.run(() => useSignOut('/signin', revoke)))
  assert.ok(flow, 'useSignOut returned nothing')
  return { router, scope, flow }
}

describe('useSignOut, wired to a real router', () => {
  test('a successful sign-out goes to the landing page through the router', BOUND, async () => {
    const { router, flow } = await wired(async () => {})
    assert.equal(await flow.run(), true)
    assert.equal(router.currentRoute.value.path, '/signin')
  })

  test('once the page that asked has unmounted, a late success leaves the visitor where they went', BOUND, async () => {
    const held = deferred()
    const { router, scope, flow } = await wired(() => held.promise)
    try {
      const run = flow.run()
      await router.push('/pricing') // the visitor clicks away
      scope.stop() // and the Account page unmounts
      held.resolve()
      assert.equal(await run, true)
      assert.equal(router.currentRoute.value.path, '/pricing', 'a reply for a page that is gone must not move them')
    } finally {
      held.resolve()
    }
  })

  test('and a late failure neither navigates nor writes a message', BOUND, async () => {
    const held = deferred()
    const { router, scope, flow } = await wired(async () => {
      await held.promise
      throw new TypeError('Failed to fetch')
    })
    try {
      const run = flow.run()
      await router.push('/pricing')
      scope.stop()
      held.resolve()
      assert.equal(await run, false)
      assert.equal(flow.error.value, '')
      assert.equal(router.currentRoute.value.path, '/pricing')
    } finally {
      held.resolve()
    }
  })
})

// --------------------------------------------------------------------------- 3. the markup

let server: ViteDevServer
before(async () => {
  server = await startViewServer()
})
after(async () => {
  await server.close()
})

interface Control {
  tag: string
  attrs: Record<string, string>
  text: string
}

/**
 * The Account page's header (where "Sign out" is drawn), with comments out. A template comment
 * may legitimately mention a `<button>`, and the first draft of the locators found the comment's
 * tag instead of the control's.
 */
function headerOf(html: string): string | null {
  const start = html.indexOf('class="portal-header"')
  if (start === -1) return null
  const end = html.indexOf('</header>', start)
  return html.slice(start, end === -1 ? undefined : end).replace(/<!--[\s\S]*?-->/g, '')
}

function attrsOf(raw: string): Record<string, string> {
  const attrs: Record<string, string> = {}
  for (const a of raw.matchAll(/([^\s=>/]+)(?:="([^"]*)")?/g)) attrs[a[1] as string] = a[2] ?? ''
  return attrs
}

/** The first button or link in the header, or null. */
function signOutControl(html: string): Control | null {
  const header = headerOf(html)
  if (header === null) return null
  const found = /<(button|a)\b([^>]*)>([\s\S]*?)<\/\1>/.exec(header)
  if (!found) return null
  return { tag: found[1] as string, attrs: attrsOf(found[2] ?? ''), text: textOf(found[3] ?? '') }
}

/** The header's `role="status"` live region, or null when there is none. */
function statusRegion(html: string): Control | null {
  const header = headerOf(html)
  if (header === null) return null
  const found = /<(\w+)\b([^>]*\brole="status"[^>]*)>([\s\S]*?)<\/\1>/.exec(header)
  if (!found) return null
  return { tag: found[1] as string, attrs: attrsOf(found[2] ?? ''), text: textOf(found[3] ?? '') }
}

/** Everything wrong with a Sign out control, as sentences. Empty when it is a real, idle button. */
function problemsWithIdleControl(control: Control | null): string[] {
  if (!control) return ['there is no Sign out control in the header']
  const out: string[] = []
  if (control.tag !== 'button') out.push(`it is a <${control.tag}>, not a <button>: a link navigates, it cannot revoke a session`)
  if ('href' in control.attrs) out.push(`it carries href="${control.attrs['href']}"`)
  if (control.tag === 'button' && control.attrs['type'] !== 'button') out.push('it has no type="button"')
  if ('disabled' in control.attrs) out.push('it is disabled while idle')
  if (control.text !== SIGN_OUT_LABEL) out.push(`it reads "${control.text}", not "${SIGN_OUT_LABEL}"`)
  return out
}

describe('the Account page markup', () => {
  test('Sign out is a real, enabled button reading "Sign out"', async () => {
    const html = await renderView(server, 'AccountView.vue', '/account')
    assert.deepEqual(problemsWithIdleControl(signOutControl(html)), [])
  })

  test('while pending the button reads "Signing out…" and is disabled', async () => {
    const html = await renderView(server, 'AccountView.vue', '/account', { set: { signOutPending: true } })
    const control = signOutControl(html)
    assert.ok(control, 'no control')
    assert.equal(control.tag, 'button')
    assert.ok('disabled' in control.attrs, 'not disabled while the request is out: a second press could send a second request')
    assert.equal(control.text, SIGN_OUT_PENDING_LABEL)
  })

  test('after a failure it is "Sign out" again and the failure is ANNOUNCED on the page', async () => {
    const html = await renderView(server, 'AccountView.vue', '/account', { set: { signOutError: SIGN_OUT_FAILED } })
    assert.deepEqual(problemsWithIdleControl(signOutControl(html)), [], 'the button must be usable for a retry')
    const alerts = [...html.matchAll(/<(\w+)\b[^>]*\brole="alert"[^>]*>([\s\S]*?)<\/\1>/g)].map((m) => textOf(m[2] ?? ''))
    assert.ok(alerts.includes(SIGN_OUT_FAILED), `no role="alert" carries the failure; alerts: ${JSON.stringify(alerts)}`)
  })

  test('with nothing wrong there is no failure message on the page', async () => {
    // The control for the test above: it must not pass because the alert is always there.
    const html = await renderView(server, 'AccountView.vue', '/account')
    assert.ok(!textOf(html).includes(SIGN_OUT_FAILED))
  })

  test('the predicate really rejects the old shape, a link to /signin (positive control)', () => {
    const oldShape = '<header class="portal-header"><div class="header-actions"><a href="/signin" class="ui-button variant-outline size-sm"><span class="content">Sign Out</span></a></div></header>'
    const problems = problemsWithIdleControl(signOutControl(oldShape))
    assert.ok(problems.some((p) => p.includes('not a <button>')), problems.join('; '))
    assert.ok(problems.some((p) => p.includes('href="/signin"')), problems.join('; '))
    assert.ok(problems.some((p) => p.includes('"Sign Out"')), problems.join('; '))
  })
})

describe('the pending state is announced politely (Quinn 4)', () => {
  // A disabled button drops focus, so a screen-reader user who pressed Sign out would hear nothing
  // until the page changed. The region is always in the markup, empty when idle: a live region
  // added at the same moment as its text is not reliably announced. It is visually hidden and
  // absolutely positioned, so it cannot move anything (the headless scenario measures that).

  test('the live region is there, polite, and EMPTY before anything is pressed', async () => {
    const html = await renderView(server, 'AccountView.vue', '/account')
    const region = statusRegion(html)
    assert.ok(region, 'no role="status" region in the header')
    assert.equal(region.attrs['aria-live'], 'polite')
    assert.equal(region.text, '', 'it must not say anything while idle')
  })

  test('while pending it says "Signing out…"', async () => {
    const html = await renderView(server, 'AccountView.vue', '/account', { set: { signOutPending: true } })
    assert.equal(statusRegion(html)?.text, SIGN_OUT_PENDING_LABEL)
  })

  test('after a failure it is empty again, and the alert carries the message instead', async () => {
    const html = await renderView(server, 'AccountView.vue', '/account', { set: { signOutError: SIGN_OUT_FAILED } })
    assert.equal(statusRegion(html)?.text, '', 'two voices for one failure')
    assert.ok(textOf(html).includes(SIGN_OUT_FAILED))
  })
})

// --------------------------------------------------------------------------- 4. parity

describe('the Account page and the navbar say the same thing', () => {
  const navbar = readFileSync(new URL('../src/components/Navbar.vue', import.meta.url), 'utf8')

  /**
   * Everything wrong with the navbar's Sign out labels. There are TWO label expressions, one on the
   * desktop bar and one in the mobile sheet, and both must be the shared words. The first draft of
   * this check used `includes`, which one correct copy satisfied: changing only the mobile label
   * stayed green (Cody, round 1).
   */
  function labelProblems(source: string): string[] {
    const labels = [...source.matchAll(/signOutPending \? '([^']*)' : '([^']*)'/g)].map((m) => [m[1], m[2]] as const)
    const out: string[] = []
    if (labels.length !== 2) {
      out.push(`expected the navbar's two label expressions (desktop bar and mobile sheet), found ${labels.length}: update this check, do not delete it`)
    }
    labels.forEach(([pendingLabel, idleLabel], index) => {
      const where = index === 0 ? 'the first (desktop)' : index === 1 ? 'the second (mobile sheet)' : `number ${index + 1}`
      if (pendingLabel !== SIGN_OUT_PENDING_LABEL) out.push(`${where} reads "${pendingLabel}" while pending, not "${SIGN_OUT_PENDING_LABEL}"`)
      if (idleLabel !== SIGN_OUT_LABEL) out.push(`${where} reads "${idleLabel}" when idle, not "${SIGN_OUT_LABEL}"`)
    })
    return out
  }

  test('the failure message is word for word the navbar\'s', () => {
    const declared = /const SIGN_OUT_FAILED = "([^"]*)"/.exec(navbar)?.[1]
    assert.ok(declared, 'Navbar.vue no longer declares SIGN_OUT_FAILED as a double-quoted literal: update this parity check, do not delete it')
    assert.equal(declared, SIGN_OUT_FAILED)
  })

  test('BOTH of the navbar\'s labels (desktop and mobile sheet) are the shared ones', () => {
    assert.deepEqual(labelProblems(navbar), [])
  })

  test('the label check really sees a drift in only one of the two (positive control)', () => {
    const both = "{{ signOutPending ? 'Signing out…' : 'Sign out' }} ... {{ signOutPending ? 'Signing out…' : 'Sign out' }}"
    assert.deepEqual(labelProblems(both), [])
    const mobileOnly = "{{ signOutPending ? 'Signing out…' : 'Sign out' }} ... {{ signOutPending ? 'Signing out…' : 'Log out' }}"
    const problems = labelProblems(mobileOnly)
    assert.equal(problems.length, 1, problems.join('; '))
    assert.match(problems[0] as string, /second \(mobile sheet\).*"Log out"/)
    const pendingOnly = "{{ signOutPending ? 'Signing out…' : 'Sign out' }} ... {{ signOutPending ? 'Working…' : 'Sign out' }}"
    assert.match(labelProblems(pendingOnly).join(';'), /"Working…" while pending/)
    assert.match(labelProblems('no labels here').join(';'), /found 0/)
  })

  test('TEMPORARY, pinned: today the Account page lands on /signin and the navbar on /', () => {
    // THE OWNER'S DECISION (2026-10-05) IS THAT BOTH BUTTONS LAND ON /signin. This ticket
    // (17tnw2b2cbr) cannot make it so: criterion 2 says /signin, criterion 5 says "identical to the
    // navbar", and the navbar lands on `/`, which is shared chrome this ticket may not edit. So
    // criterion 5 is PARTIAL until 17tnw2b2ka8 moves the navbar.
    //
    // This test says what is true TODAY, so the difference is something a person changed on
    // purpose and not something that drifted. Whoever changes the navbar under 17tnw2b2ka8 will
    // see this fail: delete it then, together with the `/` check in `session-lifecycle`
    // (`scripts/auth_pages_headless.py`), which pins the navbar's side at runtime.
    const account = readFileSync(new URL('../src/views/AccountView.vue', import.meta.url), 'utf8')
    assert.match(account, /useSignOut\('\/signin'\)/, 'the Account page no longer lands on /signin')

    const start = navbar.indexOf('const handleSignOut')
    assert.ok(start !== -1, 'Navbar.vue no longer has handleSignOut')
    const handler = navbar
      .slice(start, navbar.indexOf('/**', start))
      .replace(/\/\/[^\n]*/g, '')
    assert.ok(handler.length > 200, 'the handler slice is suspiciously short')
    assert.ok(
      handler.includes("await router.push('/')") && handler.includes("window.location.assign('/')"),
      'the navbar no longer lands on `/`. If 17tnw2b2ka8 moved it to /signin, that is the plan: delete this test ' +
        'and the `/` check in `session-lifecycle`. If not, the Account page and the navbar now differ for a new reason.',
    )
  })
})
