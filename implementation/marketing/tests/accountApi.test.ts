/**
 * The sign-in group added for 86ak11r67: request shapes, the CSRF bootstrap, and the one
 * property that is easiest to break by being helpful — that the browser never asks for
 * the session token.
 *
 * Same injection discipline as `apiSeam.test.ts`: the transport arrives via `fetchImpl`
 * rather than being patched onto `globalThis`, so concurrently-running tests cannot
 * overwrite each other's stub and an abort can be honoured the way a real fetch honours it.
 */
import assert from 'node:assert/strict'
import test, { afterEach, describe } from 'node:test'

import {
  ACCOUNT_GRAPHQL_PATH,
  ApiError,
  CSRF_BOOTSTRAP_PATH,
  CSRF_BOOTSTRAP_TIMEOUT_MS,
} from '../src/lib/api/graphql.ts'
import {
  accountViewer,
  login,
  logout,
  refreshSession,
  registerAccount,
} from '../src/lib/api/account.ts'

interface Call {
  url: string
  init: RequestInit
}

function recorder(reply: (op: string) => unknown): { calls: Call[]; impl: typeof fetch } {
  const calls: Call[] = []
  const impl = (async (input: unknown, init: RequestInit = {}) => {
    calls.push({ url: String(input), init })
    let body: { query?: string } = {}
    try {
      body = JSON.parse(String(init.body ?? '{}'))
    } catch {
      body = {}
    }
    const op = /(?:mutation|query)\s+(\w+)/.exec(body.query ?? '')?.[1] ?? ''
    return new Response(JSON.stringify(reply(op)), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    })
  }) as unknown as typeof fetch
  return { calls, impl }
}

/** Only the GraphQL POSTs — the CSRF bootstrap is a GET and is counted separately. */
function posts(calls: Call[]): Call[] {
  return calls.filter((call) => call.init.method === 'POST')
}

function variablesOf(call: Call): Record<string, unknown> {
  return JSON.parse(String(call.init.body)).variables
}

function queryOf(call: Call): string {
  return JSON.parse(String(call.init.body)).query
}

/**
 * Give this runtime a cookie jar.
 *
 * `graphql.ts` skips the CSRF bootstrap when `typeof document === 'undefined'`, because a
 * runtime with no cookie jar cannot store the cookie the bootstrap exists to fetch. Node
 * is exactly that runtime, which is why `apiSeam.test.ts` still counts one request per
 * call. These tests are about the browser path, so they install a stub document.
 */
function withDocument(cookie: string): void {
  ;(globalThis as { document?: unknown }).document = { cookie }
}

function withoutDocument(): void {
  delete (globalThis as { document?: unknown }).document
}

afterEach(withoutDocument)

/**
 * Let the async chain under test make progress without letting TIME pass.
 *
 * With `t.mock.timers` enabled, `setTimeout` no longer advances on its own, so the only
 * way a promise chain moves is by draining the microtask queue. Twenty turns is far more
 * than any path here needs and costs microseconds.
 */
async function flushMicrotasks(): Promise<void> {
  for (let turn = 0; turn < 20; turn += 1) await Promise.resolve()
}


