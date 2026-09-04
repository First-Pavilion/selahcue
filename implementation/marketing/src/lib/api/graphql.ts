/**
 * The marketing SPA's single HTTP seam.
 *
 * This is the ONLY networking code in `implementation/marketing/src`, and deliberately
 * the one place that knows about transport, CSRF, cancellation and the API's error
 * envelope. The sign-in group (86ak11r67) followed the rule this comment used to state
 * as a request: typed wrappers next to `account.ts`, reusing `graphqlRequest`. The
 * account portal (86ak11rjz) should do the same — do not re-open `fetch`.
 *
 * Three decisions worth knowing before you change anything here.
 *
 * 1. SAME-ORIGIN BY DEFAULT. The base URL is empty, so requests go to a RELATIVE
 *    `/graphql/account`, proxied to the API by the Vite dev server and by nginx in
 *    production (see `vite.config.ts` and `nginx.conf`). That removes CORS from the
 *    problem entirely, and — more importantly for the tickets after this one — it is
 *    the only arrangement in which the API's `SameSite=Strict` session cookie is ever
 *    sent, because a cross-site request never carries one. `VITE_API_BASE_URL`
 *    overrides it if a deployment really must go cross-origin, but then the API needs
 *    CORS middleware installed (it is currently absent) and the cookie needs
 *    `SameSite=None`.
 *
 * 2. ERRORS ARE HTTP 200. The API returns `{"errors":[{message, extensions:{code}}]}`
 *    with a 200 status (`selahcue_api/graphql/views.py`). A caller that only checks
 *    `response.ok` sees success. `graphqlRequest` therefore inspects the body, and
 *    raises `ApiError` carrying the server's `code`.
 *
 * 3. THE CSRF COOKIE IS SEEDED HERE, NOT BY A CALLER. `CsrfViewMiddleware` is active and
 *    both GraphQL surfaces declare `*_session_with_csrf`, but the SPA is served as static
 *    files, so Django never rendered a page and nothing ever called `get_token()` — the
 *    `csrftoken` cookie could not come into existence and every account mutation was a
 *    permanent 403 for every real browser. `GET /graphql/csrf` exists to seed it
 *    (`graphql/views.py:csrf_bootstrap`). It is fetched from INSIDE `graphqlRequest`
 *    rather than exposed as a helper views must remember to call, because a seam that can
 *    be forgotten will be: the failure it produces is a 403 on a route that worked in
 *    every test, which is the most expensive kind of bug to find. There is still exactly
 *    one transport path — callers only ever reach the network through this function.
 *    It carries its own 5s deadline, because it is awaited before the mutation's timer
 *    starts and would otherwise be the one unbounded wait in this module.
 *
 * 4. TRANSPORT FAILURE IS NOT A VALIDATION FAILURE. `ApiErrorCode.NETWORK` exists
 *    specifically so a caller can tell "we could not reach the server" from "the
 *    server rejected this". On /reset that distinction is the whole difference
 *    between showing R7 ("something went wrong on our side, your link still works")
 *    and R4 ("this link is dead") — telling a user their link is dead because their
 *    wifi dropped would send them off to request a new one for no reason.
 *
 * SECURITY: this module never logs. Request variables on these routes carry
 * single-use credential tokens and plaintext passwords, so there is no console
 * output, no error-reporting hook and no inclusion of variables in thrown messages.
 * Keep it that way.
 */

/** Error codes from `selahcue_api/graphql/errors.py`, plus two client-only codes. */
export type ApiErrorCode =
  | 'UNAUTHENTICATED'
  | 'PERMISSION_DENIED'
  | 'VALIDATION_FAILED'
  | 'NOT_FOUND'
  | 'CONFLICT'
  | 'POLICY_DENIED'
  | 'RATE_LIMITED'
  | 'NOT_IMPLEMENTED'
  /**
   * The new password failed the server's password policy, and NOTHING ELSE about the
   * request was wrong. Added by FR-551 / DEC-017 (`errors.py:30`), raised from exactly one
   * place — `confirm_password_reset`, `services.py:1245` — and only AFTER the reset token
   * has been looked up and found live. It is therefore not an enumeration oracle, and on
   * the client it is the one error code that means "your link is fine, your password is
   * not". Collapsing it to `UNKNOWN` sent /reset to R7, which tells the user something
   * went wrong on OUR side about a failure that is permanent until they change what they
   * typed.
   *
   * It deliberately carries no policy detail (`errors.py:28`): a view rendering this code
   * may say the password was refused, and must not say which rule refused it.
   */
  | 'PASSWORD_INVALID'
  | 'INTERNAL'
  /** Client-only: the request never got a usable answer (offline, DNS, TLS, timeout, proxy, non-JSON body). */
  | 'NETWORK'
  /** Client-only: a well-formed error envelope carrying a code this client does not know. */
  | 'UNKNOWN'

