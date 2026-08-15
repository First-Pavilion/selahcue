/**
 * The API seam: error classification, transport-vs-rejection, request shape, cancellation.
 *
 * The transport is INJECTED via `fetchImpl` rather than patched onto `globalThis`. Two
 * reasons, and both matter for the tests that come after this file: a patched global is
 * shared state that concurrently-running tests overwrite for each other, and injection
 * lets a stub honour the AbortSignal the way a real fetch does — which is the only way to
 * test cancellation honestly.
 */
import assert from 'node:assert/strict'
import test, { describe } from 'node:test'

import {
  ApiError,
  classifyErrors,
  graphqlRequest,
  isTransportFailure,
} from '../src/lib/api/graphql.ts'
import { confirmPasswordReset, verifyEmail } from '../src/lib/api/account.ts'

interface Call {
  url: string
  init: RequestInit
}

/** A fetch stub that records what it was sent and replies with a scripted response. */
function recorder(reply: () => Response | Promise<Response>): { calls: Call[]; impl: typeof fetch } {
  const calls: Call[] = []
  const impl = (async (input: unknown, init: RequestInit = {}) => {
    calls.push({ url: String(input), init })
    return reply()
  }) as unknown as typeof fetch
  return { calls, impl }
}

/** A fetch stub that throws, standing in for offline / DNS / TLS failure. */
const offline = (() => {
  throw new TypeError('Failed to fetch')
}) as unknown as typeof fetch

/** A fetch stub that never replies but DOES honour abort, like the real thing. */
const hangs = ((_input: unknown, init: RequestInit = {}) =>
  new Promise<Response>((_resolve, reject) => {
    init.signal?.addEventListener(
      'abort',
      () => reject(init.signal?.reason ?? new DOMException('Aborted', 'AbortError')),
      { once: true },
    )
  })) as unknown as typeof fetch

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

describe('classifyErrors', () => {
  test('reads the server code out of the error envelope', () => {
    const envelope = [
      { message: 'The request is invalid.', extensions: { code: 'VALIDATION_FAILED' } },
    ]
    assert.equal(classifyErrors(envelope), 'VALIDATION_FAILED')
  })

  test('every documented code from errors.py round-trips', () => {
    const codes = [
      'UNAUTHENTICATED',
      'PERMISSION_DENIED',
      'VALIDATION_FAILED',
      'NOT_FOUND',
      'CONFLICT',
      'POLICY_DENIED',
      'RATE_LIMITED',
      'NOT_IMPLEMENTED',
      'INTERNAL',
    ]
    for (const code of codes) {
      assert.equal(classifyErrors([{ extensions: { code } }]), code)
    }
  })

  test('an unrecognised code becomes UNKNOWN, not VALIDATION_FAILED', () => {
    // The server already collapses codes it does not know onto VALIDATION_FAILED. Doing
    // it a second time on the client would let a genuinely new server code masquerade as
    // a validation failure here too — and on /reset that means silently mis-blaming the
    // user's link.
    assert.equal(classifyErrors([{ extensions: { code: 'TEAPOT' } }]), 'UNKNOWN')
    assert.equal(classifyErrors([{ message: 'no extensions at all' }]), 'UNKNOWN')
    assert.equal(classifyErrors([]), 'UNKNOWN')
    assert.equal(classifyErrors(undefined), 'UNKNOWN')
  })
})

describe('errors arrive on HTTP 200', () => {
  test('a 200 carrying an errors array still rejects', async () => {
    // The API returns GraphQL errors with a 200 status (graphql/views.py). Anything that
    // only checked response.ok would read this as success.
    const { impl } = recorder(() => json({ errors: [{ extensions: { code: 'VALIDATION_FAILED' } }] }))

    await assert.rejects(
      () => verifyEmail('SC-EMAILVERIFY-whatever', { fetchImpl: impl }),
      (error: unknown) => error instanceof ApiError && error.code === 'VALIDATION_FAILED',
    )
  })

  test('a successful envelope resolves to the payload field', async () => {
    const { impl } = recorder(() => json({ data: { verifyEmail: { verified: true } } }))
    assert.equal(await verifyEmail('SC-EMAILVERIFY-good', { fetchImpl: impl }), true)
  })

  test('a 4xx that DOES carry a proper envelope keeps the server code', async () => {
    // SafeGraphQLView returns its envelope with a non-200 status for routing errors; the
    // envelope is authoritative, so this must not be flattened into NETWORK.
    const { impl } = recorder(() => json({ errors: [{ extensions: { code: 'NOT_FOUND' } }] }, 404))
    await assert.rejects(
      () => verifyEmail('SC-EMAILVERIFY-x', { fetchImpl: impl }),
      (error: unknown) => error instanceof ApiError && error.code === 'NOT_FOUND',
    )
  })
})

