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

  test('a caller who already aborted gets no requests at all, bootstrap included', async () => {
    withDocument('')
    const { calls, impl } = recorder(() => ({ data: { logout: { revoked: true } } }))
    const controller = new AbortController()
    controller.abort()

    await assert.rejects(() => logout(false, { fetchImpl: impl, signal: controller.signal }))
    assert.equal(calls.length, 0, 'an aborted caller must not cause a CSRF GET either')
  })
})
