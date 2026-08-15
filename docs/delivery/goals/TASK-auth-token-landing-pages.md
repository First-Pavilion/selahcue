# Goal Contract — TASK-auth-token-landing-pages

## Identity

- Goal ID: TASK-auth-token-landing-pages
- Parent goal ID: EPIC-86ajy5v6k (Platform API / Licensing & Entitlements)
- Title: `/verify` and `/reset` token-landing pages exist in the marketing SPA and complete the shipped email flows
- Role: frontend-engineer
- Status: GATE_REVIEW
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86ak10b1t
- Design: `docs/design/AUTH-LANDING-PAGES-HANDOFF.md` · Figma `SYQn5hFY8YVQKm3c6rw0eJ` web section `743:124`
- Backend dependency: 86ak120ac (`resendVerification` mutation — NOT merged at start of this goal)
- Open decision: 86ak120fz (distinguishable `EXPIRED` code — blocks frames V4 / R5)
- Created: 2026-08-14
- Updated: 2026-08-15 (resend contract reconciled against 5b6c0ae)
- Maximum iterations: 10
- Independent verification required: yes (code review + QA; end-to-end MailHog evidence is owner/QA-run)

## Objective

`GET /verify?token=…` and `GET /reset?token=…` on the marketing SPA resolve to real pages that consume the
token against `/graphql/account`, render every client-distinguishable state from the design, and never submit a
password the API would reject for length — so the verification and password-reset emails that shipped today
stop landing on a 404.

## Baseline (Verified)

- `implementation/api/selahcue_api/apps/accounts/tasks.py:55,64` build `{FRONTEND_BASE_URL}/verify?token=` and
  `/reset?token=`; `FRONTEND_BASE_URL` defaults to `http://localhost:2000` (`settings.py:277`).
- `implementation/marketing/src/router/index.ts` has **no** `/verify` or `/reset` route → both 404.
  `implementation/web/` is a lone README (not the owning surface).
- **There are zero API calls in `implementation/marketing/src`** — no `fetch`, `axios`, `gql` or `XHR`
  anywhere. This goal establishes the SPA's first networking seam.
- **There is no JavaScript test setup anywhere in the repository** — no `vitest`, `jest`,
  `@testing-library`, `playwright` or `cypress` in any `package.json`. `implementation/marketing/package.json`
  has scripts `dev` / `build` / `preview` only. No CI workflow references the marketing SPA at all.
- API contract (`graphql/account_schema.py`, `apps/accounts/services.py`):
  - `verifyEmail(token: String!) { verified }`; `confirmPasswordReset(input:{token,newPassword}) { reset }`;
    `requestPasswordReset(email: String!) { accepted }`. **No resend-verification mutation exists** (grep for
    "resend" across `implementation/api` returns nothing).
  - Errors are HTTP 200 with `{"errors":[{"message","extensions":{"code"}}]}`; `safe_graphql_error` collapses
    every unknown code to `VALIDATION_FAILED`.
  - `verify_email` (services.py:494) and `confirm_password_reset` (services.py:726) collapse
    unknown / wrong-purpose / consumed / expired into one `VALIDATION_FAILED` — no expiry oracle.
  - `confirm_password_reset` calls `_validate_password` **at line 732, before** it reads the token
    (line 733+), and `_validate_password` (line 273) raises the *same* `VALIDATION_FAILED` for
    length outside `10..200` **and for an all-whitespace password**.
- `MIN_PASSWORD_LENGTH = 10` (settings-driven), `MAX_PASSWORD_LENGTH = 200` (services.py:208-209).
- The account GraphQL surface's declared auth context is `customer_session_with_csrf`
  (`graphql/route_contracts.py:41`), `CsrfViewMiddleware` is active and the GraphQL views are **not**
  `csrf_exempt`. `CORS_ALLOWED_ORIGINS` is read from env but `corsheaders` is in neither `INSTALLED_APPS`
  nor `MIDDLEWARE`, so no CORS headers are emitted today.
- `implementation/marketing/nginx.conf` sets `Referrer-Policy "no-referrer-when-downgrade"`, which would send
  the full token-bearing URL as a `Referer` to same-scheme cross-origin destinations.

## Inputs and evidence sources

- ClickUp `86ak10b1t` + its 2026-08-14 implementation-notes comment; `86ak120ac`; `86ak120fz`.
- `docs/design/AUTH-LANDING-PAGES-HANDOFF.md` (§2.2 tokens, §3 node map, §4–5 per-frame, §8 copy deck,
  §10.2/§10.3 backend gaps, §12 a11y, §13 responsive).
