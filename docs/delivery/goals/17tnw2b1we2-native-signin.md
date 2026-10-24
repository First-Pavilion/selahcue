# Goal Contract — 17tnw2b1we2-native-signin

## Identity

- Goal ID: 17tnw2b1we2-native-signin
- Parent goal ID: NONE
- Title: The desktop licensing client signs in and activates over the native `/v1` routes, so the primary activation path works against a running server
- Role: backend-engineer
- Status: ACTIVE
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/17tnw2b1we2
- Created: 2026-10-24
- Updated: 2026-10-24
- Maximum iterations: 8
- Independent verification required: yes

## Objective

`selahcue-licensing` performs account sign-in with `POST /v1/sessions` and session activation with `POST /v1/activations:with-session` (Bearer), parses the server's real response shapes, never calls `/graphql/account`, sends no cookie or CSRF header, surfaces a MEMBER account, a wrong password and an account with no active licence as their own typed failures, and can never put a response body (HTML 403 page included) in a user-visible or logged string. Proven against a running API, not only fixtures.

## Baseline

**Verified** on origin/main `f176db35`:

- `contract.rs` defines `ACCOUNT_GRAPHQL_PATH = "/graphql/account"`, two GraphQL operation strings and the GraphQL wire types; `client.rs::graphql()` posts them to that route.
- The server half is merged (PR #151, `68d5f3a2`): `/v1/sessions` and `/v1/activations:with-session` exist in `implementation/api/selahcue_api/platform/urls.py`, contract in `docs/design/ACCOUNT-AUTH-API-HANDOFF.md` section "Native client routes" and ADR-0029.
- Against a running API from this tree, `POST /graphql/account` from a cookie-less client returns HTTP 403 with an HTML body (reproduced as the control in C-009).
- No other workspace crate depends on `selahcue-licensing` (checked: only its own manifest and the workspace member list name it; the operator mentions it in one comment).
- `selahcue-cloud`'s production transport already sets `content-type: application/json`, carries a bearer and nothing else (no cookie jar, no header map), and reads at most `MAX_TRANSPORT_RESPONSE_BYTES` (4 MiB).

## Inputs and evidence sources

- ClickUp 17tnw2b1we2 (description, comments); linked 86ak5t1gw (server), 86ak5mn11 (original client)
- `docs/design/ACCOUNT-AUTH-API-HANDOFF.md`, "Native client routes"
- `docs/architecture/adr/ADR-0029-native-client-account-surface.md`
- `implementation/api/selahcue_api/platform/views.py` (`create_session`, `activate_device_with_session`, `_activation_payload`) and `platform/responses.py` (error envelope and status map)
- `implementation/desktop/crates/selahcue-cloud/src/transport.rs` (transport seam and read cap)

## Scope

### In scope

- `selahcue-licensing`: `contract.rs`, `client.rs`, `error.rs`, `lib.rs` docs and the tests under `tests/`
- Typed sign-in failures (`InvalidCredentials`, `AccountNotActive`) so a wrong password and an unverified account are not reported as "session expired" or "plan limit"
- A parse-side response cap, a shape check on unknown error codes, and parse errors that describe position only
- `implementation/api/README.md`: remove the sentence saying the desktop does not yet call the native routes

### Non-goals

- Any API change (stop and report BLOCKED if one is needed; none was)
- Wiring sign-in into the operator UI (no workspace crate calls this client yet)
- A native revoke route or activation-only grant (ClickUp 17tnw2b1wf2)
- Redirect policy of the production `ReqwestTransport` (shared crate; recorded as a follow-up)
- Enrollment-key path behaviour (unchanged on the wire; its failure text only gets the same body-free guarantee)

### Constraints

- Credential path: no password, token or response body in logs, errors or `Debug` output
- Bounded memory for any response read
- Never work on `main`; one ticket, one branch, one Draft PR; no merge
- Stage explicit paths only; no `Co-Authored-By`

### Assumptions and unknowns

- **Verified**: the deployed API (production) has the server half, because PR #151 is merged to `main`; this contract proves the client against that code run locally. Whether the hosted environment has been redeployed since is **Unknown** and is an Otto/owner question, not testable from here.
- **Verified**: `Activation.reminted`/`token_meta`/`license` can become non-optional because both routes answer one shape.

## Dependencies and approvals

- Server routes: merged (PR #151). ADR-0029 is still "Proposed" pending the owner accepting its residual risks (30-day session the native client cannot revoke). That does not block this client change; it is recorded in the PR.
- Four-reviewer gate (Cody, Shadow, Vera, Quinn), dispatched by the orchestrator

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Sign-in is `POST /v1/sessions` with exactly `{email, password}`, no bearer, and parses the server's real body (including the unsigned `surface`/`operation` labels) | `cargo test -p selahcue-licensing --test test_client a_fresh_install_activates` and `--test test_contract a_real_sign_in_success_body_parses` | both pass | test output | PASS |
| C-002 | yes | Session activation is `POST /v1/activations:with-session` with the session as bearer, body = activation body minus `license_key` (snake_case), and returns `reminted`, token metadata and the licence block | `--test test_client a_session_activation_reports_everything` and `a_fresh_install_activates` | pass | test output | PASS |
| C-003 | yes | No code in the crate names `/graphql/account`, GraphQL, a cookie, a CSRF header, Origin or Referer; every request is a `/v1` JSON POST | `--test test_client the_source_names_no_cookie_csrf_origin_or_graphql_route` and `every_request_goes_to_a_cookie_free_v1_route` | pass; mutation M5 turns both red | test output + mutation log | PASS |
| C-004 | yes | A MEMBER (PERMISSION_DENIED), a wrong password (UNAUTHENTICATED at sign-in), an unverified account (POLICY_DENIED at sign-in) and an account with no active licence (NOT_FOUND at activation) are four distinct typed failures, none `Malformed`; the same code means the right thing on each call | `--test test_client a_member_account`, `a_wrong_password`, `an_unverified_account`, `not_found_on_the_session_path`, `the_other_sign_in_refusals` | pass; mutations M3, M7 turn them red | test output + mutation log | PASS |
| C-005 | yes | No failure's `Display` or `Debug` contains any part of a response body (HTML 403/502/200, JSON non-envelope, free-text code, wrong-typed field, truncated, empty) nor the password/session/enrollment key, on all three calls | `--test test_client no_failure_quotes_the_response_body_on_any_call`, `the_body_quoting_sweep_can_fail`, `an_unknown_code_from_a_proxy...`; `--test test_contract an_error_code_that_is_not_shaped_like_a_code` | pass; mutations M1, M4 turn them red | test output + mutation log | PASS |
| C-006 | yes | A response over `MAX_RESPONSE_BODY_BYTES` (64 KiB, below the transport's 4 MiB read cap) is refused unparsed, success or error, while one exactly at the cap is read | `--test test_client a_success_body_over_the_cap...`, `an_error_body_over_the_cap...` | pass; mutations M2, M6 turn them red | test output + mutation log | PASS |
| C-007 | yes | Credential-hygiene sweeps (formatted-types sweep, `expose()` site pin, Token-typed fields, never-blank enumeration) still pass and cover the new wire types | `cargo test -p selahcue-licensing` | all tests pass | test output | PASS |
| C-008 | yes | The enrollment-key path still works: same URL, body, no bearer; its tests pass | `--test test_client the_enrollment_key_*` and live run (C-009) | pass | test output + live log | PASS |
| C-009 | yes | Against a RUNNING API seeded with a verified admin, a MEMBER, an unverified user, a no-licence admin and one real licence key, the real `ReqwestTransport` client completes sign-in then activation, the minted token works on `/v1/license:refresh`, and the failure cases come back typed; the old route is shown returning 403 HTML | scratchpad harness `17tnw2b1we2-live-harness` run against `manage.py runserver` | output as posted on the ticket | `docs/delivery/goals/17tnw2b1we2-native-signin.md` evidence section + ClickUp comment | PASS |
| C-010 | yes | `cargo fmt --check`; `cargo clippy -D warnings` (debug and `--release`) on `selahcue-licensing`; workspace clippy and tests via one `make ci` | commands in the PR body | all exit 0 | PR body with exit codes | PASS |
| C-011 | yes | Diff has no stray non-ASCII | grep for non-ASCII bytes in the added lines of `git diff origin/main -U0` | no output | command output | PASS |
| C-012 | yes | 86ak5mn11's "both activation paths work" claim is re-verified against the live server and the result is posted on that ticket | ClickUp comment on 86ak5mn11 | comment present | ClickUp | PASS |
| C-013 | yes | Owner rule 2b: every applicable happy-path and edge case has a test that goes red when its behaviour is mutated (case list below; 19 mutations, all caught) | `python3 17tnw2b1we2-mutate.py` (scratchpad) | each mutation fails at least one named test | PR body mutation table | PASS |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Test case matrix (owner rule 2b)

Covered (tests in `crates/selahcue-licensing/tests/`):

- Success shapes: first activation with token; show-once replay (null token); re-mint; absent `activation_token` key; absent or all-null `token` metadata; MEMBER sign-in success; enrollment-key success.
- Missing, null, blank: each required activation field absent and null (`created`, `reminted`, `device`, `license`, `device_public_id`); each sign-in field absent and null; blank session token; envelope with null or no `code`.
- Boundaries: body exactly at and one past the 64 KiB cap (success and error, 4xx and 5xx); status 100/199/200/201/299/300/302/399/499/500/599/600; email 254 and password 200 characters; empty email and password; leading and trailing whitespace in a password; base URL with a trailing slash; error code at and over 64 bytes.
- Hostile or malformed bodies: Django CSRF 403 page, proxy 502 and 429 pages, captive-portal 200 HTML, WAF JSON, free-text and 4000-byte codes, wrong-typed field, truncated JSON, empty body, JSON array, null, bare string; on all three calls.
- Error codes: all six the ticket names on the right call, PERMISSION_DENIED versus POLICY_DENIED, same code meaning different things at sign-in versus activation, lower-case and padded codes, known-but-unmapped codes (CONFLICT, NOT_IMPLEMENTED), unknown code-shaped and non-code-shaped codes.
- Connection failures and timeouts: five transport reasons on all three calls (unreachable, retryable, silent); outage on the second call after a good sign-in, then a successful retry with the same session.
- Retry and repeat: retry sends a byte-identical body and the same idempotency key; replay keeps the cached token; replay with nothing cached is reported; a refused re-activation leaves the cached token alone.
- Credentials and logging: the right secret in the right place (bearer is the session token, password only in the sign-in body, nothing in a URL); no password, session token, device token, enrollment key or body text in any failure `Display`/`Debug` (sweep over 15 hostile replies x 3 calls); success-path `Debug` of the session, activation and transport; the existing formatted-types sweep, `expose()` site pin and Token-typed-field scan updated for the new wire types.
- Structure: no `graphql`, cookie, CSRF, Origin or Referer in the crate source; every request is a `/v1` POST.
- Live: the real `ReqwestTransport` client against a running server (C-009).

Deliberately not covered:

- Server-side bounds, lockout, throttle and tenant isolation: owned and tested by the API (`test_native_account_surface.py`); the client only relays the typed result.
- Concurrency between calls: `LicensingClient` is stateless and holds no lock or cache; there is nothing to race. Concurrent keychain writes belong to `custody`, unchanged here.
- A blank `activation_token` string: the key-path behaviour is unchanged and `is_activated` already treats an empty stored token as not activated; changing it would alter the enrollment path.
- Real timeouts and the 4 MiB socket read cap: owned by `selahcue-cloud` (`test_transport.rs`); here the transport is injected and reports them as errors, which is what is tested.
- Redirect handling: a shared-transport behaviour, measured and filed as 17tnw2b9aaz.

## Live-run evidence (C-009)

Real client (`selahcue-licensing` over the production `ReqwestTransport`) against `manage.py runserver` on origin/main `f176db35`, throwaway SQLite seeded with a verified ADMIN, a MEMBER, an unverified user, a verified ADMIN with no licence key and one real licence key. Harness lives outside the repo (scratchpad); it prints outcomes only, never a token, password or body.

```
[control] POST /graphql/account (old route) -> HTTP 403 ; html_body=true
[admin] sign_in OK: role=ADMIN org_id=1 expires_at=2026-11-23T05:15:13.474911+00:00 session_token_len=50
[admin] activate_with_session OK: path=AccountSession created=true reminted=false device=dev_f3ac31bc382adedebcd6a30e87d695c7 platform=macos token_issued=true token_prefix=Some(<masked>) license_status=ACTIVATED license_expires=2026-11-23T05:14:11+00:00
[admin] persist -> Stored; device token held in store: true
[admin] minted device token against POST /v1/license:refresh -> HTTP 200
[admin] replay: created=false reminted=false token_issued=false disposition=KeepExisting persist=KeptExisting
[wrong password] -> InvalidCredentials | permits_presentation=true retryable=false | "that email and password were not accepted (or the account is temporarily locked after too many attempts)"
[unknown email] -> InvalidCredentials | permits_presentation=true retryable=false | "that email and password were not accepted (or the account is temporarily locked after too many attempts)"
[unverified account] -> AccountNotActive | permits_presentation=true retryable=false | "this account cannot sign in yet: its email address is not verified, or the account has been disabled"
[member] sign_in OK: role=MEMBER
[MEMBER activation] -> PermissionDenied | permits_presentation=true retryable=false | "this account does not have permission to activate a device"
[no-licence admin] sign_in OK: role=ADMIN
[no active licence] -> NoActiveLicense | permits_presentation=true retryable=false | "this account has no active SelahCue plan; renew it to activate a device"
[bad session token] -> Unauthenticated | permits_presentation=true retryable=false | "the account session is not valid; sign in again"
[enrollment key] OK: path=EnrollmentKey created=true reminted=false device=dev_dba6ddc483233652a00ad843df73ad61 token_issued=true license_status=ACTIVATED
[enrollment key (wrong key)] -> UnknownKey | permits_presentation=true retryable=false | "that enrollment key was not recognised"
```

Server log for the run: `POST /v1/sessions` 200/401/401/403/200/200, `POST /v1/activations:with-session` 200/200/403/404/401, `POST /v1/license:refresh` 200, `POST /v1/activations` 200/404; the only 403 HTML responses are the two deliberate probes of the old `/graphql/account` route.

## Verification plan

- Focused verification: `cargo test -p selahcue-licensing`, plus eight mutation runs (revert one control, confirm RED, restore)
- Broader regression verification: one `make ci` at the end
- Independent verifier: Cody, Shadow, Vera, Quinn via the orchestrator
- Required environment: Python 3.14 venv with the API's pinned dependencies, a throwaway SQLite database, `manage.py runserver 127.0.0.1:8765`

## Iteration ledger

### Iteration 1

- Target criterion: C-001 to C-008
- Hypothesis: moving the three calls onto REST fixtures shaped from `views.py` turns the old GraphQL client red for the right reason (it tries to parse a REST body as GraphQL), and a small contract/client rewrite turns it green
- Change or investigation: rewrote the primary-path tests first (8 red, all "GraphQL response carried neither data nor errors"), then replaced the GraphQL types and `graphql()` with `post`/`decode`, added typed sign-in failures, the body-free parse errors, the code shape check and the 64 KiB cap
- Verifier executed: `cargo test -p selahcue-licensing --no-fail-fast`
- Result: all green; 8 of 8 mutations turned the intended tests red
- New evidence: see mutation log in the PR
- Decision: iterate

### Iteration 2

- Target criterion: C-009, C-012
- Hypothesis: the real `ReqwestTransport` client works against the merged server routes
- Change or investigation: built a throwaway harness outside the repo that runs the real client against a locally running API (migrated, seeded SQLite)
- Verifier executed: harness run
- Result: sign-in, activation, replay, token use, and all failure cases behaved as the contract says
- New evidence: live-run output (below)
- Decision: gate-review

## Risks and rollback

- Risks: no workspace crate calls the client yet, so nothing user-visible changes until the sign-in screen lands; `Activation` field types changed (non-optional), safe because nothing else depends on the crate; the production `ReqwestTransport` follows redirects (shared crate, not changed here).
- Rollback or recovery: revert the single PR; the server routes are additive and unaffected.

## Pause and escalation conditions

- If a server change is needed: stop, report BLOCKED (owner: backend-engineer, API). None needed.
- If `make ci` shows a failure unrelated to this diff: report with evidence, do not widen scope.

## Final evaluation

- Validator command: `python3 ~/.claude/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/17tnw2b1we2-native-signin.md`
- Validator result: structural and `--completion` both OK (see PR)
- Independent verification result: PENDING (Cody, Shadow, Vera, Quinn are dispatched by the orchestrator; this author does not self-certify)
- Terminal state: implementation VERIFIED_COMPLETE; awaiting independent review
- Remaining failed or blocked criteria: none known
- ClickUp final evidence comment: posted on 17tnw2b1we2 (live run) and 86ak5mn11 (re-verification)
