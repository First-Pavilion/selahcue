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
 * ASSUMED FIELD NAME — the only unverified thing in this file.
 *
 * The resend-verification mutation does not exist yet; 86ak120ac is building it. That
 * ticket specifies the semantics (identical response for unverified / already-verified /
 * unknown address, supersede the prior token, rate-limited) but not the field name, so
 * this mirrors the shipped `requestPasswordReset`, which has exactly the same shape and
 * the same no-enumeration contract.
 *
 * It is a named constant precisely so that reconciling with what Kenji actually ships is
 * a ONE-LINE change here and nothing else moves.
 */
export const RESEND_VERIFICATION_FIELD = 'resendVerification'

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
 * Ask for a fresh verification link.
 *
 * NOT YET AVAILABLE — see `RESEND_VERIFICATION_FIELD`. Until 86ak120ac merges, the API
 * has no such field and this rejects. `VerifyView` handles that by showing an honest
 * "we couldn't send that just now" line rather than the success state, so the button
 * never claims to have sent an email that was not sent.
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
