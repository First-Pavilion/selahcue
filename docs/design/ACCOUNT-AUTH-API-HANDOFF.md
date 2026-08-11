# Account Auth — Backend → Frontend/Desktop Handoff

Traditional email/password customer authentication on the Platform API (DEC-007 / ADR-0023). This is the contract the desktop sign-in (and any web account surface) integrates against. Backend slices AUTH-1…AUTH-6 are implemented + tested (`implementation/api/tests/test_customer_auth_slice.py`).

## Endpoint

All mutations/queries are on the **account GraphQL surface**: `POST /graphql/account` (contract `customer_session_with_csrf`). Errors use the shared envelope `extensions.code` ∈ {`UNAUTHENTICATED`, `PERMISSION_DENIED`, `VALIDATION_FAILED`, `NOT_FOUND`, `POLICY_DENIED`, `RATE_LIMITED`}; messages are fixed + safe (no detail leakage).

## Session token — storage & transport

Login/refresh return a **show-once opaque session token** (`sessionToken`). It is also set as an HttpOnly/Secure/SameSite=Strict cookie (`selahcue_account_session`) for browser clients. **Desktop** must store the token in the **OS keychain** as `account_token` (via the existing `KeyringSecretStore` + redacting `Token` type — never env/files/logs, per FR-134/NFR-017) and present it on every authenticated call as `Authorization: Bearer <token>`. The raw token leaves the server **exactly once** (the login/refresh response) — persist it immediately.

- Session lifetime: **30 days** absolute (`ACCOUNT_SESSION_TTL_SECONDS`); call `refreshSession` to rotate+extend. A refresh **replaces** the token (old one is revoked) — persist the new one.
- Password change and `logout` **revoke** the session server-side; treat any `UNAUTHENTICATED` on an authenticated call as "signed out → return to sign-in".
- **Never-blank:** the account session is entirely separate from device entitlement. Sign-out / session expiry never revokes the device token or blanks live output.

## Mutations

| Mutation | Auth | Input → Output | Notes |
|---|---|---|---|
| `registerCustomerUser(input)` | none | `{idempotencyKey, email, password, orgName, country, displayName?, timezone?}` → `{accepted}` | **Self-serve** (DEC-007): creates a NEW org (TRIAL) + first Admin. Always `accepted:true` (no enumeration). Triggers a verification email. |
| `verifyEmail(token)` | none (token) | `token` → `{verified}` | Consumes the emailed token; activates the account. All failures → `VALIDATION_FAILED`. |
| `login(input)` | none | `{email, password}` → `{sessionToken, expiresAt, role, orgId}` | Unknown-email == wrong-password (`UNAUTHENTICATED`). Unverified/disabled → `POLICY_DENIED`. Lockout → `RATE_LIMITED`. |
| `refreshSession` | session | → `{sessionToken, expiresAt}` | Rotates the token (old revoked). |
| `logout(allSessions?)` | session | → `{revoked}` | Revokes this (or all) session(s). Device tokens untouched. |
| `requestPasswordReset(email)` | none | `email` → `{accepted}` | Always `accepted:true` (no enumeration). Emails a reset link when the account exists. |
| `confirmPasswordReset(input)` | none (token) | `{token, newPassword}` → `{reset}` | Sets the new password; **revokes all sessions**. |
| `activateDeviceWithSession(input)` | session, **ADMIN** | `{idempotencyKey, deviceFingerprint, platform, appVersion?, displayName?}` → `{fullToken, created, devicePublicId, platform}` | DEC-005 account-based activation. `fullToken` is the show-once device token (null on replay). MEMBER → `PERMISSION_DENIED`; no active license → `NOT_FOUND`; at device limit → `POLICY_DENIED`. |

`accountViewer` query (session) → `{surface, actorId, orgId}` confirms the signed-in state.

## Frontend follow-ups (net-new vs the current A0/A1 design)

1. **Sign-UP screen** — the existing `ACCOUNT-SETUP-HANDOFF.md` (A0/A1) assumes the org already exists; self-serve signup needs a create-account form collecting **email, password, org name, country** (+ optional display name). First user becomes Admin.
2. **Email-verification screen** — "check your email" state + a deep-link/paste target that calls `verifyEmail`. Login is blocked (`POLICY_DENIED`) until verified.
3. **Forgot-password flow** — the "Forgot?" link on A1 → `requestPasswordReset`; a reset screen (from the email link) → `confirmPasswordReset` (then re-login; all sessions were revoked).
4. **Account-based device activation** — the Admin "activate this device" path calls `activateDeviceWithSession` (no enrollment key needed when signed in); the enrollment-key path remains for offline/secondary.
5. **Role gating (FR-137)** — hide device-management controls for MEMBER users (`login`/`accountViewer` expose `role`).

## Ops

New config keys documented in `deployments.md` §1c. `SELAHCUE_TRUST_ACTOR_HEADERS` **must be false in prod** — the session token is the sole customer authenticator there. Email delivery is a no-op seam until a provider is wired.
