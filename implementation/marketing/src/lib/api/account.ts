/**
 * Typed wrappers for the account GraphQL surface (`/graphql/account`).
 *
 * Field names and shapes are pinned against
 * `implementation/api/selahcue_api/graphql/account_schema.py`. Strawberry camel-cases
 * Python snake_case, so `confirm_password_reset` is `confirmPasswordReset` on the wire.
 *
 * Every operation here is UNAUTHENTICATED — it is reached from an email link by someone
 * who by definition cannot sign in yet.
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
 * `confirm_password_reset` checks the password at `services.py:732` BEFORE it looks at
 * the token, and raises the SAME `VALIDATION_FAILED` for both — so an unvalidated short
 * password comes back indistinguishable from a dead link, and the user is told to go get
 * a new link they do not need. `submitNewPassword` in `ResetView.vue` enforces this.
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
