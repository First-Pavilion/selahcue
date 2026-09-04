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
import { readFileSync } from 'node:fs'

import {
  ApiError,
  classifyErrors,
  graphqlRequest,
  isTransportFailure,
} from '../src/lib/api/graphql.ts'
import {
  RESEND_VERIFICATION_FIELD,
  confirmPasswordReset,
  resendVerification,
  verifyEmail,
} from '../src/lib/api/account.ts'

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

/**
 * `ErrorCode` as the SERVER defines it, parsed out of `selahcue_api/graphql/errors.py`.
 *
 * WHY THIS READS A PYTHON FILE. `SERVER_ERROR_CODES` in `graphql.ts` is a hand-maintained
 * copy of that enum, and this test used to be a THIRD copy: nine code names typed out
 * here, vouching for nine code names typed out there. Two transcriptions of one fact agree
 * with each other for exactly as long as nobody edits the original. PR #16 added
 * `PASSWORD_INVALID` to `errors.py`; both copies stayed at nine; `classifyErrors` mapped a
 * real, permanent, actionable error to `UNKNOWN`; `/reset` rendered "something went wrong
 * on our side" for it; and this file printed `ok - every documented code from errors.py
 * round-trips` while it happened. Adding a tenth name by hand would have rebuilt the same
 * mechanism one code later.
 *
 * So the list is READ. The shipped bundle still cannot see Python — the client keeps its
 * own copy, as it must — but the copy is now checked against the original by a test that
 * fails the moment the two disagree, in either direction.
 *
 * RESIDUAL, stated because it bounds what this control proves: `npm test` runs when
 * something in `implementation/marketing` changes, and CI's `marketing` job is
 * path-filtered to that directory, so an API-ONLY commit that adds an error code will not
 * re-run this test until the next marketing change. It closes the drift, not the delay.
 * Adding `implementation/api/**` to that filter is the devops half and is tracked
 * separately (86ak5rjh7).
 */
const ERRORS_PY = new URL('../../api/selahcue_api/graphql/errors.py', import.meta.url)

function errorCodesFromTheServer(): string[] {
  const source = readFileSync(ERRORS_PY, 'utf8')
  const lines = source.split('\n')
  const start = lines.findIndex((line) => line.startsWith('class ErrorCode('))
  assert.notEqual(start, -1, `no 'class ErrorCode(' in ${ERRORS_PY.pathname} — has it moved?`)

  const codes: string[] = []
  for (const line of lines.slice(start + 1)) {
    // The enum body is indented; the first unindented non-blank line ends it, so a
    // constant defined AFTER the class (SAFE_MESSAGES, say) cannot leak in.
    if (line.trim() !== '' && !line.startsWith(' ')) break
    const member = /^ {4}([A-Z][A-Z0-9_]*) = "([A-Z][A-Z0-9_]*)"\s*$/.exec(line)
    if (!member) continue
    assert.equal(
      member[1],
      member[2],
      'errors.py stopped using the member name as its wire value; classifyErrors compares ' +
        'against the VALUE, so this parser and the client copy both need revisiting',
    )
    codes.push(member[2])
  }
  return codes
}