describe('registerCustomerUser', () => {
  test('nests every field under `input`, camel-cased to match the schema', async () => {
    const { calls, impl } = recorder(() => ({ data: { registerCustomerUser: { accepted: true } } }))
    const accepted = await registerAccount(
      {
        idempotencyKey: 'a1b2c3d4e5f6a7b8',
        email: 'pastor@yourchurch.org',
        password: 'a-good-passphrase',
        orgName: 'Grace Community Church',
        country: 'GB',
        displayName: 'Alex Morgan',
        timezone: 'Europe/London',
      },
      { fetchImpl: impl },
    )

    assert.equal(accepted, true)
    // Pinned against `RegisterCustomerUserInput` in account_schema.py. Strawberry
    // camel-cases the Python names; a snake_case key here is rejected as an unknown
    // argument, which comes back as the same VALIDATION_FAILED as a bad password.
    assert.deepEqual(variablesOf(posts(calls)[0]), {
      input: {
        idempotencyKey: 'a1b2c3d4e5f6a7b8',
        email: 'pastor@yourchurch.org',
        password: 'a-good-passphrase',
        orgName: 'Grace Community Church',
        country: 'GB',
        displayName: 'Alex Morgan',
        timezone: 'Europe/London',
      },
    })
  })

  test('fills the two optional fields with the schema defaults rather than omitting them', async () => {
    const { calls, impl } = recorder(() => ({ data: { registerCustomerUser: { accepted: true } } }))
    await registerAccount(
      {
        idempotencyKey: 'a1b2c3d4e5f6a7b8',
        email: 'pastor@yourchurch.org',
        password: 'a-good-passphrase',
        orgName: 'Grace',
        country: 'GB',
      },
      { fetchImpl: impl },
    )

    const input = variablesOf(posts(calls)[0]).input as Record<string, unknown>
    assert.equal(input.displayName, '')
    assert.equal(input.timezone, 'UTC')
  })

  test('the password travels as a variable, never interpolated into the query', async () => {
    const { calls, impl } = recorder(() => ({ data: { registerCustomerUser: { accepted: true } } }))
    await registerAccount(
      {
        idempotencyKey: 'a1b2c3d4e5f6a7b8',
        email: 'pastor@yourchurch.org',
        password: 'correct-horse-battery',
        orgName: 'Grace',
        country: 'GB',
      },
      { fetchImpl: impl },
    )

    assert.ok(
      !queryOf(posts(calls)[0]).includes('correct-horse-battery'),
      'a password spliced into the query document would land in server-side query logs',
    )
  })

  test('an already-registered address is indistinguishable from a new one', async () => {
    // Not a client behaviour so much as a statement of what the client is given: the
    // service returns the identical envelope for both, so there is nothing here to branch
    // on even if someone tried. If this ever stops being true, the views that render one
    // unbranched success state need revisiting.
    const envelope = { data: { registerCustomerUser: { accepted: true } } }
    const newAddress = recorder(() => envelope)
    const takenAddress = recorder(() => envelope)

    const input = {
      idempotencyKey: 'a1b2c3d4e5f6a7b8',
      password: 'a-good-passphrase',
      orgName: 'Grace',
      country: 'GB',
    }
    const first = await registerAccount(
      { ...input, email: 'brand-new@yourchurch.org' },
      { fetchImpl: newAddress.impl },
    )
    const second = await registerAccount(
      { ...input, email: 'already-there@yourchurch.org' },
      { fetchImpl: takenAddress.impl },
    )

    assert.equal(first, second)
    assert.equal(first, true)
  })
})

