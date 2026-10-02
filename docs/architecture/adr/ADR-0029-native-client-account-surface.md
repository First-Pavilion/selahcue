# ADR-0027: Native-client account sign-in — a cookie-free, CSRF-exempt `/v1` route pair, not an exemption of `/graphql/account`

- Status: Accepted by the API side; the wire shape (REST under `/v1` rather than a second GraphQL mount) is flagged for product-owner confirmation on ClickUp 86ak5t1gw
- Date: 2026-10-02
- Confidence: High on the safety argument; Medium on the wire shape (a reasoned choice between two sound shapes)
- Owner: Backend Engineer
- Related: ClickUp **86ak5t1gw** (this decision), **86ak5mn11** (the desktop licensing client it unblocks); DEC-004, DEC-005, DEC-007, DEC-011 pt 3 (`docs/decisions/DECISION-LOG.md`); ADR-0023 (customer auth, session model); `graphql/views.py::csrf_bootstrap` (the browser half of the same principle, "seed the cookie, do NOT exempt the route")

## Context

DEC-011 part 3 makes account sign-in the **primary** activation path. The desktop reaches it as `login` then `activateDeviceWithSession` on `POST /graphql/account`. A native client has no cookie jar and sends no `X-CSRFToken` (the `HttpTransport` seam can carry only a bearer — `selahcue-cloud/src/transport.rs`), and `CsrfViewMiddleware` is enabled with `AccountGraphQLView` not exempt. Every request got Django's 403 HTML page, which the client classified as a malformed response. The delegation path (`POST /v1/activations`, enrollment key) worked; the primary path did not, and the contract fixtures on both sides agreed perfectly the whole time because CSRF is transport middleware that sits in front of the wire shape.

**What the account GraphQL route authenticates from** (verified in code at `66e514ee`):

- `graphql/context.py::_read_account_session_token` accepts `Authorization: Bearer <token>` **or** the `selahcue_account_session` cookie. The cookie is an *ambient* credential: a browser attaches it on its own, including on a request an attacker's page caused.
- `login` and `refreshSession` **set** that cookie (`account_schema.py::_set_session_cookie`), so the login operation changes browser state.
- `activateDeviceWithSession`, `refreshSession`, `logout` and `accountViewer` are session-bound and therefore cookie-reachable.

So on this route the CSRF check is load-bearing for every operation except the pre-session ones, and `login` is itself a state-changing operation in the browser (login-CSRF). A route-level exemption would delete a declared, tested control (`route_contracts.py`: `customer_session_with_csrf`), and `SameSite=Strict` is not a substitute: it is scoped to the *site*, so it still carries the cookie for a same-site attacker such as a taken-over `*.selahcue.com` host, where a CSRF token does not.

CSRF is a confused-deputy attack that depends on ambient browser authority. A native client has no ambient authority to abuse, which is precisely why `/v1` is `csrf_exempt` and why that is safe there. The browser surface and the device surface have genuinely different threat models; the defect is that the desktop was pointed at the browser one.

## Options considered

- **(a) Exempt bearer-authenticated requests on the account surface.** Rejected. It cannot cover `login` (no bearer yet), so it does not solve the defect; and a route- or request-level exemption on a route that also reads a cookie is the exact thing `csrf_bootstrap`'s docstring argues against.
- **(b) The desktop performs the `/graphql/csrf` bootstrap and double-submit.** Rejected. It needs a cookie jar and a header map in `HttpTransport` (a native client permanently imitating a browser ceremony to satisfy a control for a threat it does not face), **and it still would not pass on HTTPS**: Django 6.1.1 `CsrfViewMiddleware.process_view` (`django/middleware/csrf.py:437-446`) rejects an HTTPS POST that carries no `Origin` header unless the `Referer` matches (`REASON_NO_REFERER`). A native client sends neither, so it would also have to forge browser headers — defeating the check, not satisfying it.
- **(c) A CSRF-exempt device-facing route, separate from the browser one.** Chosen, grounded in a separation the codebase already made (`urls.py`: "`/v1` is the device-token desktop surface and is `csrf_exempt`"), and in the owner's comment on 86ak5t1gw.
- **(c′) The same operations as a second, restricted GraphQL mount under `/v1`.** Considered and not chosen. It would keep the desktop's GraphQL wire (a one-path-constant change on the desktop), but it puts a GraphQL parser/executor, introspection and IDE settings on a new unauthenticated route, duplicates the resolvers, and returns the poorer GraphQL activation payload (no `reminted`, token metadata or licence block — the desktop crate documents those as REST-only). One suspected reason against it was **checked and discarded**: GraphQL aliases do not let one request carry many failing logins (a failed `login` nulls the non-null payload and the remaining aliases do not run — measured, one failed attempt counted for four aliased logins). That is not part of this decision. The cost of (c) over (c′) is a larger desktop change; it is accepted.

