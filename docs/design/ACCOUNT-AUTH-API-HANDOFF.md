# Account Auth — Backend → Frontend/Desktop Handoff

Traditional email/password customer authentication on the Platform API (DEC-007 / ADR-0023). This is the contract the desktop sign-in (and any web account surface) integrates against. Backend slices AUTH-1…AUTH-6 are implemented + tested (`implementation/api/tests/test_customer_auth_slice.py`).

## Endpoint

**Browser clients** use the **account GraphQL surface**: `POST /graphql/account` (contract `customer_session_with_csrf`) — the SPA seeds the CSRF cookie with `GET /graphql/csrf` first. **Native clients (the desktop) must NOT call `/graphql/account`**: it authenticates from a session cookie, so it enforces CSRF, and a client with no cookie jar and no `X-CSRFToken` gets Django's `403` HTML page on every request (86ak5t1gw). They use the two `/v1` routes in "Native client routes" below instead. Errors use the shared envelope `extensions.code` ∈ {`UNAUTHENTICATED`, `PERMISSION_DENIED`, `VALIDATION_FAILED`, `NOT_FOUND`, `POLICY_DENIED`, `RATE_LIMITED`}; messages are fixed + safe (no detail leakage).

## Session token — storage & transport

Login/refresh return a **show-once opaque session token** (`sessionToken`). It is also set as an HttpOnly/Secure/SameSite=Strict cookie (`selahcue_account_session`) for browser clients. **Desktop** must store the token in the **OS keychain** as `account_token` (via the existing `KeyringSecretStore` + redacting `Token` type — never env/files/logs, per FR-134/NFR-017) and present it on every authenticated call as `Authorization: Bearer <token>`. The raw token leaves the server **exactly once** (the login/refresh response) — persist it immediately.

- Session lifetime: **30 days** absolute (`ACCOUNT_SESSION_TTL_SECONDS`); call `refreshSession` to rotate+extend. A refresh **replaces** the token (old one is revoked) — persist the new one.
- Password change and `logout` **revoke** the session server-side; treat any `UNAUTHENTICATED` on an authenticated call as "signed out → return to sign-in".
- **Never-blank:** the account session is entirely separate from device entitlement. Sign-out / session expiry never revokes the device token or blanks live output.
- **Native account cleanup:** `POST /v1/sessions:revoke` with an account bearer and `{}` returns `{"revoked": true}` and ends only that account session. No cookie/CSRF token is sent or set. The existing desktop licensing client attempts this once immediately after a valid activation; cleanup failure is separate from activation success. Native `refreshSession` and browser `logout` remain unavailable on this transport; the 30-day DEC-007 TTL is unchanged.

## Mutations

| Mutation | Auth | Input → Output | Notes |
|---|---|---|---|
| `registerCustomerUser(input)` | none | `{idempotencyKey, email, password, orgName, country, displayName?, timezone?}` → `{accepted}` | **Self-serve** (DEC-007): creates a NEW org (TRIAL) + first Admin. Always `accepted:true` (no enumeration). Triggers a verification email. |
| `verifyEmail(token)` | none (token) | `token` → `{verified}` | Consumes the emailed token; activates the account. All failures → `VALIDATION_FAILED`. |
| `login(input)` | none | `{email, password}` → `{sessionToken, expiresAt, role, orgId}` | Unknown-email == wrong-password (`UNAUTHENTICATED`). Unverified/disabled → `POLICY_DENIED`. A locked account → the same `UNAUTHENTICATED` (never a distinct code: that would be an account-existence oracle). |
| `refreshSession` | session | → `{sessionToken, expiresAt}` | Rotates the token (old revoked). |
| `logout(allSessions?)` | session | → `{revoked}` | Revokes this (or all) session(s). Device tokens untouched. |
| `requestPasswordReset(email)` | none | `email` → `{accepted}` | Always `accepted:true` (no enumeration). Emails a reset link when the account exists. |
| `confirmPasswordReset(input)` | none (token) | `{token, newPassword}` → `{reset}` | Sets the new password; **revokes all sessions**. |
| `activateDeviceWithSession(input)` | session, **ADMIN** | `{idempotencyKey, deviceFingerprint, platform, appVersion?, displayName?}` → `{fullToken, created, devicePublicId, platform}` | DEC-005 account-based activation. `fullToken` is the show-once device token (null on replay). MEMBER → `PERMISSION_DENIED`; no active license → `NOT_FOUND`; at device limit → `POLICY_DENIED`. |

