# Goal Contract — GOAL-be-86ak5t1gw-native-account-surface

## Identity

- Goal ID: GOAL-be-86ak5t1gw-native-account-surface
- Parent goal ID: 86ajy5v6k (EPIC — Platform API / Licensing & Entitlements)
- Title: A native desktop client can sign in and activate a device against the Platform API without weakening browser CSRF protection on `/graphql/account`
- Role: backend-engineer
- Status: IN_REVIEW
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86ak5t1gw
- Created: 2026-10-02
- Updated: 2026-10-02
- Maximum iterations: 8
- Independent verification required: yes

## Objective

Give the desktop client a CSRF-exempt, cookie-free, bearer-only route pair under `/v1` for the two operations of the primary activation path (DEC-011 pt 3): credential exchange (`POST /v1/sessions`) and session-authenticated activation (`POST /v1/activations:with-session`). `/graphql/account` keeps `CsrfViewMiddleware` enforced and is not exempted. The exemption is sound because neither new route can authenticate from, or set, an ambient browser credential.

## Baseline

Verified this session (2026-10-02, `origin/main` = 66e514ee):

- `implementation/api` suite on SQLite: **554 passed, 3 skipped** (`python -m pytest tests -q`, Python 3.14 venv, `pip install -e ".[dev]"`).
- `CsrfViewMiddleware` is enabled (`settings.py:90`); `AccountGraphQLView` is not exempt (`graphql/views.py:67-68`).
- `_read_account_session_token` (`graphql/context.py:94-101`) authenticates the account surface from `Authorization: Bearer` **or the `selahcue_account_session` cookie** — the cookie is an ambient credential, so a route-level exemption of `/graphql/account` is unsafe.
- `login` and `refreshSession` set that cookie (`graphql/account_schema.py:131-144`) — login-CSRF is real on the browser surface.
- Only `/v1/*` and `/webhooks/billing/*` are `csrf_exempt`; none authenticates from a cookie.
- Django 6.1.1 `CsrfViewMiddleware.process_view` (`django/middleware/csrf.py:437-446`): over HTTPS with no `Origin` header it rejects a missing `Referer` — a native client sends neither, so option (b) (cookie + header double-submit) would also need forged `Origin`/`Referer` headers.
- The desktop `HttpTransport` carries only a bearer (`selahcue-cloud/src/transport.rs:29-40`); `ReqwestTransport` has no cookie jar.

## Inputs and evidence sources

- ClickUp 86ak5t1gw (description, owner comment of 2026-08-25), 86ak5mn11 (blocked desktop licensing client).
- `docs/decisions/DECISION-LOG.md` DEC-004, DEC-005, DEC-007, DEC-011 pt 3, DEC-013; ADR-0023.
- `implementation/api/selahcue_api/{graphql/views.py,graphql/context.py,graphql/account_schema.py,platform/views.py,platform/urls.py,apps/accounts/services.py,apps/devices/services.py,apps/throttling/*}`.
- `implementation/desktop/crates/selahcue-licensing` (client + contract) for the wire the desktop speaks today.

## Scope

### In scope

- `POST /v1/sessions` (credential exchange) and `POST /v1/activations:with-session` (session-authenticated activation), `csrf_exempt`, bearer-only, no `Set-Cookie`, per-IP throttled, JSON-only.
- Audit `source_surface` for both new routes is `desktop_v1` (optional keyword on the two existing services; defaults unchanged).
- Tests: failing-first, mutation-checked, including a real-socket live-server test with a cookie-less client.
- ADR-0027 recording the decision and why it is safe for login specifically; API README, account-auth handoff doc and `deployments.md` throttling note updated.
- Linked follow-up ticket for the desktop client to move to the new routes.

### Non-goals

- Changing `/graphql/account` or `/graphql/admin` (stay CSRF-enforced, unchanged).
- Any change under `implementation/desktop` (a different owner; follow-up ticket).
- Native session refresh/revoke routes, a scoped activation-only grant token, per-IP app-level throttling of the browser surface (all tracked as follow-ups, not required to unblock activation).
- The Docker Compose / `api/.env` integration path (the live-server test in the suite is the repeatable integration evidence that does not depend on it).

### Constraints

- Python imports at module top; no function-local imports unless breaking a cycle.
- Keep `settings.py`, `urls` hunks minimal; do not touch password-reset code in `accounts/services.py` (concurrent ticket 86ak65mj5).
- No secrets in logs, payloads or audit rows.

### Assumptions and unknowns

- ASSUMED: the owner's comment on the ticket (route desktop session operations onto `/v1`, do not exempt or imitate the browser surface) is the product-owner direction; the exact wire shape (REST rather than a second GraphQL mount) is an API-side decision recorded in ADR-0027 for owner confirmation.
- UNKNOWN: whether the production edge applies a per-IP rate rule to `/graphql/account` only; mitigated by an app-level per-IP throttle on both new routes and a `deployments.md` note.
- UNKNOWN: Postgres-run results (CI runs Postgres + Redis; this environment runs SQLite + LocMem).

## Dependencies and approvals

