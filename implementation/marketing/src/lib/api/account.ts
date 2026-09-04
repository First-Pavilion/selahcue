/**
 * Typed wrappers for the account GraphQL surface (`/graphql/account`).
 *
 * Field names and shapes are pinned against
 * `implementation/api/selahcue_api/graphql/account_schema.py`. Strawberry camel-cases
 * Python snake_case, so `confirm_password_reset` is `confirmPasswordReset` on the wire.
 *
 * The first four operations are UNAUTHENTICATED — they are reached from an email link by
 * someone who by definition cannot sign in yet. The sign-in group added for 86ak11r67
 * (`registerCustomerUser`, `login`) is unauthenticated too; `logout`, `refreshSession`
 * and `accountViewer` are authenticated by the session cookie the browser already holds.
 *
 * WHY NOTHING HERE EVER SELECTS `sessionToken`
 * -------------------------------------------
 * `LoginPayload` and `RefreshPayload` both expose `sessionToken` — the show-once opaque
 * credential. That field exists for the DESKTOP client, which has an OS keychain to put
 * it in. A browser must not ask for it.
 *
 * `_set_session_cookie` (`account_schema.py`) runs in the RESOLVER BODY, before the
 * payload is serialised, so the `selahcue_account_session` cookie is set whether or not
 * the field is selected. The cookie is HttpOnly, Secure and SameSite=Strict: the server
 * has deliberately put the credential somewhere JavaScript cannot reach. Selecting
 * `sessionToken` would undo that on purpose — it would deliver the same secret into the
 * JS heap, the response body, devtools, any HAR capture, and anything that has wrapped
 * `fetch`. So these documents select only the non-secret metadata, and the browser
 * authenticates with a credential it has never seen. `tests/apiSeam.test.ts` pins it.
 */

// Relative, not the `@` alias: these modules are pure and are unit-tested directly under
// `node --test`, which resolves real paths and knows nothing about Vite's alias. Views
// still import them via `@/lib/...`.
import { graphqlRequest, type GraphQLRequestOptions } from './graphql.ts'

/**
 * VERIFIED against `graphql/account_schema.py:179-182` (shipped in `5b6c0ae`).
 *
 * Python `resend_verification_email` → Strawberry camel-cases it to
 * `resendVerificationEmail`. Note the trailing `Email`: it does NOT follow
 * `requestPasswordReset`'s shorter shape, which is what this was originally wired
 * against while the mutation was still being built.
 *
 * Returns `ResendVerificationPayload { accepted: Boolean! }` — always `true`, and
 * deliberately carrying no other field, because an unknown address, an unverified
 * account and an already-verified one must be indistinguishable.
 */
export const RESEND_VERIFICATION_FIELD = 'resendVerificationEmail'

const VERIFY_EMAIL = `
  mutation VerifyEmail($token: String!) {
    verifyEmail(token: $token) {
      verified
    }
  }
`

const CONFIRM_PASSWORD_RESET = `
  mutation ConfirmPasswordReset($input: ConfirmPasswordResetInput!) {
    confirmPasswordReset(input: $input) {
      reset
    }
  }
`

const REQUEST_PASSWORD_RESET = `
  mutation RequestPasswordReset($email: String!) {
    requestPasswordReset(email: $email) {
      accepted
    }
  }
`

const RESEND_VERIFICATION = `
  mutation ResendVerification($email: String!) {
    ${RESEND_VERIFICATION_FIELD}(email: $email) {
      accepted
    }
  }
`

/**
 * Consume an email-verification token.
 *
 * Every failure mode the API knows — unknown, wrong-purpose, already consumed, expired —
 * arrives as one `VALIDATION_FAILED` (`services.py:494`, deliberate: no expiry oracle).
 * Callers must not try to infer which; V3 is the single honest failure state.
 */
export async function verifyEmail(token: string, options?: GraphQLRequestOptions): Promise<boolean> {
  const data = await graphqlRequest<{ verifyEmail: { verified: boolean } }>(
    VERIFY_EMAIL,
    { token },
    options,
  )
  return data.verifyEmail.verified
}

/**
 * Set a new password from a reset token.
 *
 * CALLER CONTRACT: validate `newPassword` with `validateNewPassword` first.
 *
 * THE ORDERING THIS COMMENT USED TO STATE IS NO LONGER TRUE, and the correction is the
 * point. It read: "`confirm_password_reset` checks the password at `services.py:732`
 * BEFORE it looks at the token, and raises the SAME `VALIDATION_FAILED` for both". FR-551
 * (PR #16, merged into this branch at `33237c0`) reversed exactly that. The function now
 * validates the token first — fingerprint, purpose, consumed, expiry, `services.py:1185`
 * to `1206`, every failure the one collapsed `VALIDATION_FAILED` — and only then the
 * password, at `services.py:1245`, where it raises the DISTINCT `PASSWORD_INVALID`.
 *
 * So the two failures are separable now, and the caller MUST separate them: a
 * `VALIDATION_FAILED` from this mutation is a token failure, and `PASSWORD_INVALID` is a
 * live link with a password the policy refused. `PASSWORD_INVALID` is reachable ONLY from
 * behind a token already found live, and the raise happens inside the enclosing
 * `transaction.atomic()`, so the token is not consumed — a view may tell the user their
 * link still works, and `ResetView.vue` does.
 *
 * The pre-flight guard survives the reorder for two reasons that never depended on it: a
 * password this client can reject costs no round trip and no rate-limit budget, and it is
 * the only thing able to say WHICH rule failed — `PASSWORD_INVALID` deliberately carries
 * no policy detail (`graphql/errors.py:28`). `submitNewPassword` in `ResetView.vue`
 * enforces it.
 */