`accountViewer` query (session) → `{surface, actorId, orgId}` confirms the signed-in state.

> The mutations in this table are the **browser** contract (`POST /graphql/account`, CSRF-enforced). A native client uses the `/v1` routes in "Native client routes" below; in particular it cannot call `refreshSession`, `logout` or `accountViewer`.

## Native client routes (`/v1`) — what the desktop calls

Decision and safety argument: `docs/architecture/adr/ADR-0029-native-client-account-surface.md`. Both routes are `csrf_exempt` like the rest of `/v1`, and that is sound because neither reads or sets a cookie: the session travels in `Authorization: Bearer` only. Both require `Content-Type: application/json` (anything else is refused with `400 VALIDATION_FAILED` before the rate limit or any credential check), and the application responses of these two views (200, 400, 401, 403, 404) carry `Cache-Control: no-store`. Shared-throttle `429` responses also carry `Cache-Control: no-store` and `Retry-After` with the remaining fixed-window seconds, rounded up to at least one; unavailable expiry metadata gives a bounded full-window retry hint without changing the denial (17tnw2b1wqc). A `405` (wrong method) is produced by Django and does not carry these headers. Errors use the `/v1` envelope `{"error": {"code", "message"}, "surface": "desktop", "operation": ...}` with the same codes as above (branch on the **code**, not the status).

**`POST /v1/sessions`** — sign in (the `login` mutation's native twin; same service, so the lockout and the no-enumeration rule are identical).

- Request: `{"email": "...", "password": "..."}` (email at most 254 characters, password at most 200).
- `200`: `{"session_token", "expires_at", "role", "org_id", "surface": "desktop", "operation": "session_login"}`. `session_token` is show-once; keep it in the OS keychain as `account_token`. No `Set-Cookie`.
- `401 UNAUTHENTICATED` (unknown email, wrong password, **or a locked account** — indistinguishable), `403 POLICY_DENIED` (correct password but unverified/disabled), `400 VALIDATION_FAILED` (not JSON, wrong types, over-long), `429 RATE_LIMITED` (per-IP budget, 10 per minute by default).

**`POST /v1/activations:with-session`** — activate this device for the signed-in administrator's organisation (the `activateDeviceWithSession` mutation's native twin; ADMIN only, same instance limit).

- Header: `Authorization: Bearer <session_token>` (the session is **not** read from a cookie or the body).
- Request: `{"idempotency_key", "device_fingerprint", "platform", "app_version"?, "display_name"?}` — the `POST /v1/activations` body without `license_key`.
- All supplied fields must be strings; optional version/name may be omitted or empty. Control characters are refused before storage. Platform is `macos`, `windows`, or `linux`; fingerprint/name are at most128 characters and version at most32. Invalid types, unknown platforms, oversized bodies and excessively nested JSON return400 `VALIDATION_FAILED` in the same JSON envelope on both native activation routes (17tnw2b1wqd).
- `200`: exactly the `POST /v1/activations` response (`created`, `reminted`, `activation_token` — show-once, `null` on replay — `device`, `token`, `license`), with `"operation": "activation_with_session"`.
- `401 UNAUTHENTICATED` (no/invalid/expired session), `403 PERMISSION_DENIED` (MEMBER), `403 POLICY_DENIED` (instance limit, licence not activatable), `404 NOT_FOUND` (org has no active licence key), `400 VALIDATION_FAILED`, `429 RATE_LIMITED`.

