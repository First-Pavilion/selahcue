/**
 * The Account page's "Sign out" (ClickUp 17tnw2b2cbr).
 *
 * The button was `<UiButton to="/signin">Sign Out</UiButton>`: a router link. It never called
 * the `logout` mutation, so the server session, the HttpOnly cookie and the browser's session
 * hint all survived, and a visitor who pressed it believed they were signed out when they were
 * not. On a shared church-office PC that is the worst lie this UI could tell.
 *
 * Three groups:
 *
 *   1. THE FLOW (`lib/auth/signOutFlow.ts`), with a fake server and a fake router. This is where
 *      the honesty rules live: one request however many presses, "Signing out…" held through the
 *      navigation, a failed revocation reported as a failure, and (the reverse) a failed
 *      NAVIGATION never reported as one.
 *   2. THE MARKUP the real `AccountView.vue` renders, server-rendered with a real router: a real
 *      <button> (not a link), the shared wording, disabled while pending, an announced message
 *      on failure.
 *   3. PARITY with the navbar, whose copy this page must not drift from. `Navbar.vue` is not
 *      edited by this ticket (shared chrome), so it keeps its own copy of the two strings until
 *      it adopts `useSignOut`; the third group fails if the two ever disagree.
 *
 * What none of this can see (a real click, a real request, storage, the route guard afterwards,
 * focus) is asserted in a browser by the `account-signout*` scenarios in
 * `scripts/auth_pages_headless.py`.
 *
 * EVERY PREDICATE HERE HAS ONE DEFINITION and its positive control consumes THAT definition: a
 * check that has never been seen to fail on the fault it names is decoration.
 */
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test, { after, before, describe } from 'node:test'

import type { ViteDevServer } from 'vite'

import {
  SIGN_OUT_FAILED,
  SIGN_OUT_LABEL,
  SIGN_OUT_PENDING_LABEL,
  createSignOutFlow,
  type SignOutDeps,
} from '../src/lib/auth/signOutFlow.ts'
import { renderView, startViewServer, textOf } from './fixtures/viewRender.ts'

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
  test('a successful sign-out sends one request and lands on the landing page', async () => {
    const { log, flow } = harness()
    const finished = await flow.run()
    assert.equal(finished, true)
    assert.equal(log.revoke, 1)
    assert.deepEqual(log.navigate, ['/signin'])
    assert.equal(flow.error.value, '')
    assert.deepEqual(log.hard, [], 'a navigation that worked needs no full page load')
  })

  test('while the request is in flight it is pending, and a second press sends no second request', async () => {
    const held = deferred()
    const { log, flow } = harness({
      revoke: async () => {
        log.revoke += 1
        await held.promise
      },
    })
    const first = flow.run()
    assert.equal(flow.pending.value, true, 'pending from the moment of the press')
    const second = await flow.run()
    assert.equal(second, false, 'the second press is refused')
    assert.equal(log.revoke, 1, 'and it sent nothing')
    held.resolve()
    assert.equal(await first, true)
    assert.equal(log.revoke, 1)
  })

  test('it stays pending through the navigation, so the page is not pressable in the gap', async () => {
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
    const run = flow.run()
    await settle()
    assert.deepEqual(log.navigate, ['/signin'], 'the revocation finished and navigation began')
    assert.equal(flow.pending.value, true, 'still "Signing out…" while the next page loads')
    assert.equal(await flow.run(), false)
    assert.equal(log.revoke, 1)
    navigation.resolve()
    await run
    assert.equal(flow.pending.value, false, 'settled once the navigation has')
  })

  test('a failed revocation is reported, nothing is navigated, and the button is usable again', async () => {
    let failing = true
    const held = deferred()
    const { log, flow } = harness({
      revoke: async () => {
        log.revoke += 1
        if (failing) throw new TypeError('Failed to fetch')
        await held.promise
      },
    })
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
  })

  test('a navigation that fails AFTER the session was revoked is not reported as a failed sign-out', async () => {
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

  test('the positive control: the failure message is the shared one, not an empty string', () => {
    // Every "no error" assertion above would pass if SIGN_OUT_FAILED were ''.
    assert.match(SIGN_OUT_FAILED, /couldn't sign you out/i)
    assert.ok(SIGN_OUT_FAILED.length > 20)
  })
})

// --------------------------------------------------------------------------- 2. the markup

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

/** The first button or link in the Account page's header (where "Sign out" is drawn), or null. */
function signOutControl(html: string): Control | null {
  const start = html.indexOf('class="portal-header"')
  if (start === -1) return null
  const end = html.indexOf('</header>', start)
  // Comments out first: a template comment may legitimately mention a `<button>`, and the first
  // draft of this locator found the comment's tag instead of the control's.
  const header = html.slice(start, end === -1 ? undefined : end).replace(/<!--[\s\S]*?-->/g, '')
  const found = /<(button|a)\b([^>]*)>([\s\S]*?)<\/\1>/.exec(header)
  if (!found) return null
  const attrs: Record<string, string> = {}
  for (const a of (found[2] ?? '').matchAll(/([^\s=>/]+)(?:="([^"]*)")?/g)) attrs[a[1] as string] = a[2] ?? ''
  return { tag: found[1] as string, attrs, text: textOf(found[3] ?? '') }
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

// --------------------------------------------------------------------------- 3. parity

describe('the Account page and the navbar say the same thing', () => {
  const navbar = readFileSync(new URL('../src/components/Navbar.vue', import.meta.url), 'utf8')

  test('the failure message is word for word the navbar\'s', () => {
    const declared = /const SIGN_OUT_FAILED = "([^"]*)"/.exec(navbar)?.[1]
    assert.ok(declared, 'Navbar.vue no longer declares SIGN_OUT_FAILED as a double-quoted literal: update this parity check, do not delete it')
    assert.equal(declared, SIGN_OUT_FAILED)
  })

  test('the two labels are the navbar\'s', () => {
    assert.ok(
      navbar.includes(`signOutPending ? '${SIGN_OUT_PENDING_LABEL}' : '${SIGN_OUT_LABEL}'`),
      `Navbar.vue's button label is no longer "${SIGN_OUT_PENDING_LABEL}" / "${SIGN_OUT_LABEL}"`,
    )
  })
})