- `implementation/api/selahcue_api/{graphql/account_schema.py,graphql/errors.py,apps/accounts/services.py,settings.py}`.
- Existing SPA conventions: `src/views/SignInView.vue`, `src/components/{FormField,UiButton}.vue`,
  `src/assets/styles/tokens.css`, `src/router/index.ts`.
- Headless-check precedent: `scripts/operator_headless.py`.

## Scope

### In scope

- Routes `/verify` and `/reset` in the marketing SPA (the owning surface — decision recorded below).
- `/verify` states **V1** verifying, **V2** verified, **V3** merged link-failure (with resend), **V5** new link
  sent, **V6** missing token.
- `/reset` states **R1** form, **R2** client validation errors, **R3** submitting, **R4** merged link-failure
  (with request-new-link), **R6** password updated, **R7** server error; plus a **missing-token** state built
  on V6's designed pattern.
- A reusable API-call seam (`src/lib/api/`) — the first in the SPA — that later tickets (86ak11r67, 86ak11rjz)
  reuse.
- Client-side password validation that mirrors `_validate_password` exactly (length 10–200, non-blank), so a
  short password can never be mis-reported as a dead link.
- Token hygiene: token scrubbed from the URL on arrival; never logged; never placed in an error message.

### Non-goals

- **V4 / R5** (the TTL-specific frames) — unreachable until 86ak120fz decides whether the API exposes a
  distinguishable `EXPIRED`. Per the designer's note, building two states the API cannot tell apart would
  make the page lie. Tracked, not skipped.
- Desktop sign-up A11–A13 (86ajy7anx adjacency) and Manage-devices D1–D6 — separate stories in §15 of the handoff.
- Sign-in wiring (86ak11r67) and the account portal (86ak11rjz) — this goal only lays the seam they reuse.
- Any change under `implementation/api/` or `implementation/mobile/` — Kenji and Mika are working there
  concurrently. `settings.py:275-276`'s stale comment (ticket AC7) is therefore handed back, not edited.

### Constraints

- Stay entirely within `implementation/marketing/` (plus this contract). Path-scoped `git add` only.
- Reuse the shipped SPA conventions: `<script setup lang="ts">` SFCs, scoped `<style>`, `--sc-*` tokens
  (handoff §2.2 maps the Figma legacy ramp onto them), `FormField`, `UiButton`, lazy-imported route components.
- Dark ramp only — the design system defines no light variant. "Theme" is never used for appearance in this
  codebase (it means a slide-design template).
- No new runtime or dev dependency may be added to `package.json`.

### Assumptions and unknowns

- **RESOLVED (was ASSUMED)** — the resend mutation shipped in `5b6c0ae`. The assumed name was **WRONG**:
  the field is `resendVerificationEmail`, not `resendVerification` (Python `resend_verification_email`,
  `account_schema.py:179-182`). Corrected, and now pinned by both a unit test and a headless assertion on the
  query document. Payload confirmed as `ResendVerificationPayload { accepted: Boolean! }`
  (`account_schema.py:102-105`). Isolating it behind one constant is what made this a one-line correction.
- **Verified from source, not reported** — only `VALIDATION_FAILED` (malformed address) and `RATE_LIMITED`
  (`enforce_budget`, `throttling/guards.py:45`) are reachable. The per-address budget is spent BEFORE the
  account lookup (`services.py:596-613`) so a rate limit is not evidence the address exists; the copy is
  worded accordingly and a headless check asserts it never implies otherwise. The service also pads the
  accepted path to a floor and runs a dummy PBKDF2 on the ineligible branch (`services.py:628-632`) — the
  latency is a security property, so the client adds no timing heuristic and does not suppress the pending
  state.
- **UNKNOWN** — whether the SPA and API will be served same-origin in production. This goal defaults the client
  to a **relative** `/graphql/account` and ships dev+nginx proxies, which removes CORS and makes the
  `SameSite=Strict` session cookie work for the later portal tickets. `VITE_API_BASE_URL` overrides it if the
  deployment chooses cross-origin. Validation owner: /devops-engineer + /backend-engineer (86ak11r67).
- **UNKNOWN** — CSRF. The account surface requires `customer_session_with_csrf` but nothing issues a CSRF
  cookie to the SPA today. The client sends `X-CSRFToken` when a `csrftoken` cookie is present. Whether the
  unauthenticated token mutations are exempted or a CSRF-bootstrap endpoint is added is Kenji's call
  (86ak11r67). Verified as a real gap, not an assumption.

## Dependencies and approvals