- Desktop migration to the new routes: follow-up ticket (desktop owner). 86ak5mn11 must re-verify "both activation paths" after that lands.
- Review gate (Cody, Vera, Shadow, Quinn) is brokered by the parent agent, not run here.

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | AC1: a decision with rationale exists, incl. why the choice is safe for login specifically | read `docs/architecture/adr/ADR-0027-native-client-account-surface.md` | names options (a)/(b)/(c), chosen route, login-CSRF analysis, abuse story | ADR-0027 (Options considered, Decision, Why the exemption is sound) + ClickUp comments 1400430000051492 and 1400430000051493 | PASS |
| C-002 | yes | AC2: a cookie-less, token-less client over a real socket completes login then activation, and the minted device token then works | `pytest tests/test_native_account_surface.py -k live_server` + a `manage.py runserver` smoke with a cookie-less urllib client | exits 0; 200/200/200 | live-server test passes; runserver smoke: sessions 200 no Set-Cookie, activation 200, license:refresh 200 | PASS |
| C-003 | yes | AC3: browser CSRF on `/graphql/account` intact (existing pins pass unchanged; cookie-authenticated browser path still 403; exempt-route set is pinned) | `pytest tests/test_foundation_contract.py tests/test_native_account_surface.py` | exits 0 | full suite 587 passed, 3 skipped; mutation M4 (exempt `AccountGraphQLView`) turns 5 tests RED incl. the existing `test_a_browser_can_obtain_a_csrf_token_and_post_an_account_mutation` | PASS |
| C-004 | yes | AC4: new routes carry per-IP throttle, inherit per-account lockout and the no-oracle collapse | `pytest tests/test_native_account_surface.py -k "throttle or lockout or indistinguishable or policy_denied"` | exits 0 | tests pass; mutations M5a-M5d RED | PASS |
| C-005 | yes | Neither new route can authenticate from or set an ambient cookie | `pytest tests/test_native_account_surface.py -k "cookie or dev_actor or cors"` | exits 0 | tests pass; mutations M2a, M2b, M3, M7, M12 RED | PASS |
| C-006 | yes | Each new test is RED when its fix is reverted (mutation check) | revert each guarded line, run the matching test | test fails for the stated reason, restored => passes | 18 mutations, every one RED on its intended test(s); working tree restored clean after each | PASS |
| C-007 | yes | Full API suite and Django checks green | `manage.py check`, `makemigrations --check --noinput`, `pytest tests -q` | all exit 0, no new skips | `check`: no issues; migrations: no changes; pytest: 587 passed, 3 skipped (baseline 554 passed, 3 skipped) | PASS |
| C-008 | yes | AC5 handed off: follow-up desktop ticket created and 86ak5mn11 told what to re-verify | ClickUp read-back | ticket id recorded | follow-up 17tnw2b1we2 (desktop, linked to 86ak5t1gw and 86ak5mn11); hardening follow-up 17tnw2b1wf2 | PASS |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused verification: the new test module, then the foundation/device/customer-auth slices.
- Broader regression verification: full `pytest tests -q` on SQLite; `manage.py check`; `makemigrations --check --noinput`.
- Independent verifier: Cody, Vera, Shadow, Quinn via the parent's review gate.
- Required environment: Python 3.14 venv inside the worktree, SQLite + LocMemCache (Postgres/Redis not available locally).

## Iteration ledger

### Iteration 1

- Target criterion: all (design + failing tests first)
- Hypothesis: a bearer-only `/v1` route pair removes the CSRF dependence without touching the browser surface.
- Change or investigation: read-only tracing of the account surface auth, the CSRF middleware and the desktop transport.
- Verifier executed: baseline suite.
- Result: 554 passed, 3 skipped.
- New evidence: cookie is an ambient credential on the account route; Django demands Referer/Origin on HTTPS.
- Decision: iterate

## Risks and rollback

- Risks: a new unauthenticated credential-check endpoint (mitigated: per-IP throttle, inherited per-account lockout, no cookie, JSON-only); the desktop is still broken until it adopts the new routes (follow-up); audit `source_surface` keyword touches `accounts/services.py` `login` (localized).
- Rollback or recovery: revert the PR; no migration, no data change, `/graphql/*` untouched.

## Pause and escalation conditions

- Owner rejects the REST-under-`/v1` shape in favour of a GraphQL mount: stop and re-plan (API side + product owner).
- A trivial merge conflict in `accounts/services.py` is resolved; anything else stops and is reported.

## Final evaluation

- Validator command: `python3 ~/.claude/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/GOAL-be-86ak5t1gw-native-account-surface.md`
- Validator result: structural and completion runs OK (see the PR)
- Independent verification result: PENDING (Cody, Vera, Shadow, Quinn - brokered by the parent agent)
- Terminal state: GATE_REVIEW (implementation criteria PASS; independent review outstanding; the ticket stays in progress)
- Remaining failed or blocked criteria: none; the AC5 re-verification of 86ak5mn11 waits on the desktop follow-up 17tnw2b1we2 by design
- ClickUp final evidence comment: posted on 86ak5t1gw