/**
 * The codes the server can actually send. This list is a COPY of `ErrorCode` in
 * `selahcue_api/graphql/errors.py`, and a copy is a thing that drifts: `PASSWORD_INVALID`
 * was added there by PR #16 and was missing here for the whole of round 3, so a real,
 * permanent, actionable error classified as `UNKNOWN` and /reset rendered R7 for it with
 * every gate green.
 *
 * It is a copy on purpose — the shipped bundle must not read a Python file — but it is no
 * longer an UNCHECKED copy. `tests/apiSeam.test.ts` parses `errors.py` and asserts every
 * member of that enum round-trips through `classifyErrors`, so the next code added on the
 * server fails this project's own test suite instead of degrading silently here.
 */
const SERVER_ERROR_CODES: ReadonlySet<string> = new Set([
  'UNAUTHENTICATED',
  'PERMISSION_DENIED',
  'VALIDATION_FAILED',
  'NOT_FOUND',
  'CONFLICT',
  'POLICY_DENIED',
  'RATE_LIMITED',
  'NOT_IMPLEMENTED',
  'PASSWORD_INVALID',
  'INTERNAL',
])

export class ApiError extends Error {
  readonly code: ApiErrorCode

  constructor(code: ApiErrorCode, message?: string) {
    // The message is for developers only and is never rendered. Views map `code` to
    // designed copy; the API's own messages are deliberately generic ("The request is
    // invalid.") and would read as a bug if shown to a customer.
    super(message ?? code)
    this.name = 'ApiError'
    this.code = code
  }
}

/** True when the request failed in transport rather than being rejected by the API. */
export function isTransportFailure(error: unknown): boolean {
  return error instanceof ApiError && error.code === 'NETWORK'
}

/** The account surface's endpoint (`selahcue_api/urls.py`). */
export const ACCOUNT_GRAPHQL_PATH = '/graphql/account'

const DEFAULT_TIMEOUT_MS = 15000

/** Django's default CSRF cookie/header pair. */
const CSRF_COOKIE_NAME = 'csrftoken'
const CSRF_HEADER_NAME = 'X-CSRFToken'

/** Seeds `csrftoken` for the browser surfaces (`selahcue_api/urls.py`, `csrf_bootstrap`). */
export const CSRF_BOOTSTRAP_PATH = '/graphql/csrf'

/**
 * The in-flight bootstrap, so a page that fires several mutations at once issues ONE GET
 * rather than a stampede. Cleared when it settles: a bootstrap that failed must be
 * retryable, and once the cookie exists `needsCsrfBootstrap` stops asking anyway.
 */
let csrfBootstrap: Promise<void> | null = null

/**
 * The bootstrap's own deadline, separate from and shorter than the mutation's.
 *
 * It needs one BECAUSE it is awaited before the mutation's timer starts — which is
 * deliberate, so a slow seed does not eat the mutation's budget, but it means nothing
 * else bounds it. Without this a proxy that accepts the connection and never answers
 * leaves "Signing in…" on screen forever: not an error state, not a retry, just a
 * spinner. That is the dead end FR-552 exists to prevent, arrived at from an unusual
 * direction.
 *
 * Five seconds because a timed-out bootstrap is not a failure — the request proceeds
 * regardless on the best-effort path below — so the only thing this trades away is a few
 * seconds before an honest error appears.
 */
export const CSRF_BOOTSTRAP_TIMEOUT_MS = 5000

