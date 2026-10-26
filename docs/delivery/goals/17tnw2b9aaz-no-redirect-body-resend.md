# Goal Contract - 17tnw2b9aaz-no-redirect-body-resend

## Identity

- Goal ID: 17tnw2b9aaz-no-redirect-body-resend
- Parent goal ID: NONE
- Title: The desktop HTTP transport never follows a redirect, so a 307/308 can no longer replay the account password, the enrollment key or the sermon transcript to another host
- Role: backend-engineer
- Status: GATE_REVIEW
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/17tnw2b9aaz
- Created: 2026-10-26
- Updated: 2026-10-26
- Maximum iterations: 6
- Independent verification required: yes

## Objective

Make the production `ReqwestTransport` (`selahcue-cloud`, feature `http`) build its client with `reqwest::redirect::Policy::none()`, so that a 3xx is returned to the caller as a status and the `Location` it names is never requested. Decide per consumer whether a redirect is ever legitimate, record the decision, and pin it with tests that fail when redirects are followed.

## Baseline

**Verified** on `origin/main` at `93bf8063` (2026-10-26), by reading the code and by running the new tests against it (they fail, see iteration 1):

- `ReqwestTransport::configured_builder` sets two timeouts and nothing else, so reqwest's default policy applies: up to ten redirects are followed. On a 307 or 308 reqwest replays the request body to the new location, and it also sends a `Referer` naming the URL it came from. It strips `Authorization` and cookies on a host or port change; it does not strip the body.
- Measured on the baseline with the new loopback tests: a POST answered with a 301, 302, 303, 307 or 308 reaches the redirect target (301 shown first: `GET /landed` with `referer: http://127.0.0.1:<origin port>/v1/sessions`); a hosted-notes `generate` against a server that answers 307 delivers the whole JSON request body, including the transcript, to the target.
- Construction sites of `ReqwestTransport` (grep over `implementation/` and `docs/`): three in `selahcue-operator/src/main.rs` (hosted notes under `cloud-live`, and two direct-OpenAI sites under `openai-notes`), the `selahcue-cloud` tests, the TLS unit tests, and the live harness under `docs/delivery/goals/17tnw2b1we2-evidence/`. `selahcue-licensing` takes an injected `HttpTransport` and has no production construction site yet. `selahcue-stt-cloud` has no dependency on `selahcue-cloud` and does not use this transport.
- Existing tests: `tests/test_redirect_limit.rs` characterised "ten followed, eleven an error" and said its expectations would change deliberately when this ticket landed; `tests/test_redirect_credentials.rs` pinned only the bearer.
- The licensing client already maps any non-2xx, non-5xx, non-429 status to `ActivationFailure::UnexpectedStatus(n)` (fixed wording, no body); `tests/test_client.rs` already pins 300, 302 and 399. The hosted notes client maps it to `NoteError::Malformed("unexpected status n" + allowlisted reason)`; the OpenAI mapper to `Malformed("unexpected provider status n")`.

## Inputs and evidence sources

- ClickUp 17tnw2b9aaz (description), discovered in 17tnw2b1we2 (native sign-in)
- `selahcue-cloud/src/transport.rs`, `client.rs`, `openai.rs`; `selahcue-licensing/src/client.rs`, `error.rs`
- `implementation/api/selahcue_api/platform/urls.py` (the hosted routes are fixed paths with no trailing-slash redirect)
- PR #230 (86akbzxjg): status handling and no-echo rules in the cloud clients, kept as they are

## Scope

### In scope

- `implementation/desktop/crates/selahcue-cloud/src/transport.rs` (the redirect policy and its documentation)
- `selahcue-cloud/tests/test_redirect_credentials.rs`, `tests/test_redirect_limit.rs` (rewritten for the new policy), a stale sentence in `tests/test_wire.rs`
- `selahcue-licensing/src/client.rs` (one stale doc comment) and `tests/test_client.rs` (307 and 308 added to the status list)
- `implementation/desktop/CLAUDE.md` (one bullet), this contract

### Non-goals

- A switch, flag or second constructor that follows redirects: no consumer needs it, and an unused insecure option is a regression waiting for a caller
- The URL that `reqwest` puts in a send-error message ("error sending request for url (...)"): unchanged; the URLs built here carry no query
- Rejecting an `http://` base URL (the licensing client documents that the wiring must require `https://`; that check belongs to the not-yet-written sign-in wiring)
- Cloud transcription (Deepgram) and the scripture downloader (`ureq`, its own HTTPS-only redirect rule): not this transport
- Any change to `selahcue-operator` or `selahcue-desktop` source

### Constraints