describe('login', () => {
  test('NEVER selects sessionToken', async () => {
    // THE control in this file. `_set_session_cookie` runs in the resolver body, so the
    // HttpOnly cookie is set whether or not the field is selected — asking for it would
    // copy a credential the server deliberately put out of JavaScript's reach back into
    // the JS heap, the response body, devtools and every HAR capture, for no gain.
    const { calls, impl } = recorder(() => ({
      data: { login: { expiresAt: '2026-09-24T10:00:00+00:00', role: 'ADMIN', orgId: 'org-1' } },
    }))
    await login('pastor@yourchurch.org', 'a-good-passphrase', { fetchImpl: impl })

    const query = queryOf(posts(calls)[0])
    assert.ok(
      !query.includes('sessionToken'),
      `the login document must not request the raw session token; got: ${query}`,
    )
    // Positive control: the fields it DOES select are present, so "no sessionToken" is
    // not passing because the selection set is empty or the call never happened.
    assert.match(query, /expiresAt/)
    assert.match(query, /role/)
    assert.match(query, /orgId/)
  })

  test('returns the non-secret metadata and nests credentials under `input`', async () => {
    const { calls, impl } = recorder(() => ({
      data: { login: { expiresAt: '2026-09-24T10:00:00+00:00', role: 'ADMIN', orgId: 'org-1' } },
    }))
    const metadata = await login('pastor@yourchurch.org', 'a-good-passphrase', { fetchImpl: impl })

    assert.deepEqual(metadata, {
      expiresAt: '2026-09-24T10:00:00+00:00',
      role: 'ADMIN',
      orgId: 'org-1',
    })
    assert.deepEqual(variablesOf(posts(calls)[0]), {
      input: { email: 'pastor@yourchurch.org', password: 'a-good-passphrase' },
    })
  })

  test('unknown email and wrong password reach the caller as the same code', async () => {
    // The service equalises these deliberately (a dummy PBKDF2 on the unknown-email
    // branch). This asserts the seam does not re-introduce a difference on the way back —
    // if a future change mapped one of them somewhere else, the single rejection state in
    // SignInView would silently become two.
    const unauthenticated = () => ({ errors: [{ extensions: { code: 'UNAUTHENTICATED' } }] })

    const codes: string[] = []
    for (const email of ['nobody@nowhere.test', 'pastor@yourchurch.org']) {
      const { impl } = recorder(unauthenticated)
      await login(email, 'whatever', { fetchImpl: impl }).catch((error: unknown) => {
        codes.push(error instanceof ApiError ? error.code : 'NOT-AN-API-ERROR')
      })
    }
    assert.deepEqual(codes, ['UNAUTHENTICATED', 'UNAUTHENTICATED'])
  })

  test('an unverified account is POLICY_DENIED, distinct from a rejected credential', async () => {
    // The one sanctioned difference — reachable only after a correct password — so the
    // view can offer a fresh verification link instead of "check your password".
    const { impl } = recorder(() => ({ errors: [{ extensions: { code: 'POLICY_DENIED' } }] }))
    await assert.rejects(
      () => login('pastor@yourchurch.org', 'a-good-passphrase', { fetchImpl: impl }),
      (error: unknown) => error instanceof ApiError && error.code === 'POLICY_DENIED',
    )
  })
})

describe('logout / refreshSession / accountViewer', () => {
  test('logout sends allSessions explicitly', async () => {
    const { calls, impl } = recorder(() => ({ data: { logout: { revoked: true } } }))
    assert.equal(await logout(false, { fetchImpl: impl }), true)
    assert.deepEqual(variablesOf(posts(calls)[0]), { allSessions: false })
  })

  test('refreshSession selects only expiresAt — never the rotated token', async () => {
    const { calls, impl } = recorder(() => ({
      data: { refreshSession: { expiresAt: '2026-10-24T10:00:00+00:00' } },
    }))
    assert.equal(
      await refreshSession({ fetchImpl: impl }),
      '2026-10-24T10:00:00+00:00',
    )
    const query = queryOf(posts(calls)[0])
    assert.ok(
      !query.includes('sessionToken'),
      'refresh rotates the credential; the browser must not receive the new one either',
    )
    assert.match(query, /expiresAt/)
  })

  test('accountViewer is the session probe and reports UNAUTHENTICATED when there is none', async () => {
    const live = recorder(() => ({
      data: { accountViewer: { surface: 'account', actorId: 'user-1', orgId: 'org-1' } },
    }))
    assert.deepEqual(await accountViewer({ fetchImpl: live.impl }), {
      surface: 'account',
      actorId: 'user-1',
      orgId: 'org-1',
    })

    const dead = recorder(() => ({ errors: [{ extensions: { code: 'UNAUTHENTICATED' } }] }))
    await assert.rejects(
      () => accountViewer({ fetchImpl: dead.impl }),
      (error: unknown) => error instanceof ApiError && error.code === 'UNAUTHENTICATED',
    )
  })
})

