/**
 * What the browser remembers about being signed in — which is deliberately almost nothing.
 *
 * THE CREDENTIAL IS NOT HERE, AND MUST NEVER BE
 * ---------------------------------------------
 * The account session is an opaque, server-side-hashed token delivered as the
 * `selahcue_account_session` cookie: HttpOnly, Secure, SameSite=Strict
 * (`_set_session_cookie`, `account_schema.py`). HttpOnly means JavaScript cannot read
 * it, and that is the point — an XSS on this origin can make requests as the user but
 * cannot walk off with a credential that keeps working after the tab closes.
 *
 * So the session persists across reload because the COOKIE persists, not because
 * anything here does. `src/lib/api/account.ts` never even selects `sessionToken` from
 * the login payload, so the raw value never enters this application at all.
 *
 * It is not a JWT. There is nothing encoded in it, nothing to decode, and no claim to
 * read. Any code that tries to parse session state out of a token is wrong twice over:
 * wrong about the format, and reaching for a value it does not have.
 *
 * WHAT THIS MODULE IS FOR
 * -----------------------
 * A HINT: the non-secret metadata `login` returns — role, org, expiry. It exists so the
 * navbar can render "Account" instead of "Sign in" on first paint without waiting for a
 * round trip, and so a guard can turn away an obviously-signed-out visitor without one.
 *
 * A HINT IS NOT AUTHORISATION. It is attacker-writable — it is just localStorage — and
 * it can be stale in the one direction that matters, claiming a session that the server
 * has since revoked. Nothing may be granted on the strength of it. `sessionStore.ts`
 * confirms with `accountViewer` before a protected route is entered, and the server
 * authorises every request on the cookie regardless of anything written here.
 *
 * Pure and dependency-free — no Vue, no DOM globals reached directly — so it is unit
 * tested under `node --test` with an injected storage.
 */

/** Non-secret metadata from `LoginPayload`. Note the absence of a token field. */
export interface SessionHint {
  role: string
  orgId: string
  /** ISO-8601 from `session.expires_at.isoformat()`. */
  expiresAt: string
}

export const SESSION_HINT_KEY = 'selahcue.session'

/**
 * The ONLY keys ever written or read back.
 *
 * Copying field by field rather than storing whatever the caller passed is a real
 * control, not tidiness: `login`'s payload type is one field away from carrying
 * `sessionToken`, and the natural mistake — `writeSessionHint(payload)` — would quietly
 * persist a credential to localStorage forever. Because the object is rebuilt from this
 * list, that mistake stores the three fields and drops the token on the floor.
 * `tests/session.test.ts` passes a token-bearing object in and asserts it does not land.
 */
const HINT_FIELDS = ['role', 'orgId', 'expiresAt'] as const

/** The `Storage` surface this module needs. Injected so it can be tested under Node. */
export interface HintStorage {
  getItem(key: string): string | null
  setItem(key: string, value: string): void
  removeItem(key: string): void
}

/**
 * Resolve the browser's storage, or `null` where there is none or it is unusable.
 *
 * Merely TOUCHING `localStorage` throws in a Firefox profile with cookies disabled, and
 * `setItem` throws in Safari private mode and when a quota is full. A sign-in flow must
 * not become unusable because a preference makes a convenience cache unavailable, so
 * every access here is guarded and every failure degrades to "no hint" — which costs one
 * `accountViewer` round trip and nothing else.
 */
export function defaultHintStorage(): HintStorage | null {
  try {
    const storage = globalThis.localStorage
    return storage ?? null
  } catch {
    return null
  }
}

function isNonEmptyString(value: unknown): value is string {
  return typeof value === 'string' && value !== ''
}

/**
 * Read the hint, or `null` when there is not a usable, unexpired one.
 *
 * `now` is injected rather than read from `Date.now()` so expiry is deterministic in
 * tests, matching the injected-clock convention the rest of this codebase follows.
 */
export function readSessionHint(
  now: number = Date.now(),
  storage: HintStorage | null = defaultHintStorage(),
): SessionHint | null {
  if (!storage) return null

  let raw: string | null
  try {
    raw = storage.getItem(SESSION_HINT_KEY)
  } catch {
    return null
  }
  if (!raw) return null

  let parsed: unknown
  try {
    parsed = JSON.parse(raw)
  } catch {
    // Someone else's key, a truncated write, a half-migrated older shape. Not an error
    // worth reporting — just not a session.
    return null
  }
  if (typeof parsed !== 'object' || parsed === null) return null

  const record = parsed as Record<string, unknown>
  // Rebuilt field by field, so a blob that has acquired extra keys — a token among them —
  // cannot carry them into the running application.
  const hint: SessionHint = {
    role: record.role as string,
    orgId: record.orgId as string,
    expiresAt: record.expiresAt as string,
  }
  for (const field of HINT_FIELDS) {
    if (!isNonEmptyString(hint[field])) return null
  }

  const expiresAt = Date.parse(hint.expiresAt)
  // An unparseable expiry is treated as dead rather than as "no expiry". Failing the
  // other way would make a corrupted timestamp into an immortal hint.
  if (Number.isNaN(expiresAt) || expiresAt <= now) return null

  return hint
}

/**
 * Persist the hint. Accepts anything hint-shaped; stores only the three allowed fields.
 *
 * The wide parameter type is intentional — it is what lets `writeSessionHint(payload)`
 * be safe rather than merely discouraged.
 */
export function writeSessionHint(
  hint: SessionHint & Record<string, unknown>,
  storage: HintStorage | null = defaultHintStorage(),
): void {
  if (!storage) return
  const safe: SessionHint = {
    role: hint.role,
    orgId: hint.orgId,
    expiresAt: hint.expiresAt,
  }
  try {
    storage.setItem(SESSION_HINT_KEY, JSON.stringify(safe))
  } catch {
    // Quota or a disabled store. The cookie is the real session; losing the hint costs a
    // round trip, never access.
  }
}

/** Forget the hint. Called on sign-out and whenever the server says the session is gone. */
export function clearSessionHint(storage: HintStorage | null = defaultHintStorage()): void {
  if (!storage) return
  try {
    storage.removeItem(SESSION_HINT_KEY)
  } catch {
    // Nothing useful to do; the cookie has already been cleared server-side.
  }
}