function apiBaseUrl(): string {
  // `import.meta.env` is a Vite BUILD-TIME construct. It does not exist under plain Node,
  // which is where these modules are unit tested — and reading `.VITE_API_BASE_URL` off
  // `undefined` throws a TypeError from INSIDE the request's try block, where it would be
  // swallowed and misreported to the user as "we couldn't reach the API". Read it
  // defensively so the failure mode is an empty base URL, not a phantom outage.
  const env = import.meta.env as Record<string, unknown> | undefined
  const configured = env?.VITE_API_BASE_URL
  if (typeof configured !== 'string') return ''
  return configured.replace(/\/+$/, '')
}

function readCookie(name: string): string {
  if (typeof document === 'undefined') return ''
  for (const part of document.cookie.split(';')) {
    const separator = part.indexOf('=')
    if (separator < 0) continue
    if (part.slice(0, separator).trim() !== name) continue
    return decodeURIComponent(part.slice(separator + 1).trim())
  }
  return ''
}

/**
 * True when this runtime has a cookie jar and does not yet hold a CSRF token.
 *
 * The `document` guard is not defensive noise. These modules are unit tested under plain
 * Node, where there is no cookie jar at all — a bootstrap there would issue a request
 * that cannot store its own result, and would silently change the call count every
 * request-shape test in `apiSeam.test.ts` measures. No document, no bootstrap.
 */
function needsCsrfBootstrap(): boolean {
  if (typeof document === 'undefined') return false
  return readCookie(CSRF_COOKIE_NAME) === ''
}

/**
 * Fetch `/graphql/csrf` so Django sets the `csrftoken` cookie this request will carry.
 *
 * BEST EFFORT, DELIBERATELY. A failure here does not abort the mutation that triggered
 * it: the cookie may already exist under a name we cannot read, a deployment may not
 * enforce CSRF, and turning one transient GET failure into a total authentication outage
 * would be a far worse outcome than letting the mutation try and report its own result.
 *
 * Never throws, and — like the rest of this module — never logs.
 */
function ensureCsrfCookie(send: typeof fetch): Promise<void> {
  if (csrfBootstrap) return csrfBootstrap

  const attempt = (async () => {
    // Its OWN controller, and deliberately NOT the caller's signal. This promise is
    // shared by every request that arrives while it is in flight, so honouring one
    // caller's cancellation would abort a seed the others are still waiting on. The
    // caller's cancellation is respected the correct way — `graphqlRequest` re-checks
    // `signal.aborted` the moment this resolves, and issues no mutation if it was.
    const controller = new AbortController()
    const timeout = setTimeout(() => controller.abort(), CSRF_BOOTSTRAP_TIMEOUT_MS)
    try {
      await send(`${apiBaseUrl()}${CSRF_BOOTSTRAP_PATH}`, {
        method: 'GET',
        // The whole point: accept the Set-Cookie this response carries.
        credentials: 'same-origin',
        referrerPolicy: 'no-referrer',
        headers: { Accept: 'application/json' },
        signal: controller.signal,
      })
    } catch {
      // Swallowed on purpose — a timeout included. See above.
    } finally {
      clearTimeout(timeout)
    }
  })().then(() => {
    csrfBootstrap = null
  })

  csrfBootstrap = attempt
  return attempt
}

/**
 * Wait for `work`, or for `signal` to abort — whichever happens first.
 *
 * RESOLVES on abort rather than rejecting: the caller's abort is turned into the caller's
 * own `AbortError` by the check that follows this call, and having two places raise it
 * would mean two different errors for one cancellation. `work` is left running, which is
 * the point — it is shared.
 *
 * The listener is removed either way, so a long-lived signal does not accumulate one per
 * request.
 */
async function raceAgainstAbort(work: Promise<void>, signal?: AbortSignal): Promise<void> {
  if (!signal) return work
  if (signal.aborted) return

  let onAbort = (): void => {}
  const abandoned = new Promise<void>((resolve) => {
    onAbort = () => resolve()
    signal.addEventListener('abort', onAbort, { once: true })
  })
  try {
    await Promise.race([work, abandoned])
  } finally {
    signal.removeEventListener('abort', onAbort)
  }
}