describe('CSRF bootstrap', () => {
  /**
   * Why this matters more than it looks: `CsrfViewMiddleware` is active and both GraphQL
   * surfaces declare `*_session_with_csrf`, but the SPA is served as static files, so
   * Django never rendered a page and nothing ever called `get_token()`. Without a
   * bootstrap the `csrftoken` cookie cannot come into existence and EVERY account
   * mutation is a permanent 403 in a real browser — including the two views that shipped
   * before this ticket. It passes in tests because the Django test client bypasses CSRF.
   */

  test('fetches /graphql/csrf before the mutation when the cookie is absent', async () => {
    withDocument('')
    const { calls, impl } = recorder(() => ({ data: { logout: { revoked: true } } }))
    await logout(false, { fetchImpl: impl })

    assert.equal(calls.length, 2, `expected a bootstrap GET then the POST; got ${calls.length}`)
    assert.equal(calls[0].url, CSRF_BOOTSTRAP_PATH)
    assert.equal(calls[0].init.method, 'GET')
    // The whole point of the GET is the Set-Cookie it carries back.
    assert.equal(calls[0].init.credentials, 'same-origin')
    // Order is the assertion: a bootstrap after the mutation would seed a cookie for next
    // time and leave this request to 403.
    assert.equal(calls[1].url, ACCOUNT_GRAPHQL_PATH)
    assert.equal(calls[1].init.method, 'POST')
  })

  test('skips the bootstrap and sends the header when the cookie is already there', async () => {
    // The positive control. Without it, "the bootstrap fired" above is indistinguishable
    // from "this code always fires a GET", and the header path could be dead.
    withDocument('csrftoken=a-real-csrf-token; other=x')
    const { calls, impl } = recorder(() => ({ data: { logout: { revoked: true } } }))
    await logout(false, { fetchImpl: impl })

    assert.equal(calls.length, 1, 'a readable cookie means there is nothing to bootstrap')
    const headers = calls[0].init.headers as Record<string, string>
    assert.equal(headers['X-CSRFToken'], 'a-real-csrf-token')
  })

  test('a failed bootstrap does not abort the mutation', async () => {
    // Best effort on purpose. The cookie may already exist under a name we cannot read,
    // or a deployment may not enforce CSRF; turning one transient GET failure into a
    // total authentication outage would be far worse than letting the mutation try.
    withDocument('')
    const calls: string[] = []
    const impl = (async (input: unknown, init: RequestInit = {}) => {
      calls.push(String(init.method))
      if (init.method === 'GET') throw new TypeError('Failed to fetch')
      return new Response(JSON.stringify({ data: { logout: { revoked: true } } }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      })
    }) as unknown as typeof fetch

    assert.equal(await logout(false, { fetchImpl: impl }), true)
    assert.deepEqual(calls, ['GET', 'POST'])
  })

  test('a hung bootstrap is bounded and the mutation still gets its answer', async (t) => {
    // LOW-1 (Sana). The bootstrap is awaited BEFORE the mutation's timer starts, so
    // nothing else bounds it — a proxy that accepts the connection and never answers
    // would leave "Signing in…" on screen forever. Not an error, not a retry, just a
    // spinner: the FR-552 dead end reached from an unusual direction.
    //
    // LOW-3 (Vera): this test used to WAIT OUT the real five seconds, and was ~93% of the
    // unit suite's wall time on its own (0.4s at baseline, 5.4s with it). The test is
    // valuable; the cost model was not — every future deadline test written this way adds
    // its whole deadline to every `npm test` run. Node 22's mock timers keep both bounds
    // assertable and make the assertions STRONGER than the wall clock ever did: instead of
    // "somewhere between 4.5 and 9 seconds", it now pins that the mutation has NOT been
    // issued one millisecond before the deadline and HAS been just after it.
    t.mock.timers.enable({ apis: ['setTimeout'] })
    withDocument('')

    const seen: string[] = []
    const impl = (async (input: unknown, init: RequestInit = {}) => {
      seen.push(String(init.method))
      if (init.method === 'GET') {
        // Never resolves on its own. It must be the bootstrap's OWN deadline that ends
        // this, which is exactly what the assertions below are checking.
        return new Promise<Response>((_resolve, reject) => {
          init.signal?.addEventListener(
            'abort',
            () => reject(init.signal?.reason ?? new DOMException('Aborted', 'AbortError')),
            { once: true },
          )
        })
      }
      return new Response(JSON.stringify({ data: { logout: { revoked: true } } }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      })
    }) as unknown as typeof fetch

    const pending = logout(false, { fetchImpl: impl })
    // Let the GET be dispatched before any time passes.
    await flushMicrotasks()
    assert.deepEqual(seen, ['GET'], 'the bootstrap must be issued before the mutation')

    // THE LOWER BOUND, and it is the one that matters: without it this test passes just as
    // well for a bootstrap that was skipped entirely. One millisecond short of the
    // deadline, the mutation must still be waiting.
    t.mock.timers.tick(CSRF_BOOTSTRAP_TIMEOUT_MS - 1)
    await flushMicrotasks()
    assert.deepEqual(seen, ['GET'], 'the mutation ran before the bootstrap deadline expired')

    // THE UPPER BOUND: at the deadline the seed is abandoned and the mutation proceeds. A
    // timed-out seed degrades via the best-effort path rather than taking the request down.
    t.mock.timers.tick(1)
    assert.equal(await pending, true)
    assert.deepEqual(seen, ['GET', 'POST'])
  })

  test('a caller who abandons the request does not sit out the seed deadline', async (t) => {
    // Vera's LOW on `graphql.ts`. The seed keeps its own 5s deadline and its own
    // controller — correctly, because the promise is shared and one caller's cancellation
    // must not abort a seed the others are waiting on. What was wrong was that the caller
    // was held to that deadline anyway: an abort fired at 500ms surfaced its rejection at
    // 5,001ms. Nothing user-visible depends on it today, because the views abort only on
    // unmount; any future cancel or retry affordance would inherit the wait.
    t.mock.timers.enable({ apis: ['setTimeout'] })
    withDocument('')

    const seen: string[] = []
    const impl = (async (input: unknown, init: RequestInit = {}) => {
      seen.push(String(init.method))
      if (init.method === 'GET') {
        return new Promise<Response>((_resolve, reject) => {
          init.signal?.addEventListener(
            'abort',
            () => reject(init.signal?.reason ?? new DOMException('Aborted', 'AbortError')),
            { once: true },
          )
        })
      }
      return new Response(JSON.stringify({ data: { logout: { revoked: true } } }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      })
    }) as unknown as typeof fetch

    const controller = new AbortController()
    const pending = logout(false, { fetchImpl: impl, signal: controller.signal })
    await flushMicrotasks()
    assert.deepEqual(seen, ['GET'])

    // Abandoned well inside the seed's deadline, and NO time is allowed to pass after it.
    // If the caller were still held to the seed, this would hang rather than reject —
    // which is exactly the shape of the defect.
    controller.abort()
    await assert.rejects(() => pending, { name: 'AbortError' })

    // And the mutation was never issued, which is the part that must not regress.
    assert.deepEqual(seen, ['GET'], 'an abandoned caller must issue no mutation')
  })

  test('a caller who already aborted gets no requests at all, bootstrap included', async () => {
    withDocument('')
    const { calls, impl } = recorder(() => ({ data: { logout: { revoked: true } } }))
    const controller = new AbortController()
    controller.abort()

    await assert.rejects(() => logout(false, { fetchImpl: impl, signal: controller.signal }))
    assert.equal(calls.length, 0, 'an aborted caller must not cause a CSRF GET either')
  })
})