describe('classifyErrors', () => {
  test('reads the server code out of the error envelope', () => {
    const envelope = [
      { message: 'The request is invalid.', extensions: { code: 'VALIDATION_FAILED' } },
    ]
    assert.equal(classifyErrors(envelope), 'VALIDATION_FAILED')
  })

  test('every code errors.py defines round-trips — the list is read, not transcribed', () => {
    const codes = errorCodesFromTheServer()

    // THE PREMISE, so a parser that silently matched nothing could not turn the loop below
    // into a pass over an empty list. Pinned against the file's own contents, not against
    // a remembered count: the number is allowed to grow, and this test is how the client
    // finds out that it did.
    assert.ok(
      codes.length >= 10,
      `parsed only ${codes.length} codes out of errors.py — the parser, not the enum, is ` +
        'almost certainly what broke',
    )
    assert.ok(codes.includes('VALIDATION_FAILED'), 'the parse missed VALIDATION_FAILED')
    assert.ok(
      codes.includes('PASSWORD_INVALID'),
      'PASSWORD_INVALID is gone from errors.py — /reset has a branch that can no longer ' +
        'be reached, and ResetView needs revisiting before this assertion is relaxed',
    )

    for (const code of codes) {
      assert.equal(
        classifyErrors([{ extensions: { code } }]),
        code,
        `errors.py can send ${code} and this client collapses it to UNKNOWN — add it to ` +
          'SERVER_ERROR_CODES and to ApiErrorCode, and decide what every view does with it',
      )
    }
  })

  test('PASSWORD_INVALID reaches the caller as itself, not as UNKNOWN', () => {
    // Called out by name as well as by the sweep above. This is the code /reset uses to
    // tell "your link is dead" (R4) apart from "your link is fine, your password is not",
    // and a client that cannot see the difference tells the user the wrong one.
    assert.equal(classifyErrors([{ extensions: { code: 'PASSWORD_INVALID' } }]), 'PASSWORD_INVALID')
  })

  test('an unrecognised code becomes UNKNOWN, not VALIDATION_FAILED', () => {
    // The server already collapses codes it does not know onto VALIDATION_FAILED. Doing
    // it a second time on the client would let a genuinely new server code masquerade as
    // a validation failure here too — and on /reset that means silently mis-blaming the
    // user's link.
    // The negative control is only a control if TEAPOT really is unknown to the server.
    // Otherwise this line would pass by asserting UNKNOWN about a code that ought to
    // round-trip, and would keep passing after the sweep above stopped covering anything.
    assert.ok(
      !errorCodesFromTheServer().includes('TEAPOT'),
      'errors.py now defines TEAPOT, so it is no longer an unrecognised code — pick ' +
        'another one for this control',
    )
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

  test('a rejected password reaches the reset view as PASSWORD_INVALID, not VALIDATION_FAILED', async () => {
    // End to end through the seam the view actually calls, because that is what decides
    // which of three states /reset renders. VALIDATION_FAILED here would show R4 ("this
    // reset link didn't work") for a link the server had to find LIVE to get this far, and
    // UNKNOWN would show R7 ("something went wrong on our side") for a request the server
    // answered correctly.
    const { impl } = recorder(() =>
      json({ errors: [{ extensions: { code: 'PASSWORD_INVALID' } }] }),
    )
    await assert.rejects(
      () => confirmPasswordReset('SC-PASSWORDRESET-live', 'a-good-passphrase', { fetchImpl: impl }),
      (error: unknown) => error instanceof ApiError && error.code === 'PASSWORD_INVALID',
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

describe('resend verification (86ak120ac, shipped in 5b6c0ae)', () => {
  test('the field name matches account_schema.py exactly', () => {
    // `resend_verification_email` camel-cased. NOT `resendVerification` — it does not
    // follow requestPasswordReset's shorter shape. A wrong field name comes back as
    // VALIDATION_FAILED, the same code a dead link produces, so this would present as
    // "resend is broken for everyone" with nothing pointing at the cause.
    assert.equal(RESEND_VERIFICATION_FIELD, 'resendVerificationEmail')
  })

  test('asks for the real field and selects only { accepted }', async () => {
    const { calls, impl } = recorder(() =>
      json({ data: { resendVerificationEmail: { accepted: true } } }),
    )
    const accepted = await resendVerification('pastor@church.org', { fetchImpl: impl })

    assert.equal(accepted, true)
    const body = JSON.parse(String(calls[0].init.body))
    assert.match(body.query, /resendVerificationEmail\(email: \$email\)\s*\{\s*accepted\s*\}/)
    assert.deepEqual(body.variables, { email: 'pastor@church.org' })
  })

  test('rate limiting surfaces as RATE_LIMITED, not as a generic failure', async () => {
    // The view needs this code distinctly so it can say "wait a few minutes" instead of
    // "try again in a moment", which would invite an immediate retry that also fails.
    const { impl } = recorder(() => json({ errors: [{ extensions: { code: 'RATE_LIMITED' } }] }))

    await assert.rejects(
      () => resendVerification('pastor@church.org', { fetchImpl: impl }),
      (error: unknown) => error instanceof ApiError && error.code === 'RATE_LIMITED',
    )
  })

  test('a malformed address surfaces as VALIDATION_FAILED', async () => {
    const { impl } = recorder(() => json({ errors: [{ extensions: { code: 'VALIDATION_FAILED' } }] }))
    await assert.rejects(
      () => resendVerification('nope', { fetchImpl: impl }),
      (error: unknown) => error instanceof ApiError && error.code === 'VALIDATION_FAILED',
    )
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