/**
 * Await `body` under `signal`, rejecting the moment `signal` aborts.
 *
 * WHY THIS EXISTS AT ALL, given that the same signal was handed to `fetch`. Aborting a
 * signal after the headers have landed is specified to error the response's body stream,
 * so a conforming `fetch` does end `response.json()` on its own. This function does not
 * trust that, for two reasons that are both real here: the transport is INJECTABLE
 * (`options.fetchImpl`), so the object carrying `json()` is whatever the caller handed
 * us and need not honour a signal at all; and a body that arrives through a proxy,
 * a service worker or a polyfilled `Response` is exactly the population most likely to
 * stall in the first place. A deadline that only holds when the transport cooperates is
 * not a deadline. This one settles the WAIT regardless — the read itself is left running
 * and unobserved, which costs nothing and cannot deadlock the caller.
 *
 * The rejection carries the signal's own reason, so the caller-abort and deadline cases
 * stay distinguishable one frame up: a cancellation must surface as the caller's
 * `AbortError`, never as an `ApiError`.
 */
function readUnderDeadline<T>(body: Promise<T>, signal: AbortSignal): Promise<T> {
  const reason = (): unknown => signal.reason ?? new DOMException('Aborted', 'AbortError')
  if (signal.aborted) {
    // Already over before the body was even offered. Attach a sink so abandoning the read
    // cannot surface later as an unhandled rejection.
    void body.then(
      () => {},
      () => {},
    )
    return Promise.reject(reason())
  }
  return new Promise<T>((resolve, reject) => {
    const onAbort = (): void => reject(reason())
    signal.addEventListener('abort', onAbort, { once: true })
    body.then(resolve, reject).finally(() => {
      signal.removeEventListener('abort', onAbort)
    })
  })
}

/**
 * Classify a GraphQL error envelope.
 *
 * Mirrors `safe_graphql_error`, which maps every code it does not recognise onto
 * `VALIDATION_FAILED` before it reaches us. We do NOT repeat that collapse on the
 * client: an unrecognised code becomes `UNKNOWN`, so a genuinely new server code
 * cannot silently masquerade as a validation failure in this codebase too.
 */
export function classifyErrors(errors: unknown): ApiErrorCode {
  if (!Array.isArray(errors) || errors.length === 0) return 'UNKNOWN'
  const first = errors[0] as { extensions?: { code?: unknown } } | null
  const code = first?.extensions?.code
  if (typeof code === 'string' && SERVER_ERROR_CODES.has(code)) return code as ApiErrorCode
  return 'UNKNOWN'
}

export interface GraphQLRequestOptions {
  /** Caller-owned cancellation — views abort in flight on unmount so a late reply cannot set state. */
  signal?: AbortSignal
  timeoutMs?: number
  /**
   * Transport override. Production code never passes this; tests do, so they can drive
   * the envelope/status/abort paths without patching `globalThis.fetch` — a shared
   * global that concurrently-running tests stomp on each other's copy of.
   */
  fetchImpl?: typeof fetch
}

interface GraphQLEnvelope<TData> {
  data?: TData | null
  errors?: unknown
}

/**
 * POST a GraphQL operation to the account surface.
 *
 * Resolves with `data`. Rejects with `ApiError` — `NETWORK` when the request never
 * produced a usable answer, otherwise the server's own code.
 *
 * Aborting via `options.signal` rejects with the caller's `AbortError` (a DOMException),
 * NOT an `ApiError`: a deliberate cancellation is not a failure and views must not
 * render an error state for one.
 */
