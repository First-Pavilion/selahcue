/**
 * The marketing SPA's single HTTP seam.
 *
 * This is the FIRST networking code in `implementation/marketing/src` — before this
 * there were no fetch/axios/gql calls anywhere — so it is deliberately the one place
 * that knows about transport, CSRF, cancellation and the API's error envelope. Later
 * work (sign-in wiring 86ak11r67, account portal 86ak11rjz) should add typed wrappers
 * next to `account.ts` and reuse `graphqlRequest`, not re-open `fetch`.
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
 * 3. TRANSPORT FAILURE IS NOT A VALIDATION FAILURE. `ApiErrorCode.NETWORK` exists
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
  | 'INTERNAL'
  /** Client-only: the request never got a usable answer (offline, DNS, TLS, timeout, proxy, non-JSON body). */
  | 'NETWORK'
  /** Client-only: a well-formed error envelope carrying a code this client does not know. */
  | 'UNKNOWN'

const SERVER_ERROR_CODES: ReadonlySet<string> = new Set([
  'UNAUTHENTICATED',
  'PERMISSION_DENIED',
  'VALIDATION_FAILED',
  'NOT_FOUND',
  'CONFLICT',
  'POLICY_DENIED',
  'RATE_LIMITED',
  'NOT_IMPLEMENTED',
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
  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), options.timeoutMs ?? DEFAULT_TIMEOUT_MS)

  const abortFromCaller = () => controller.abort(options.signal?.reason)
  if (options.signal) {
    if (options.signal.aborted) {
      clearTimeout(timeout)
      throw options.signal.reason ?? new DOMException('Aborted', 'AbortError')
    }
    options.signal.addEventListener('abort', abortFromCaller, { once: true })
  }

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    Accept: 'application/json',
  }
  // The account surface's declared auth context is `customer_session_with_csrf`
  // (`graphql/route_contracts.py`) and Django's CsrfViewMiddleware is active, so send
  // the token whenever the cookie is readable. It is absent today — nothing issues one
  // to this origin yet — which is tracked on 86ak11r67.
  const csrfToken = readCookie(CSRF_COOKIE_NAME)
  if (csrfToken) headers[CSRF_HEADER_NAME] = csrfToken

  const send = options.fetchImpl ?? fetch
  // Built OUTSIDE the try on purpose: only genuine transport failures may be classified
  // as NETWORK, so nothing that could throw for another reason belongs inside it.
  const endpoint = `${apiBaseUrl()}${ACCOUNT_GRAPHQL_PATH}`
  const payload = JSON.stringify({ query, variables })

  let response: Response
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
  } finally {
    clearTimeout(timeout)
    options.signal?.removeEventListener('abort', abortFromCaller)
  }

  let envelope: GraphQLEnvelope<TData>
  try {
    envelope = (await response.json()) as GraphQLEnvelope<TData>
  } catch {
    // HTML error page, empty body, gzip truncation, a proxy in the way: not an answer.
    throw new ApiError('NETWORK', 'The API response could not be read.')
  }

  // Checked BEFORE `response.ok`: the API returns its error envelope on 200 for GraphQL
  // errors and on 4xx for routing errors, and the envelope is authoritative in both.
  if (envelope.errors) throw new ApiError(classifyErrors(envelope.errors))
  if (!response.ok) throw new ApiError('NETWORK', `Unexpected HTTP ${response.status}.`)
  if (envelope.data === null || envelope.data === undefined) throw new ApiError('UNKNOWN')

  return envelope.data
}