- One ticket, one branch, one Draft PR off `origin/main`; not marked ready or merged by this role; no `Co-Authored-By` trailer
- No manifest or lock change (no `cargo deny` needed)
- No body, URL query, header or credential text in any error or log
- Source ASCII-only

### Assumptions and unknowns

- **Verified**: the behaviour on the loopback transport, on macOS arm64, Rust 1.98.0, reqwest 0.13.
- **Inferred**: the hosted API (not live yet) and `api.openai.com` answer at the URL they are given. The routes in `implementation/api` have no trailing slash and the API settings contain no `SECURE_SSL_REDIRECT` or `APPEND_SLASH` override; a deployment behind a proxy that redirects http to https would now surface as `UnexpectedStatus(301)`/`Malformed("unexpected status 301")` instead of a silent follow, which is the intended failure (the base URL must be https).
- **Unknown**: whether any future production edge intends to answer the API with a redirect. If it does, the answer is to fix the base URL, not to follow the redirect.
- **Not run**: `selahcue-operator` build, tests and clippy; one `make ci`; Windows and the ubuntu CI runner. Held for the coordinator (see the PR body).

## Dependencies and approvals

- None. Reviewers (Cody, Shadow, Quinn, Vera) are dispatched by the coordinator after the Draft PR is open.

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`. This contract stops at `GATE_REVIEW`: C-010 (independent review) and C-011 (held gates) are not run by this role.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | The new tests fail on the unfixed transport for the stated reason (the redirect is followed and the body reaches the target) | the two redirect test files run on `93bf8063` plus the new tests | exit 101; 4 of the 7 tests red with "the redirect was followed and the request reached another host" and "left: 200 right: 302" | iteration 1 | PASS |
| C-002 | yes | A redirect (301, 302, 303, 307, 308) to another host:port, on a POST carrying a credential body and bearer and on a GET carrying a bearer, returns the redirect status and the target is never contacted; positive controls: the origin received the body and bearer, and the same recorder does capture a body when hit directly | `cargo test -p selahcue-cloud --features http --test test_redirect_credentials` | exit 0; 4 tests | iteration 2 | PASS |
| C-003 | yes | A same-host redirect chain of 1, 10 and 11 is answered by its first hop and the second hop is never requested; positive control: the last hop answers when asked directly | `cargo test -p selahcue-cloud --features http --test test_redirect_limit` | exit 0; 3 tests | iteration 2 | PASS |
| C-004 | yes | The hosted notes client over the real transport reports a 307 as exactly `Malformed("unexpected status 307")`; the transcript, bearer, a token in the `Location` query, the redirect body and the host never appear in the error; the target is never contacted | `a_redirect_through_the_hosted_notes_client_is_an_unexpected_status_that_quotes_nothing` | exit 0 | iteration 2 | PASS |
| C-005 | yes | The licensing client classifies 307 and 308 as `UnexpectedStatus` like 302 | `cargo test -p selahcue-licensing --test test_client` (`the_success_range_is_exactly_200_to_299`) | exit 0 | iteration 2 | PASS |
| C-006 | yes | Every new redirect test fails when the policy is altered: default policy, `limited(1)`, follow-same-host-only, follow-307/308-only | driver script in the scratchpad (`w2-17tnw2b9aaz-mutate.py`): each mutation runs both redirect files with `test_wire` (siblings, not `--exact`), then restores `transport.rs` and checks it with `cmp` | each mutation exit 101 with the named tests red; restored byte-identical | iteration 3 | PASS |
| C-007 | yes | TLS provider, TLS trust, proxy, wire-format and bearer-stripping tests are unchanged and green | `cargo test -p selahcue-cloud --features http` under `NO_PROXY=127.0.0.1,localhost` | exit 0; 72 passed, 0 failed, 1 ignored (the by-hand live TLS probe) | iteration 4 | PASS |
| C-008 | yes | The per-consumer decision (hosted licensing, hosted notes, direct OpenAI, cloud STT) is recorded where the next reader will look | `transport.rs` "Redirect posture", `implementation/desktop/CLAUDE.md`, the PR description | present in all three | iteration 2 | PASS |
| C-009 | yes | fmt, clippy (`-D warnings`) workspace and `selahcue-cloud` on default, `http`, `openai`; tests for `selahcue-cloud` on default, `http`, `openai` and the workspace; import guards; launch reachability | the commands in the PR description | all exit 0 (workspace tests: 1,899 passed, 0 failed, 5 ignored) | iteration 4 | PASS |
| C-010 | yes | Independent review passed (code, security, QA, performance) at the head SHA | review report page | verdicts recorded, zero open blocking findings | held for the coordinator | PENDING |
| C-011 | no | `selahcue-operator` compile-check, clippy and tests, and one `make ci` | `make ci` and the operator commands in the PR description | exit 0 | held for the coordinator | PENDING |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused verification: C-001 to C-006 from the worktree, each integration test file run alone and with siblings (never `--exact`), every gate captured to a file and its exit code read (no piped gate)
- Broader regression verification: C-007 and C-009
- Independent verifier: Cody, Shadow, Quinn and Vera, dispatched by the coordinator
- Required environment: macOS arm64 host, Rust 1.98.0 (pinned), the workspace target cloned copy-on-write from a baseline worktree

## Iteration ledger

### Iteration 1

- Target criterion: C-001
- Hypothesis: reqwest's default policy replays a 307/308 body to the redirect target, and the existing suite pins nothing that says otherwise
- Change or investigation: rewrote `test_redirect_limit.rs` and `test_redirect_credentials.rs` for the new policy (a recorder server that captures the whole request, a same-host chain counter, a hosted-notes end-to-end), and ran them on the unfixed transport
- Verifier executed: `cargo test -p selahcue-cloud --features http --test test_redirect_credentials --test test_redirect_limit`
- Result: exit 101, 4 red and 3 green. The red ones: the status-sweep test (first failing status 301: `GET /landed ... referer: http://127.0.0.1:<port>/v1/sessions`), the notes end-to-end (`POST /landed?token=... content-length: 355 ... {"transcript":"REDIRECT-PROBE-TRANSCRIPT-a41e ...`), and both chain tests (`left: 200 right: 302`). The green ones are the positive controls and the old bearer test
- New evidence: the replayed request also carries a `Referer` with the origin URL, and a `Location` query is followed verbatim
- Decision: iterate