/**
 * The request deadline has to cover the BODY, not just the headers.
 *
 * Cody measured the defect against the real module (PR #17, round 3): a transport whose
 * headers arrive at once and whose body never does left `graphqlRequest` unsettled after
 * 3,000ms with a 200ms deadline and a caller abort at 100ms. `clearTimeout` and the
 * caller's abort listener were torn down in the `finally` of the fetch `try`, which fires
 * the moment headers land — so by the time `await response.json()` ran there was no
 * deadline and no cancellation left. `SignInView.submit` awaits that promise, so the page
 * sits at `aria-busy`, button disabled, no banner and no way forward: the FR-552 dead end
 * arrived at from the one direction nothing in this suite could see, because every faked
 * reply in `tests/` is a fully-buffered `new Response(...)` whose `json()` always resolves.
 *
 * These four run on mock timers for the reason the bootstrap tests do: a wall-clock
 * version of the first test costs its whole deadline on every `npm test`, and pinning the
 * millisecond BEFORE the deadline as well as the one after is a stronger assertion than
 * "it eventually rejected" ever was.
 */
describe('the response body is read under the request deadline', () => {
  /** Short, and short on purpose: with mock timers nothing here waits for it. */
  const BODY_DEADLINE_MS = 200

  const LOGIN_REPLY = {
    data: { login: { expiresAt: '2026-09-24T10:00:00+00:00', role: 'ADMIN', orgId: 'org-1' } },
  }

  /**
   * A transport that answers with HEADERS AT ONCE and a body that does whatever `body`
   * says — the one shape `recorder` cannot express, because `new Response(...)` is always
   * fully buffered and its `json()` therefore always resolves.
   *
   * `jsonCalls` is the premise accessor. Every test below asserts it BEFORE its contract,
   * so a request refused before it ever reached the body cannot pass as a bounded one.
   */
  function headersThenBody(body: () => Promise<unknown>): {
    jsonCalls: () => number
    impl: typeof fetch
  } {
    let calls = 0
    const impl = (async () =>
      ({
        ok: true,
        status: 200,
        json: () => {
          calls += 1
          return body()
        },
      }) as unknown as Response) as unknown as typeof fetch
    return { jsonCalls: () => calls, impl }
  }

  /** Names how a rejection arrived, so an assertion failure says which mechanism fired. */
  function outcomeOf(error: unknown): string {
    return error instanceof ApiError ? `ApiError ${error.code}` : `${(error as Error).name}`
  }

  /** Never settles by itself. Only the deadline or the caller can end a wait on this. */
  function neverSettles(): Promise<never> {
    return new Promise<never>(() => {})
  }

  test('a server that sends headers and then stalls the body is refused at the deadline', async (t) => {
    t.mock.timers.enable({ apis: ['setTimeout'] })
    const { jsonCalls, impl } = headersThenBody(neverSettles)

    const settledAs: string[] = []
    const settled = login('pastor@yourchurch.org', 'a-good-passphrase', {
      fetchImpl: impl,
      timeoutMs: BODY_DEADLINE_MS,
    }).then(
      () => settledAs.push('resolved'),
      (error: unknown) => settledAs.push(outcomeOf(error)),
    )

    await flushMicrotasks()
    // PREMISE FIRST. Without this the test passes just as well for a request refused
    // before `json()` was ever called — and the body read, which is the whole subject,
    // would go unexercised while the assertions below still went green.
    assert.equal(
      jsonCalls(),
      1,
      'the body was never read — the deadline-covers-the-body contract was not exercised',
    )

    // LOWER BOUND, and it is the one that stops this being a test of "rejects eventually".
    // One millisecond short of the deadline the wait must still be open.
    t.mock.timers.tick(BODY_DEADLINE_MS - 1)
    await flushMicrotasks()
    assert.deepEqual(settledAs, [], 'the request settled before its own deadline')

    // UPPER BOUND: at the deadline the stalled body is abandoned and the caller is told
    // the truth — NETWORK, "we could not get an answer", which is what SignInView needs
    // to leave `submitting` and show a banner instead of spinning forever.
    t.mock.timers.tick(1)
    // Drained, not awaited: under the defect this promise NEVER settles, and `await`ing
    // it would hang the runner instead of failing it. The assertion below is what reports.
    await flushMicrotasks()
    assert.deepEqual(settledAs, ['ApiError NETWORK'])
    await settled
  })

  test("a caller's abort still reaches a body that has already started arriving", async (t) => {
    // The other half of the same teardown. The listener that forwards the caller's
    // cancellation was removed at the same moment the timer was cleared, so a view that
    // unmounted while the body was streaming could not cancel anything — and, worse, the
    // promise it abandoned never settled at all.
    //
    // NO TIME PASSES in this test. If the abort did not reach the body read, only the
    // deadline could end this wait, and the deadline is never ticked.
    t.mock.timers.enable({ apis: ['setTimeout'] })
    const { jsonCalls, impl } = headersThenBody(neverSettles)

    const controller = new AbortController()
    const settledAs: string[] = []
    const settled = login('pastor@yourchurch.org', 'a-good-passphrase', {
      fetchImpl: impl,
      timeoutMs: BODY_DEADLINE_MS,
      signal: controller.signal,
    }).then(
      () => settledAs.push('resolved'),
      (error: unknown) => settledAs.push(outcomeOf(error)),
    )

    await flushMicrotasks()
    assert.equal(jsonCalls(), 1, 'the body was never read — this asserts nothing about it')

    controller.abort()
    await flushMicrotasks()
    // AbortError, not `ApiError NETWORK`: a deliberate cancellation is not a failure and
    // views must not render an error state for one. That contract is stated at the top of
    // `graphqlRequest`, and it has to hold on the body path too, not only on the headers.
    assert.deepEqual(settledAs, ['AbortError'])
    await settled
  })

  test('positive control: headers that never arrive are refused at the same deadline', async (t) => {
    // Proves the deadline mechanism is LIVE rather than merely present. Without it,
    // "refused at 200ms" above would be indistinguishable from a transport that happens
    // to reject for some unrelated reason of its own.
    t.mock.timers.enable({ apis: ['setTimeout'] })
    const impl = (async (_input: unknown, init: RequestInit = {}) =>
      new Promise<Response>((_resolve, reject) => {
        init.signal?.addEventListener(
          'abort',
          () => reject(init.signal?.reason ?? new DOMException('Aborted', 'AbortError')),
          { once: true },
        )
      })) as unknown as typeof fetch

    const settledAs: string[] = []
    const settled = login('pastor@yourchurch.org', 'a-good-passphrase', {
      fetchImpl: impl,
      timeoutMs: BODY_DEADLINE_MS,
    }).then(
      () => settledAs.push('resolved'),
      (error: unknown) => settledAs.push(outcomeOf(error)),
    )

    await flushMicrotasks()
    t.mock.timers.tick(BODY_DEADLINE_MS - 1)
    await flushMicrotasks()
    assert.deepEqual(settledAs, [], 'the headers deadline fired early')

    t.mock.timers.tick(1)
    await flushMicrotasks()
    assert.deepEqual(settledAs, ['ApiError NETWORK'])
    await settled
  })

  test('positive control: an ordinary buffered body resolves with no time passing at all', async (t) => {
    // The other direction, and the one that would catch a "fix" that simply made every
    // request fail. Mock timers are enabled and never ticked, so this resolves on the
    // microtask queue alone: the deadline machinery costs a healthy request nothing.
    t.mock.timers.enable({ apis: ['setTimeout'] })
    const { calls, impl } = recorder(() => LOGIN_REPLY)

    const metadata = await login('pastor@yourchurch.org', 'a-good-passphrase', {
      fetchImpl: impl,
      timeoutMs: BODY_DEADLINE_MS,
    })

    assert.deepEqual(metadata, {
      expiresAt: '2026-09-24T10:00:00+00:00',
      role: 'ADMIN',
      orgId: 'org-1',
    })
    assert.equal(posts(calls).length, 1)
  })
})