- 86ak120ac (`resendVerification`) — /backend-engineer — **NOT MERGED**. Blocks live verification of the V3/V6
  resend path only. `/reset`'s "send a new reset link" uses the shipped `requestPasswordReset` and is unaffected.
- 86ak120fz (`EXPIRED` code decision) — product + /security-reviewer — **OPEN**. Blocks V4/R5.
- 86ak11r67 (CORS/session config for the SPA origin) — /backend-engineer — **IN FLIGHT**.

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | `/verify` and `/reset` are registered routes that resolve to a rendered page instead of 404 | headless check loads `http://127.0.0.1:PORT/verify` and `/reset` over the built bundle | both render the auth card; neither is the router's unmatched path | headless: 17 scenarios reach a rendered auth card; `/verify` and `/reset` both resolve | PASS |
| C-002 | yes | A password shorter than 10 chars is rejected client-side and never reaches `confirmPasswordReset` | `npm test` — the explicit 6-character case from the ClickUp note | rejected with "Password must be at least 10 characters."; zero mutations dispatched | `npm test` 48/48; headless `reset-short-password`: 0 mutations dispatched | PASS |
| C-003 | yes | Client password validation matches `_validate_password` exactly: 10–200 inclusive, all-whitespace rejected | `npm test` boundary cases 0/1/6/9/10/200/201 + `"            "` | boundaries agree with services.py:273-279 | `npm test` boundaries 0/9/10/11/200/201 + all-whitespace + code-point counting | PASS |
| C-004 | yes | Every client-distinguishable state renders with its designed copy: V1,V2,V3,V5,V6 and R1,R2,R3,R4,R6,R7 | headless check drives each state and asserts the title/body strings from handoff §8 | 11 states asserted, 0 FAIL | headless: 495 checks, 0 FAIL across 18 scenarios | PASS |
| C-005 | yes | No rendered string reveals whether an email address is registered | headless check greps all rendered state text against a banned-phrase list | 0 matches for "already registered"/"no account"/"not found"/"we've sent" | headless: 11 banned enumeration phrases asserted absent in every scenario | PASS |
| C-006 | yes | A transport failure renders R7 (server error) and NOT R4 (dead link) | `npm test` on the error-classification mapper + headless R7 state | network failure classifies as `NETWORK`, never `VALIDATION_FAILED` | `npm test` NETWORK classification; headless `reset-unreachable` renders R7 not R4 | PASS |
| C-007 | yes | The token is removed from the URL on arrival and never appears in a log or a rendered error | headless check reads `location.search` after mount and scans rendered text + console | `location.search` empty; token string absent from DOM text and console output | headless: `location.search` empty after mount; token absent from DOM text | PASS |
| C-008 | yes | Both failure states offer a fresh-link path without leaving the page | headless check asserts the email field + submit button exist in V3, V6 and R4 | present and enabled in all three | headless: email field + submit present in V3, V6, R4 and the /reset no-token state | PASS |
| C-009 | yes | The production typecheck and bundle succeed | `npm run build` (`vue-tsc -b && vite build`) | exit 0, no TS errors | `npm run build` exit 0, 198 modules, no TS errors | PASS |
| C-010 | yes | Accessibility contract from handoff §12 holds on the built pages | headless check asserts `role=status`/`aria-live` on V1/R3, `aria-busy` on the submitting form, `aria-invalid`+`aria-describedby` on errored fields, `autocomplete` values, `aria-pressed` on Show | all assertions pass | headless: role=status/aria-live, aria-busy, aria-invalid+describedby, autocomplete, aria-pressed | PASS |
| C-011 | no | The resend-verification affordance is wired to a live mutation | manual call against a running API | `accepted: true` over the wire | Contract reconciled against shipped source (`5b6c0ae`) and pinned in tests; NO live call made — no running API in this environment | BLOCKED |
| C-012 | no | End-to-end against a genuinely delivered MailHog email | Docker Compose stack + MailHog | verification and reset complete from a real email link | — | BLOCKED |
| C-013 | yes | Independent code review raises no unresolved Blocker/High finding | /code-reviewer on the diff | no unresolved Blocker or High | ClickUp comment | PENDING |

`C-011` and `C-012` are non-mandatory **for this goal only** because both require systems that do not exist in
this environment: `C-011` needs 86ak120ac merged (a declared blocking dependency, not a weakened criterion),
and `C-012` needs Docker, which is unavailable in this sandbox (`docker` is not on PATH; the Django server
answering `localhost:8008` is a different project and 404s `/graphql/account`). Both are handed to QA with the
exact steps rather than being marked PASS on weaker evidence.

## Verification plan