export async function confirmPasswordReset(
  token: string,
  newPassword: string,
  options?: GraphQLRequestOptions,
): Promise<boolean> {
  const data = await graphqlRequest<{ confirmPasswordReset: { reset: boolean } }>(
    CONFIRM_PASSWORD_RESET,
    { input: { token, newPassword } },
    options,
  )
  return data.confirmPasswordReset.reset
}

/**
 * Ask for a fresh password-reset link.
 *
 * Returns `accepted: true` whether or not the address is registered — the no-enumeration
 * contract. Copy built on this result must stay conditional ("if this address has an
 * account…"); it must never claim an email was sent.
 */
export async function requestPasswordReset(
  email: string,
  options?: GraphQLRequestOptions,
): Promise<boolean> {
  const data = await graphqlRequest<{ requestPasswordReset: { accepted: boolean } }>(
    REQUEST_PASSWORD_RESET,
    { email },
    options,
  )
  return data.requestPasswordReset.accepted
}

/**
 * Ask for a fresh verification link. Shipped and live as of 86ak120ac (`5b6c0ae`).
 *
 * Resolves `true` for a valid address whether or not it has an account, whether or not
 * that account is verified, and whether or not anything was actually sent. That is the
 * entire point: the caller must learn nothing. Copy built on this result stays
 * conditional ("if this address has an account…") — see V5.
 *
 * Only two error codes are reachable:
 *   - `VALIDATION_FAILED` — the address is malformed (`_require_valid_email`). Rare,
 *     because `validateEmail` catches that on the field first.
 *   - `RATE_LIMITED` — one of three budgets is spent: the address, the caller IP, or a
 *     global ceiling.
 *
 * `RATE_LIMITED` IS NOT EVIDENCE THE ADDRESS IS REAL. The per-address budget is spent
 * before the account is even looked up, precisely so the limiter cannot become the
 * enumeration oracle the rest of this surface avoids. Never surface anything that would
 * let a user infer otherwise.
 *
 * TIMING IS A SECURITY PROPERTY HERE. The service pads the accepted path to a ~0.25s
 * floor and runs a dummy PBKDF2 on the ineligible branch so the three cases take the same
 * time. Do not add a "that returned too fast, it must have failed" heuristic, and do not
 * suppress the pending state to make it feel snappier — both would work against the
 * padding, and the second would just leave the user staring at an unresponsive button.
 */
export async function resendVerification(
  email: string,
  options?: GraphQLRequestOptions,
): Promise<boolean> {
  const data = await graphqlRequest<Record<string, { accepted: boolean }>>(
    RESEND_VERIFICATION,
    { email },
    options,
  )
  return data[RESEND_VERIFICATION_FIELD]?.accepted ?? false
}


// ---------------------------------------------------------------------------------------
// Sign-in / create-account / forgot-password (86ak11r67).
//
// Pinned against `account_schema.py`. Strawberry camel-cases the Python names, so
// `register_customer_user` is `registerCustomerUser` and `RegisterCustomerUserInput`'s
// `idempotency_key` is `idempotencyKey` on the wire.
// ---------------------------------------------------------------------------------------

const REGISTER_CUSTOMER_USER = `
  mutation RegisterCustomerUser($input: RegisterCustomerUserInput!) {
    registerCustomerUser(input: $input) {
      accepted
    }
  }
`

/**
 * Note the selection set: `expiresAt role orgId` and NOT `sessionToken`. See the module
 * header — the cookie is set by the resolver regardless, so asking for the raw token
 * would only copy a credential the server put out of JavaScript's reach back into it.
 */
const LOGIN = `
  mutation Login($input: LoginInput!) {
    login(input: $input) {
      expiresAt
      role
      orgId
    }
  }
`

const LOGOUT = `
  mutation Logout($allSessions: Boolean!) {
    logout(allSessions: $allSessions) {
      revoked
    }
  }
`

const REFRESH_SESSION = `
  mutation RefreshSession {
    refreshSession {
      expiresAt
    }
  }
`

const ACCOUNT_VIEWER = `
  query AccountViewer {
    accountViewer {
      surface
      actorId
      orgId
    }
  }
`