## Decision

Add two routes beside the rest of `/v1`, both `csrf_exempt`:

- `POST /v1/sessions` — `{"email", "password"}` → `{"session_token", "expires_at", "role", "org_id"}`. Calls the same `login` service as the GraphQL mutation.
- `POST /v1/activations:with-session` — `Authorization: Bearer <session_token>` + the `POST /v1/activations` body minus `license_key` → the `POST /v1/activations` response shape. Calls the same `activate_device_with_session` service as the GraphQL mutation (ADMIN only, same instance limit, same show-once device token and idempotency).

`/graphql/account` and `/graphql/admin` are **unchanged and not exempted**.

### Why the exemption is sound — for `login` specifically, not just the bearer mutation

CSRF protection exists to stop an attacker's page making a victim's browser perform an authenticated or state-changing action using credentials the browser attaches by itself. For the two new routes each ingredient is absent, and each absence is pinned by a test:

1. **No ambient credential in.** They read the session from the `Authorization` header only — never `request.COOKIES`, never the dev actor-header bridge, never a body field. A cookie-only request is `401`, even with a valid session cookie. (A cross-site page cannot set `Authorization` without a CORS preflight, and this API emits no CORS headers.)
2. **No state change in the browser out.** `/v1/sessions` never sets a cookie. Login-CSRF — a forged request that leaves the victim signed in as the attacker — needs the response to change the victim's browser; it does not, and the body is unreadable cross-origin.
3. **Not forgeable from an HTML form.** Both routes require `Content-Type: application/json`, which a cross-site form cannot send without a preflight. A `text/plain` form post is refused before any credential is looked at, and is not counted as a login attempt.

What is left for `login` is not a CSRF problem but ordinary credential abuse, which a forged request does no better than an attacker's own `curl`: guessing, and locking a victim's account. That is what the abuse protections below answer.

### Abuse story for the new unauthenticated login route

- **Per-IP throttle**, `SELAHCUE_THROTTLE_SESSION_LOGIN` (default 10 per minute), spent before the credential is checked and below `require_POST` so a 405 cannot burn budget. This is stronger than the surface it parallels: the browser login mutation has **no** app-level per-IP limit (it relies on the edge, per `deployments.md`).
- **Per-account lockout**: inherited, not re-implemented — the route calls the same `login`, so five failures lock the account for 15 minutes on **both** surfaces, shared state. The route is not a way around it.
- **No account-existence oracle**: unknown email and wrong password are indistinguishable (same status and body); a locked account is refused with the same code; an unverified account is `POLICY_DENIED` only after the right password. All inherited.
- **Bounded input**: email ≤ 254, password ≤ 200 characters, else `VALIDATION_FAILED` without attempting anything.
- **Provenance**: the audit rows for sign-in and activation over these routes carry `source_surface = desktop_v1`, so a session minted natively is distinguishable from a browser one.
- **Edge rule**: any per-IP rate rule keyed on `/graphql/account` does not cover these paths; `deployments.md` now says so.

Residual, accepted: a distributed guess spread across many source IPs (including a hostile page recruiting visitors' browsers to POST here — that works because the route is exempt, and is no worse than any botnet) is bounded only by the per-account lockout; and the lockout can be used to lock a victim out for 15 minutes. Both are properties of the existing browser login too.

## Consequences

- **The desktop must move to the new routes.** Until it does, the primary activation path stays blocked (fail-closed; never-blank is unaffected). The change is in `selahcue-licensing` (tracked as a follow-up). 86ak5mn11's "both activation paths work" claim must be re-verified after that lands, against a running server.
- **The activation response gains the REST shape** on the primary path: `reminted`, token metadata and the licence block, which the desktop could not see before.
- **The set of `csrf_exempt` routes is pinned** by `test_the_set_of_csrf_exempt_routes_is_pinned_and_excludes_every_graphql_route`: exempting anything else — in particular a GraphQL route — is a deliberate edit to that set, reviewed as a security decision.
- **The 30-day account session** (DEC-007) is what the native client holds after sign-in. That is the decided model; a narrower activation-only grant and a native revoke route would shrink it and are recorded as follow-ups, not blockers.
- **Integration evidence is now repeatable**: `test_live_server_a_cookieless_client_signs_in_activates_and_refreshes` runs a real server on a real socket with a cookie-less client, so this class of defect (CSRF is invisible to fixtures) is caught without the Docker Compose environment.

## Reversibility

Additive. Removing the two routes restores the previous state exactly; no migration, no data change, no GraphQL schema change. The two optional `source_surface` keywords on `login` and `activate_device_with_session` default to their previous values.