The device token returned here is used exactly as one from the enrollment-key path (`POST /v1/license:refresh`, `GET /v1/entitlements/manifest`).

Enrollment `POST /v1/activations` also requires `application/json` before spending throttle budget or querying the database. For `POST /v1/license:refresh`, that guard applies when the token comes from the JSON body. Existing bearer-header refresh requests may omit the body and Content-Type: the Authorization header already requires a cross-origin preflight, and its token still passes the existing authentication checks. A header credential continues to take precedence over a body token; no cookie authentication or GET requirement is added (17tnw2b1wqb).

**`POST /v1/sessions:revoke`** — end only the account session in `Authorization: Bearer <session_token>`. Requires `application/json` and an empty object; no body/cookie credentials or all-sessions switch. Success200: `{"revoked":true,"surface":"desktop","operation":"session_revoke"}`. Invalid JSON/body400, absent/invalid/inactive bearer401, per-IP budget exhausted429 with `Retry-After` and `Cache-Control:no-store`. Content type and method are refused before spending budget. Separate fixed budget10/minute/IP; the browser GraphQL contract and devices are unchanged.

The Rust `activate_with_session` method returns a valid `Activation` even if its immediate cleanup request fails. `session_cleanup` is `Revoked` only after a positive acknowledgement; otherwise `RetryRequired` carries the existing bounded failure classification, never the response body. No automatic retry loop runs. `activate_and_persist_with_session` also stores the show-once device token before waiting on remote cleanup and clears only the matching licensing `account_session_token` after confirmed cleanup; device persistence and local-account removal have separate outcomes. Its caller must serialize custody operations. Cleanup failures never call `forget_all`, revoke a device, or gate presentation.

An unsuccessful/ambiguous activation retains the session for an idempotent activation retry. For an abandoned attempt or unconfirmed cleanup, a host may explicitly call `revoke_session` with that same token; only a confirmed acknowledgement permits clearing its local account entry. A lost revoke acknowledgement may leave an already inactive token retained; the client does not pretend it confirmed revocation. The existing DEC-007 expiry/password-change/all-session logout rules remain the server fallback, with no new grant or TTL policy. If device-token persistence fails after server activation, the returned activation still carries its show-once token for retrying persistence; do not repeat activation expecting that secret to be re-shown.

Current `main` has no operator licensing activation UI/command or pending-session orchestration. This ticket implements and tests the actual licensing-library path and secret-store seam, not operator/physical-booth E2E. The operator's separate hosted-provider `account_token` is untouched. ADR-0029 remains Proposed; implementing this task's route-only option does not assert owner acceptance of the broader wire/residual-risk decision.

## Frontend follow-ups (net-new vs the current A0/A1 design)

1. **Sign-UP screen** — the existing `ACCOUNT-SETUP-HANDOFF.md` (A0/A1) assumes the org already exists; self-serve signup needs a create-account form collecting **email, password, org name, country** (+ optional display name). First user becomes Admin.
2. **Email-verification screen** — "check your email" state + a deep-link/paste target that calls `verifyEmail`. Login is blocked (`POLICY_DENIED`) until verified.
3. **Forgot-password flow** — the "Forgot?" link on A1 → `requestPasswordReset`; a reset screen (from the email link) → `confirmPasswordReset` (then re-login; all sessions were revoked).
4. **Account-based device activation** — the Admin "activate this device" path calls `activateDeviceWithSession` (no enrollment key needed when signed in); the enrollment-key path remains for offline/secondary.
5. **Role gating (FR-137)** — hide device-management controls for MEMBER users (`login`/`accountViewer` expose `role`).

## Ops

New config keys documented in `deployments.md` §1c. `SELAHCUE_TRUST_ACTOR_HEADERS` **must be false in prod** — the session token is the sole customer authenticator there. Email delivery is a no-op seam until a provider is wired.
