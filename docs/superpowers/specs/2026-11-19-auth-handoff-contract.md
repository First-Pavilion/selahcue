# Auth handoff contract correction

Authority: [existing ticket86ak120kw](https://app.clickup.com/t/86ak120kw), its comment adding the forgot-password enumeration correction, current maina53d2ca5b97d72d4f353a9a9748f1e3ccc1eaf54, and the user's delegated backlog implementation/review/merge instruction. This is a correction to implementation guidance, with no application behavior change.

## Intent and scope

Make `docs/design/MARKETING-PORTAL-GAP-FILL-HANDOFF.md` §§3–5 safe to build from. Reconcile directly related signup, verification-resend, reset-password and correction notes in `docs/design/AUTH-LANDING-PAGES-HANDOFF.md`, plus the signup and reset-request Notes cells in `docs/design/ACCOUNT-AUTH-API-HANDOFF.md`. Confirm the contract against backend and current marketing code; sweep `docs/design/` and shipped account email templates for equivalent contradictory normative instructions. Preserve historical descriptions when clearly labeled as superseded, rather than erasing evidence.

## Approaches considered

Use narrow source-backed corrections in the two handoffs and any equivalent live instructions found by the required sweep. This closes the identified regression trap without inventing product behavior. Rewriting auth code to match the old spec would introduce enumeration and reject existing credentials, so it is outside the ticket. Rewriting unrelated device, OAuth or paid-plan designs would need their own scope and evidence.

## Binding contract

- Registration: valid, admitted submissions use one accepted/check-email state for existing and new addresses. Only the address owner receives account-exists guidance out of band. Acceptance neither proves account creation nor delivery and creates no authenticated session; remove both the email-taken error and the automatic account-success redirect. Validation, rate-limit and transient errors remain errors, never existence signals.
- Forgot password: use the same conditional accepted state for known/unknown addresses. Remove email-not-found. Resend success means accepted request, not guaranteed delivery. A failed request stays in its error/form state.
- Verification resend: the shipped mutation gives admitted callers one accepted result across address states. Use conditional check-inbox copy on acceptance and retain error states. Mark the previous missing-mutation estimate as historical.
- Sign-in: require a nonempty submitted password, with no new-password minimum, maximum or composition checks and no silent trimming. This follows current `SignInView.validate` and `accounts.services.login`; the old ticket's request to apply10 characters to §3c is superseded by this source-backed distinction. Acceptance of input is not successful authentication.
- Creation/reset: shipped policy is10–200 Unicode code points inclusive, length-only, with no uppercase/number requirement. Empty/all-whitespace and non-UTF-8-encodable values are rejected; accepted values are not trimmed. Confirmation must match on the client. Any retained strength indicator is advisory and cannot become a composition or submission gate.
- Reset links: shipped lifetime is1hour from issuance; email verification uses24hours. These are defaults and current copy, not a statement about unverified production overrides. Never diagnose a token as expired from its advertised lifetime alone.
- Reset confirmation: DEC-017 and `_consume_reset_token` validate a live reset token before the new-password policy, then revalidate under the write lock. `PASSWORD_INVALID` behind a live token is a correctable password error and does not consume the token. Unknown/expired/used/wrong-purpose token failures remain collapsed. Replace the companion handoff's obsolete password-first/shared-error note; preserve its valid token-failure collapse rule.

## Verification and boundaries

A backend engineer confirms each statement against current source and existing tests by inspection. Record a scoped before/after sweep with matches classified as live contract, superseded history, legitimate unrelated value or defect. Verify local references, changed-path scope and `git diff --check`. This is documentation-only: do not add mirror tests or run application/native/browser/CI suites, install dependencies or read secrets. Existing tests are references, not new passing evidence. Independent code/spec and security review plus final whole-branch review are required before the authorized merge; no performance gate is warranted for unchanged executable code.

No new auth policy, timing guarantee, provider/deployment choice, UI redesign, OAuth work, runtime qualification or broad design cleanup belongs to this ticket. Report any runtime or template defect identified in the sweep before expanding the documentation scope. No separate staff messages are needed: the current ticket comments already document the downstream warning and shipped safe views.