- Focused verification: `npm test` (Node's built-in `node:test` runner — **no new dependency**; the repo has no
  JS test framework and one must not be chosen unilaterally, so this uses only the runtime the build already
  requires).
- Broader verification: `npm run build`; `python3 implementation/marketing/scripts/auth_pages_headless.py`
  drives the **real built bundle** in headless Chrome over a local static server with SPA fallback and a
  stubbed `fetch`, mirroring `scripts/operator_headless.py`.
- Independent verifier: /code-reviewer, then /qa-engineer for the MailHog end-to-end (C-012).
- Required environment: Node 26 (`/opt/homebrew/bin/node`), headless Chrome.

## Iteration ledger

### Iteration 1

- Target criterion: C-001 … C-010 (the implementation slice)
- Hypothesis: the whole surface is one coherent increment — the two views share a card shell, an API seam and a
  validation module, so splitting them would produce throwaway scaffolding.
- Change or investigation: build the `src/lib/api` seam, the pure `src/lib/auth` modules, three shared auth
  components, the two views, the routes, the dev/nginx proxies and the referrer-policy tightening.
- Verifier executed: `npm run build`, `npm test`, `auth_pages_headless.py`
- Result: PASS on all 11 mandatory criteria
- New evidence: `npm run build` exit 0 · `npm test` 48/48 · `npm run test:states` 18 scenarios / 495 checks / 0 FAIL
- Decision: gate-review (C-013 independent review outstanding; C-011/C-012 blocked on 86ak120ac and Docker)

### Iteration 2

- Target criterion: C-011 (assumption closure) — reconcile the resend wiring against the shipped mutation.
- Hypothesis: 86ak120ac landed while iteration 1 was in flight, so the assumed field name needs verifying at
  source rather than trusting the handoff summary.
- Change or investigation: read `account_schema.py:179-196`, `ResendVerificationPayload`,
  `resend_email_verification` and `enforce_budget` directly. Found the assumed name WRONG
  (`resendVerification` vs the real `resendVerificationEmail`). Corrected the constant, replaced the stale
  "not yet available" doc comment, added distinct non-enumerating `RATE_LIMITED` copy, and added 4 unit tests
  plus a whole `verify-rate-limited` scenario pinning the field name, selection set and rate-limit wording.
- Verifier executed: `npm run build`, `npm test`, `npm run test:states`
- Result: PASS — build exit 0; 48/48 unit tests; 18 scenarios / 495 checks / 0 FAIL.
- New evidence: the wrong field name would have failed as `VALIDATION_FAILED` — the same code a dead link
  produces — so it would have presented as "resend is broken" with nothing pointing at the cause. It is now
  pinned in two places.
- Decision: gate-review (C-011 still BLOCKED on a live call; C-012 and C-013 unchanged)

## Risks and rollback

- Risks: (a) the assumed `resendVerification` field name is wrong — contained to one constant; (b) CSRF/CORS
  are unresolved, so the pages cannot be proven against a live API from this environment; (c) the merged V3/R4
  failure copy will need revisiting if 86ak120fz decides to expose `EXPIRED` — the designed V4/R5 frames
  already exist for that outcome.
- Rollback: the change is additive — two new routes, one new `src/lib` tree, three new components. Reverting the
  commit restores the previous behaviour exactly (a 404, i.e. today's bug).

## Pause and escalation conditions

- If implementing any state would require claiming knowledge the API does not return (expired vs invalid),
  stop and keep the merged state — owner: product + /security-reviewer via 86ak120fz.
- If a design string would leak account existence, stop and escalate to /ui-ux-designer rather than paraphrase.
- If the work would require editing `implementation/api/` or `implementation/mobile/`, stop and hand back —
  Kenji and Mika hold those trees concurrently.

## Final evaluation

- Validator command: `python3 scripts/validate_goal_contract.py docs/delivery/goals/TASK-auth-token-landing-pages.md`
- Validator result: PASS (13 criteria, 11 mandatory)
- Independent verification result: OUTSTANDING — /code-reviewer (C-013), then /qa-engineer for the MailHog end-to-end (C-012)
- Terminal state: GATE_REVIEW
- Remaining failed or blocked criteria: C-011 (resend wired to a live mutation) BLOCKED — the mutation now EXISTS (86ak120ac, `5b6c0ae`) and the client is corrected against its real signature, but no call has been made against a running API, so V5 is structurally wired and contract-verified, NOT proven end to end; C-012 (MailHog end-to-end) BLOCKED — no Docker in this environment; C-013 (independent review) PENDING
- ClickUp final evidence comment: posted on 86ak10b1t