export async function graphqlRequest<TData>(
  query: string,
  variables: Record<string, unknown>,
  options: GraphQLRequestOptions = {},
): Promise<TData> {
  const send = options.fetchImpl ?? fetch

  // Checked BEFORE anything reaches the network, including the CSRF bootstrap: a caller
  // who has already aborted gets no requests issued on their behalf at all.
  if (options.signal?.aborted) {
    throw options.signal.reason ?? new DOMException('Aborted', 'AbortError')
  }

  // Seeded before the timeout starts, so a slow bootstrap does not eat the mutation's
  // budget and report a healthy API as unreachable.
  //
  // Raced against the CALLER's signal (Vera, PR #17). The seed keeps its own deadline and
  // its own controller — it is shared by every request that arrives while it is in flight,
  // so one caller's cancellation must never abort a seed the others are still waiting on.
  // What was wrong was that a caller who abandoned the request at 500ms still sat out the
  // seed's full 5s: measured, the rejection surfaced at 5,001ms. Racing settles THIS
  // caller's wait without touching the shared GET, and the re-check below turns it into
  // the caller's own AbortError. Nothing user-visible depends on it today — the views
  // abort only on unmount — but any future cancel or retry affordance would inherit a
  // wait of up to 4.5 seconds on a promise the user already walked away from.
  if (needsCsrfBootstrap()) await raceAgainstAbort(ensureCsrfCookie(send), options.signal)

  // The bootstrap is awaited, so re-check: the user may have navigated away during it.
  if (options.signal?.aborted) {
    throw options.signal.reason ?? new DOMException('Aborted', 'AbortError')
  }

  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), options.timeoutMs ?? DEFAULT_TIMEOUT_MS)

  const abortFromCaller = () => controller.abort(options.signal?.reason)
  options.signal?.addEventListener('abort', abortFromCaller, { once: true })

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    Accept: 'application/json',
  }
  // The account surface's declared auth context is `customer_session_with_csrf`
  // (`graphql/route_contracts.py`) and Django's CsrfViewMiddleware is active, so send
  // the token whenever the cookie is readable. Read AFTER the bootstrap above, which is
  // the thing that brings the cookie into existence in the first place.
  const csrfToken = readCookie(CSRF_COOKIE_NAME)
  if (csrfToken) headers[CSRF_HEADER_NAME] = csrfToken
  // Built OUTSIDE the try on purpose: only genuine transport failures may be classified
  // as NETWORK, so nothing that could throw for another reason belongs inside it.
  const endpoint = `${apiBaseUrl()}${ACCOUNT_GRAPHQL_PATH}`
  const payload = JSON.stringify({ query, variables })

  // ONE try/finally around BOTH the headers and the body, and the teardown is at the end
  // of it. This used to be two: the timer was cleared and the caller's abort listener
  // removed in a `finally` that fired the instant HEADERS arrived, and `response.json()`
  // then ran with no deadline and no cancellation behind it. A server that answered and
  // then stalled the body left this promise unsettled forever — measured at 3,000ms with a
  // 200ms deadline and a caller abort at 100ms — and `SignInView.submit` awaits it, so the
  // page held at `aria-busy` with the button disabled and no banner and no way forward.
  // That is precisely the dead end FR-552 exists to prevent, and it was reached through
  // the one gap the deadline did not cover. Headers arriving is not an answer; the body is
  // the answer, and the deadline has to survive until it is in hand.
  let response: Response
  let envelope: GraphQLEnvelope<TData>
  try {
    try {
      response = await send(endpoint, {
        method: 'POST',
        headers,
        // Same-origin: carries the session cookie for the authenticated surfaces that
        // come later, and sends nothing at all if a deployment moves the API off-origin.
        credentials: 'same-origin',
        // Belt and braces with the page-level policy: a request URL must never become a
        // referrer that leaks the page's own token-bearing URL.
        referrerPolicy: 'no-referrer',
        body: payload,
        signal: controller.signal,
      })
    } catch (error) {
      // A caller-driven abort is passed through untouched; anything else is transport.
      if (options.signal?.aborted) throw error
      throw new ApiError('NETWORK', 'The request did not reach the API.')
    }

    try {
      envelope = (await readUnderDeadline(
        response.json(),
        controller.signal,
      )) as GraphQLEnvelope<TData>
    } catch (error) {
      // Same rule as the headers, for the same reason: a deliberate cancellation is not a
      // failure and must not be dressed up as one. Everything else — an HTML error page,
      // an empty body, gzip truncation, a proxy in the way, a body that simply stopped
      // arriving — is the same thing to a caller: no answer came back.
      if (options.signal?.aborted) throw error
      throw new ApiError('NETWORK', 'The API response could not be read.')
    }
  } finally {
    clearTimeout(timeout)
    options.signal?.removeEventListener('abort', abortFromCaller)
  }

  // Checked BEFORE `response.ok`: the API returns its error envelope on 200 for GraphQL
  // errors and on 4xx for routing errors, and the envelope is authoritative in both.
  if (envelope.errors) throw new ApiError(classifyErrors(envelope.errors))
  if (!response.ok) throw new ApiError('NETWORK', `Unexpected HTTP ${response.status}.`)
  if (envelope.data === null || envelope.data === undefined) throw new ApiError('UNKNOWN')

  return envelope.data
}