### Iteration 2

- Target criterion: C-002 to C-005, C-008
- Hypothesis: one `.redirect(Policy::none())` on the shared builder satisfies every consumer, because none depends on a redirect
- Change or investigation: added the policy to `configured_builder` (so the TLS-test builders carry it too); documented the posture and the per-consumer decision in `transport.rs` and `CLAUDE.md`; added 307 and 308 to the licensing status list; fixed two stale comments
- Verifier executed: the two redirect test files; the licensing client test
- Result: green (4 and 3 tests)
- New evidence: none new
- Decision: iterate

### Iteration 3

- Target criterion: C-006
- Hypothesis: the tests catch any policy that follows a redirect, including partial ones
- Change or investigation: mutation driver with four policies (default, `limited(1)`, same-host-only, 307/308-only), each run with the redirect files and `test_wire`
- Verifier executed: `w2-17tnw2b9aaz-mutate.py`
- Result: all four red, restored byte-identical (`cmp`). Default and `limited(1)` redden four tests (both files); same-host-only reddens only the two chain tests (the cross-port credential tests correctly stay green: a cross-port redirect is still refused); 307/308-only reddens only the credential tests (the chain uses 302)
- New evidence: the two files are complementary; neither alone catches all four mutations
- Decision: iterate

### Iteration 4

- Target criterion: C-007, C-009
- Hypothesis: nothing outside the redirect behaviour moved
- Change or investigation: full gate set, results in the PR description
- Verifier executed: the gate script
- Result: every gate exit 0: fmt; clippy workspace and `selahcue-cloud` on default, `http`, `openai`; `selahcue-cloud` tests default (47), `http` (72, 1 ignored), `openai` (96); `cargo test --workspace` (1,899 passed, 0 failed, 5 ignored); import guards; launch reachability. The free-space guard (13 GiB) tripped after the workspace test run; the last two gates run no compiler (`cargo tree`/`cargo metadata` only) and were run by hand after the guard tripped
- New evidence: none
- Decision: gate-review

## Risks and rollback

- Risks: a consumer that silently relied on a redirect would now see an error. None was found (see Baseline), and the failure is loud and specific (`unexpected status 301`). The Referer a followed redirect used to send is gone as a side effect, which is the intended direction.
- Rollback or recovery: delete the one `.redirect(..)` line in `configured_builder`; the tests would then fail, which is the point.

## Pause and escalation conditions

- A reviewer finds a consumer that legitimately needs a redirect: stop and return it to the owner; the answer would be a per-call decision, not a transport default
- A gate fails for a reason outside this change: report it, do not mask it

## Final evaluation

- Validator command: `python3 scripts/validate_goal_contract.py docs/delivery/goals/17tnw2b9aaz-no-redirect-body-resend.md`
- Validator result: recorded in the PR description
- Independent verification result: pending (coordinator)
- Terminal state: GATE_REVIEW
- Remaining failed or blocked criteria: C-010 and C-011 held for the coordinator
- ClickUp final evidence comment: written by the coordinator