describe('transport failure is not a validation failure', () => {
  /**
   * This split is the whole difference between /reset showing R7 ("something went wrong
   * on our side, your link still works") and R4 ("this link is dead"). Telling someone
   * their link is dead because their wifi dropped sends them off to burn another token
   * for no reason.
   */
  test('a rejected fetch classifies as NETWORK', async () => {
    await assert.rejects(
      () => verifyEmail('SC-EMAILVERIFY-x', { fetchImpl: offline }),
      (error: unknown) => {
        assert.ok(error instanceof ApiError)
        assert.equal(error.code, 'NETWORK')
        assert.equal(isTransportFailure(error), true)
        return true
      },
    )
  })

  test('an unparseable body (an HTML error page) classifies as NETWORK', async () => {
    const { impl } = recorder(
      () =>
        new Response('<html><body>502 Bad Gateway</body></html>', {
          status: 502,
          headers: { 'Content-Type': 'text/html' },
        }),
    )

    await assert.rejects(
      () => verifyEmail('SC-EMAILVERIFY-x', { fetchImpl: impl }),
      (error: unknown) => error instanceof ApiError && error.code === 'NETWORK',
    )
  })

  test('a NETWORK failure is never reported as VALIDATION_FAILED', async () => {
    await assert.rejects(
      () => confirmPasswordReset('SC-PASSWORDRESET-x', 'a-good-passphrase', { fetchImpl: offline }),
      (error: unknown) => error instanceof ApiError && error.code !== 'VALIDATION_FAILED',
    )
  })
})

describe('request shape', () => {
  test('posts to a relative /graphql/account so the SPA is same-origin with the API', async () => {
    const { calls, impl } = recorder(() => json({ data: { verifyEmail: { verified: true } } }))
    await verifyEmail('SC-EMAILVERIFY-good', { fetchImpl: impl })

    assert.equal(calls.length, 1)
    assert.equal(calls[0].url, '/graphql/account')
    assert.equal(calls[0].init.method, 'POST')
    // SameSite=Strict session cookies are only ever sent same-origin; the sign-in and
    // account-portal tickets reuse this seam and depend on that.
    assert.equal(calls[0].init.credentials, 'same-origin')
    assert.equal(calls[0].init.referrerPolicy, 'no-referrer')
  })

  test('sends the token as a GraphQL variable, never interpolated into the query', async () => {
    const { calls, impl } = recorder(() => json({ data: { verifyEmail: { verified: true } } }))
    await verifyEmail('SC-EMAILVERIFY-secret-value', { fetchImpl: impl })

    const body = JSON.parse(String(calls[0].init.body))
    assert.equal(body.variables.token, 'SC-EMAILVERIFY-secret-value')
    assert.ok(
      !body.query.includes('SC-EMAILVERIFY-secret-value'),
      'a token spliced into the query string would land in server-side query logs',
    )
  })

  test('confirmPasswordReset nests token and newPassword under `input`', async () => {
    const { calls, impl } = recorder(() => json({ data: { confirmPasswordReset: { reset: true } } }))
    await confirmPasswordReset('SC-PASSWORDRESET-t', 'a-good-passphrase', { fetchImpl: impl })

    const body = JSON.parse(String(calls[0].init.body))
    // Matches ConfirmPasswordResetInput in account_schema.py.
    assert.deepEqual(body.variables, {
      input: { token: 'SC-PASSWORDRESET-t', newPassword: 'a-good-passphrase' },
    })
  })
})

describe('cancellation', () => {
  test('an aborted request rejects with AbortError, not an ApiError', async () => {
    // A deliberate cancellation (the user navigated away) is not a failure, and a view
    // must not render an error state for one.
    const controller = new AbortController()
    const pending = graphqlRequest('query { x }', {}, { signal: controller.signal, fetchImpl: hangs })
    controller.abort()

    await assert.rejects(pending, (error: unknown) => {
      assert.ok(!(error instanceof ApiError), 'an abort must not look like a transport failure')
      return true
    })
  })

  test('an already-aborted signal short-circuits without touching the network', async () => {
    const { calls, impl } = recorder(() => json({ data: {} }))
    const controller = new AbortController()
    controller.abort()

    await assert.rejects(() =>
      graphqlRequest('query { x }', {}, { signal: controller.signal, fetchImpl: impl }),
    )
    assert.equal(calls.length, 0)
  })

  test('a timeout is a transport failure', async () => {
    // A hung API must eventually resolve to "we could not reach it", not hang V1 forever.
    await assert.rejects(
      () => graphqlRequest('query { x }', {}, { timeoutMs: 10, fetchImpl: hangs }),
      (error: unknown) => error instanceof ApiError && error.code === 'NETWORK',
    )
  })
})