/** `RegisterCustomerUserInput` (`account_schema.py`). */
export interface RegisterAccountInput {
  /**
   * Client-generated, `^[A-Za-z0-9._:-]{12,128}$` (`validate_idempotency_key`).
   *
   * MUST be stable across retries of the SAME signup attempt. `register_customer_user`
   * namespaces the guard per email fingerprint, so a retry carrying the same key
   * converges on the existing row instead of racing a second one. A fresh key on every
   * retry would throw that guarantee away exactly when it matters — after a timeout,
   * when the client cannot tell whether the first attempt landed.
   */
  idempotencyKey: string
  email: string
  password: string
  orgName: string
  /** ISO 3166-1 alpha-2. `len(country) != 2` is a hard VALIDATION_FAILED server-side. */
  country: string
  displayName?: string
  /** IANA zone. Defaults to `UTC` server-side when blank. */
  timezone?: string
}

/**
 * Self-serve signup (DEC-007).
 *
 * Returns `accepted: true` whether the address is new OR already registered — the
 * no-enumeration contract, and the reason 86ak120kw rules that the gap-fill handoff's
 * "this email already exists" error MUST NOT be built. An existing address gets an
 * out-of-band "account exists" email to its real owner; the submitter learns nothing.
 *
 * CALLER CONTRACT: validate email, password, org name and country with
 * `validateSignup` first. `register_customer_user` checks all four before it looks at
 * anything else and raises ONE `VALIDATION_FAILED` for every one of them, so an
 * unvalidated submit produces an error the UI cannot attribute — and the one thing it
 * must never guess is that the error was about the email.
 */
export async function registerAccount(
  input: RegisterAccountInput,
  options?: GraphQLRequestOptions,
): Promise<boolean> {
  const data = await graphqlRequest<{ registerCustomerUser: { accepted: boolean } }>(
    REGISTER_CUSTOMER_USER,
    {
      input: {
        idempotencyKey: input.idempotencyKey,
        email: input.email,
        password: input.password,
        orgName: input.orgName,
        country: input.country,
        displayName: input.displayName ?? '',
        timezone: input.timezone ?? 'UTC',
      },
    },
    options,
  )
  return data.registerCustomerUser.accepted
}

/** The non-secret half of `LoginPayload`. The token itself is never requested. */
export interface SessionMetadata {
  expiresAt: string
  role: string
  orgId: string
}

/**
 * Authenticate and establish a session.
 *
 * The three failure codes, and why the UI must keep them apart:
 *
 *   - `UNAUTHENTICATED` — unknown email, wrong password, OR a locked-out account. The
 *     service runs a dummy PBKDF2 on the unknown-email branch and a real one on the
 *     locked branch specifically so all three take the same time and return the same
 *     code. Rendering ANY difference between them — different copy, a different state,
 *     an extra hint — hands back the enumeration oracle the service paid for. One
 *     message, always.
 *   - `POLICY_DENIED` — the password was CORRECT but the account is unverified or not
 *     active. This does disclose that the account exists, deliberately: it is only ever
 *     reachable by someone who already proved they know the password, so it discloses
 *     to the owner and to nobody else. It is the one branch that may say more, and it
 *     must offer a way forward (a fresh verification link) rather than stopping.
 *   - `NETWORK` — we never reached the API. Never report this as a credential failure.
 */
export async function login(
  email: string,
  password: string,
  options?: GraphQLRequestOptions,
): Promise<SessionMetadata> {
  const data = await graphqlRequest<{ login: SessionMetadata }>(
    LOGIN,
    { input: { email, password } },
    options,
  )
  return data.login
}

/**
 * Revoke the current session (or every session for the user).
 *
 * Revokes the ACCOUNT session ONLY. Device tokens and cached entitlements are untouched
 * by design — an activated machine keeps presenting offline after its operator signs
 * out. That is the never-blank guarantee, and it is why sign-out copy may not imply
 * anything about live output.
 */
export async function logout(
  allSessions = false,
  options?: GraphQLRequestOptions,
): Promise<boolean> {
  const data = await graphqlRequest<{ logout: { revoked: boolean } }>(
    LOGOUT,
    { allSessions },
    options,
  )
  return data.logout.revoked
}

/**
 * Rotate the session token and extend the window.
 *
 * The presented token is read from the cookie by the server, and the replacement is
 * written back to the cookie by the resolver, so this whole exchange happens without the
 * client handling either value. Only `expiresAt` is selected.
 */
export async function refreshSession(options?: GraphQLRequestOptions): Promise<string> {
  const data = await graphqlRequest<{ refreshSession: { expiresAt: string } }>(
    REFRESH_SESSION,
    {},
    options,
  )
  return data.refreshSession.expiresAt
}

/** `AccountViewer` (`account_schema.py`). */
export interface AccountViewer {
  surface: string
  actorId: string
  orgId: string
}

/**
 * Ask the server whether the cookie we are holding is a live session.
 *
 * This is the ONLY honest answer to "is the user signed in?". The credential is
 * HttpOnly, so the client genuinely cannot inspect it, and anything stored locally is a
 * hint about a past login rather than evidence of a current one. `UNAUTHENTICATED` here
 * means the session is gone — expired, revoked, or invalidated by a password change.
 */
export async function accountViewer(options?: GraphQLRequestOptions): Promise<AccountViewer> {
  const data = await graphqlRequest<{ accountViewer: AccountViewer }>(ACCOUNT_VIEWER, {}, options)
  return data.accountViewer
}
