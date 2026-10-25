# Goal Contract — 86akbzxjg-cloud-client-error-bodies

## Identity

- Goal ID: 86akbzxjg-cloud-client-error-bodies
- Parent goal ID: NONE
- Title: The SelahCue cloud client never puts any part of a provider response body into an error, and tells a terminal out-of-credit 429 from a transient rate-limit 429
- Role: backend-engineer
- Status: ACTIVE
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86akbzxjg
- Created: 2026-10-25
- Updated: 2026-10-25 (review round 1 fixes)
- Maximum iterations: 6
- Independent verification required: yes

## Objective

`SelahCueCloudClient` (`implementation/desktop/crates/selahcue-cloud/src/client.rs`) builds every `NoteError` message from text of its own plus a small allowlist of fields parsed out of the response (a reason code taken from a closed list, matched exactly and case-sensitively), never from response text. The parse is bounded: a body over 32 KiB is not parsed at all. Both `generate_with_quota` and `fetch_quota` use that one path, for non-2xx statuses and for 2xx bodies that fail to parse. A 429 whose payload says `insufficient_quota` or `credit_balance_exhausted`, and any 402, is `QuotaExceeded` and propagates with no fallback. Any other 429 is `Transport`, so `generate_sermon_notes` serves the degraded local draft. The discrimination is defined once, in an always-compiled module that the OpenAI mapper in `src/openai.rs` also calls, so there is no second copy.

## Baseline

Verified on origin/main ed561471 (2026-10-25):

- `client.rs:75` maps `402 | 429` to `QuotaExceeded`; `client.rs:79-82` maps any other non-2xx to `Malformed("unexpected status N: <first 200 bytes of the body>")`. `status_error` is called from `generate_with_quota` and `fetch_quota`.
- `client.rs:108` and `:155` build `Malformed(e.to_string())` from a typed `serde_json` error. For a type mismatch serde_json's text includes the offending value (for example `invalid type: string "sk-proj-...", expected u32`), so a 2xx body is a third raw-body path.
- `src/openai.rs:907-949` (`map_error_status`, `error_code`) already discriminates terminal exhaustion (`insufficient_quota`, `credit_balance_exhausted`) from a rate-limit 429, but sits behind the `openai` feature, so the default-build client cannot call it.
- `tests/test_openai.rs` holds the verbatim live captures of 2026-09-04 (`ERR_401_INVALID_KEY` carries `sk-proj-********************-key`). It is `#![cfg(feature = "openai")]`.
- `generate_sermon_notes` (`lib.rs:99-138`) falls back locally on `NoteError::Transport` only.
- The platform API's /v1 error envelope exists (`implementation/api/selahcue_api/platform/responses.py`: `{"error": {"code": "RATE_LIMITED", ...}}`, UPPER_SNAKE codes) and ADR-0028 records a coded refusal `QUOTA_EXHAUSTED`. None of those match the closed list of this client; see Assumptions.
- The operator maps `NoteError` to UI codes in `selahcue-operator/src/main.rs:7330` (`consent_required`, `not_configured`, `quota_exceeded`, `transport`, and the existing `malformed`). Not changed here.
- No existing test asserts on a `Malformed` text from `client.rs` (grep of `crates/selahcue-cloud/tests` and the operator).

## Inputs and evidence sources

- ClickUp 86akbzxjg description and acceptance criteria; the note linking it on 86akby3xu is already done by the orchestrator.
- `crates/selahcue-cloud/src/openai.rs` (reference discrimination), `tests/test_openai.rs` (captured fixtures), `src/lib.rs` (fallback classification).
- Repo `CLAUDE.md` and `implementation/desktop/CLAUDE.md` (mutation-verification method: run with siblings, never `--exact`; a control must consume the same predicate as the code under test).
- PRD FR-135, FR-082.

## Scope

### In scope

- New always-compiled module `src/provider_error.rs`: parses an error body into an allowlisted view (a reason code from a closed list; no correlation handle) and exposes the single terminal-exhaustion predicate, with a 32 KiB parse bound (`MAX_ERROR_BODY_PARSE_BYTES`, the only public item). `src/openai.rs` swaps its private `error_code` for it (behaviour unchanged).
- `client.rs`: `status_error` rewritten (402 terminal; 429 split on the shared predicate; 5xx transport; everything else `Malformed` with our wording plus the allowlisted fields); the two `serde_json` error sites replaced by a helper that states the error category and position only.
- New test file `tests/test_client_errors.rs` (no feature gate, so it runs in the default build): the captured 401, credential-shaped material at several positions, both entry points, the two 429 cases through `generate_sermon_notes`, 402, a 2xx type-mismatch leak, the parse bound, hostile body shapes (BOM, case, whitespace, non-string values, top-level non-objects, over-nesting), the cross-field rule, a 5xx carrying an exhaustion code, and the NoteError variants the client returns.
- Doc notes: the fallback list in `generate_sermon_notes`, and an "Error responses" note in `contract.rs` for 86akby3xu.
- Goal contract, PR description.

### Non-goals

- Behaviour of the OpenAI client other than sharing the predicate (lane B, 86akby7d8).
- New `NoteError` variants or new UI codes; `settings.js` stays untouched.
- The hosted service's error design (86akby3xu).
- Retry or back-off logic: a transient 429 becomes `Transport`, which already means "serve the local draft"; this client does not retry.
- Reading response headers (`HttpResponse` has none).
- A correlation-handle channel. Dropped after review: nothing produces a request id today, and a check on the shape of a value cannot tell an identifier from an alphanumeric secret. 86akby3xu defines the hosted envelope and can add a channel with a producer behind it.
- A non-secret degraded reason on `GenerationOutcome` (see the PR follow-ups).

### Constraints

- Strict TDD: failing test first; the leak test and the 429 test are mutation-verified, run with siblings, files restored byte-identical (`cmp`).
- No redaction regex over free text. Allowlist of fields only.
- No Co-Authored-By trailer; push only to the ticket branch; PR opened as Draft against main; no ready, no merge, no QA move.
- Disk free above 15 GiB (13 GiB for the review-round work, by the orchestrator's later instruction); no second target dir, no second worktree; `CARGO_INCREMENTAL=0` for the round-1-review builds.
- Nothing new may grow without bound (nothing here buffers).

### Assumptions and unknowns

- ASSUMED: a hosted service that wants its exhaustion treated as terminal sends HTTP 402, or a 429 whose `error.code` or `error.type` is `insufficient_quota` or `credit_balance_exhausted`, in the `{"error": {"type", "code"}}` shape the in-tree OpenAI reference reads. The hosted envelope is not defined (86akby3xu owns it), but it is only partly true that nothing defines an envelope today: the platform API /v1 envelope in `selahcue_api/platform/responses.py` uses UPPER_SNAKE codes (`RATE_LIMITED`, ...) and ADR-0028 records `QUOTA_EXHAUSTED`; none of these match the closed list, and matching is exact and case-sensitive. A 429 `RATE_LIMITED` therefore reads as transient (right), but exhaustion signalled only by an UPPER_SNAKE code on a 429 would also read as transient. The orchestrator's comment on 86akby3xu asks for 402 (or a listed code) and for upstream provider exhaustion to be translated, never forwarded; the same note is in the `contract.rs` docs.
- UNKNOWN: whether a bare 401/403 from the hosted service should become `NotConfigured` (as the OpenAI mapper does). Left as `Malformed`, as today; flagged as a follow-up.

## Dependencies and approvals

- 86akby7d8 (lane B) is merged on origin/main; this change edits `openai.rs` by one function only.
- Sana's review of the allowlist approach is part of the orchestrator's review gate, not run by this role.

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Failing tests exist first and fail for the stated reason | `cargo test -p selahcue-cloud --test test_client_errors --no-fail-fast` before any production change | the leak, 429 and 2xx tests FAIL on the unmodified client | RED run before any production change: 7 of 11 tests failed, 4 already correct (terminal 429, 402, 5xx, contract codes); failures were the key fragment in the Malformed text, the serde value echo, and transient 429 as QuotaExceeded; log kept as working file | PASS |
| C-002 | yes | No `NoteError` text (Display or Debug) from either entry point contains any part of a provider body, against the captured 401 and against credential-shaped material at several positions | `cargo test -p selahcue-cloud --test test_client_errors` | passes; each position has a premise check that the marker is really in the body | tests/test_client_errors.rs (17 tests after review round 1): 11 hostile bodies (start, middle, past 200 bytes, end, in code, in type, in error.request_id, extra field, echoed bearer, HTML) x 14 statuses x 2 entry points, marker check plus a 12-character-run check against the whole body, premise per case; error.request_id is never read (three shapes, with a positive control that the reason beside it is kept); mutants L1 to L4, L5b, N6 RED | PASS |
| C-003 | yes | A 429 with `insufficient_quota` / `credit_balance_exhausted` is `QuotaExceeded` and propagates with no fallback; a plain-rate-limit 429 is `Transport` and yields the degraded local draft; the two outcomes differ | same file | passes | terminal_bodies (5) give Err(QuotaExceeded) through generate_sermon_notes; transient_bodies (8, now including a rate limit whose free-text message names both exhaustion codes) give a degraded local draft; a pair differing only in the code field gives different outcomes; mutants D1, D2 and N1 (free text read) RED | PASS |
| C-004 | yes | 402 stays terminal (`QuotaExceeded`, no fallback) | same file | passes | a_402_is_terminal_whatever_its_body_says passed for all 12 bodies on both entry points and the orchestrator; mutant D3 RED | PASS |
| C-005 | yes | `generate_with_quota` and `fetch_quota` both covered for the leak and the 429 split | same file | passes | every test above runs both generate_with_quota and fetch_quota; mutants L8 (fetch site only) and L9 (generate site only) each RED | PASS |
| C-006 | yes | A 2xx body that fails typed parsing does not echo the offending value | same file | passes | a_success_status_with_a_mistyped_field_does_not_echo_the_value passed, with a control that serde_json itself quotes the value; mutants L8 and L9 RED | PASS |
| C-007 | yes | The five UI error codes are unchanged (four contract codes plus malformed): `NoteError` variants unchanged, `settings.js` and the operator mapper untouched | `git diff origin/main --stat` | no change to `selahcue-core`, `selahcue-operator` | git diff origin/main --stat touches only selahcue-cloud (client.rs, contract.rs docs, lib.rs, openai.rs, provider_error.rs, tests/test_client_errors.rs) and this contract; no selahcue-core, selahcue-operator or settings.js change; no manifest change. The operator maps FIVE variants (consent_required, not_configured, quota_exceeded, transport, malformed); this crate cannot see that function, so the test each_note_error_variant_the_client_returns_is_still_produced_by_its_original_path pins only that no NoteError variant was added or removed and that each path still returns its original variant | PASS |
| C-008 | yes | There is one discrimination: `client.rs` and `openai.rs` both call `provider_error`; `openai.rs` has no private copy | read of the diff plus a grep | one definition of the exhaustion codes outside tests | grep shows the exhaustion codes defined once, in provider_error.rs; openai.rs private error_code deleted and its 429 arm calls ErrorFields::parse(body).is_terminal_exhaustion(); mutants D4 to D9 and N5 on the shared definition turn test_client_errors RED, and D8 and D9 also turn lane B test_openai.rs tests RED under --features openai | PASS |
| C-009 | yes | The leak test and the 429 test are mutation-verified (RED when the fix is removed, GREEN restored byte-identical), run with siblings | mutation script, `cmp` after each restore | every mutant RED, every restore GREEN, `cmp` clean | mutation harness (working file outside the repository), re-run in review round 1 with the extended file: 30 mutants applied one at a time, the whole test_client_errors file run with its siblings, never --exact; 27 RED by failing tests; 1 (N4, cap raised to 3 MiB) caught only at compile time by the 64 KiB upper-bound pin in the test file, reported as a build break not a failing test; 2 survived (N9 trim and N10 ignore-case applied to the terminal match only, equivalent mutants because the output step re-filters through the exact-match closed list; the real both-places mutants N9b and N10b are RED); every restore cmp-identical and the whole file green after the final restore. Round 1 (20 mutants, one equivalent survivor L5, replaced by L5b RED) predates the request-id removal and the new tests | PASS |
| C-010 | yes | Existing `selahcue-cloud` tests pass unchanged on default, `--features http` and `--features openai` builds | `cargo test -p selahcue-cloud --no-fail-fast` x3 | exit 0 | cargo test -p selahcue-cloud --no-fail-fast exit 0 (47 passed) on default, --features http exit 0 (67 passed, NO_PROXY set), --features openai exit 0 (96 passed); baseline on origin/main was 30 on default; no existing test file changed | PASS |
| C-011 | yes | fmt, clippy (workspace and `-p selahcue-cloud --features http`), workspace tests, import guards, launch reachability | the gate commands | exit 0 each | cargo fmt --all --check exit 0; cargo clippy --workspace --all-targets -D warnings exit 0; clippy -p selahcue-cloud on default, http and openai exit 0 each; cargo test --workspace --no-fail-fast exit 0 (1899 passed, 5 ignored, 0 failed); scripts/import_guards.sh exit 0; scripts/check_launch_reachability.py exit 0; all run with CARGO_INCREMENTAL=0 after the review-round changes | PASS |
| C-012 | yes | `make ci` passes (one run, serialised) | `make ci` | exit 0, or any failure shown to exist on origin/main as well | NOT RUN. The orchestrator held make ci and every selahcue-operator build because the data volume is near its floor (another session is compiling the operator). Held commands are listed in the PR description | BLOCKED |
| C-013 | yes | Branch contains origin/main and a Draft PR exists against main | `git rev-list --count HEAD..origin/main`, `gh pr view` | 0; Draft | Draft PR https://github.com/First-Pavilion/selahcue/pull/230 against main (gh pr view: isDraft true, base main); origin/main ed561471 unchanged at fetch and an ancestor of HEAD (rev-list HEAD..origin/main is 0) | PASS |
| C-014 | yes | The goal contract validates | `python3 ~/.claude/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/86akbzxjg-cloud-client-error-bodies.md` (and `--completion` before the claim) | exit 0 | repo validator exit 0 and skill validator structural exit 0; skill validator --completion exit 1 with exactly one error, C-012 (BLOCKED, make ci held); no VERIFIED_COMPLETE is claimed | PASS |
| C-015 | yes | The error-body parse is bounded: a body over 32 KiB is never parsed; a terminal code in an oversized body reads as transient with nothing leaked; a body exactly at the cap still parses | `cargo test -p selahcue-cloud --test test_client_errors` | boundary both sides plus a transport-cap-sized body | a_terminal_429_exactly_at_the_parse_cap_still_parses_and_one_byte_over_reads_as_transient and a_transport_cap_sized_body_is_refused_before_it_is_parsed pass (the second uses a literal 4 MiB array body so raising or removing the cap reddens it); compile-time pins keep the cap under the transport cap, at least 8 KiB and at most 64 KiB; mutants N2 (cap removed) and N3 (cap exclusive) RED, N4 (cap raised) fails the build through the pin. The new tests were written after the production edit, so the RED proof is the mutants | PASS |
| C-016 | yes | Hostile body shapes and the cross-field rule are pinned: non-string, string-valued error, BOM, case and whitespace variants, top-level non-objects, over-nesting all read as transient; exhaustion in either field wins; a 5xx carrying an exhaustion code stays Transport; free-text message never read | same file | passes | hostile_shapes_read_as_transient_and_a_malformed_terminal_body_is_not_terminal (16 bodies, with positive controls: a terminal body nested 100 levels deep and the plain terminal body are terminal), exhaustion_in_either_field_wins_whatever_the_other_field_says, a_5xx_carrying_an_exhaustion_code_is_transport_by_design, the_free_text_message_is_never_read_for_the_terminal_decision pass; RED proof by mutants N8 (BOM stripped), N9b (whitespace), N10b (case), N11 (top-level fallback), N5 (first known reason by field order), N7 (5xx read as quota), N1 (free text read). The nesting-past-128 case has no mutant (the limit is serde_json internal); its positive control shows the parser is live | PASS |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused verification: `tests/test_client_errors.rs` by file, with siblings, never `--exact`.
- Broader regression verification: the whole `selahcue-cloud` suite on three feature sets, the workspace tests, `make ci`.
- Independent verifier: the orchestrator dispatches Cody, Shadow, Quinn and Vera; this run does not.
- Required environment: `NO_PROXY=127.0.0.1,localhost` for the `http` tests; cmake and Flutter on PATH for `make ci`.

## Iteration ledger

### Iteration 0

- Target criterion: baseline
- Hypothesis: the existing `selahcue-cloud` suite is green on origin/main ed561471
- Change or investigation: ran the existing selahcue-cloud suite on origin/main ed561471
- Verifier executed: `cargo test -p selahcue-cloud --no-fail-fast`
- Result: exit 0, 30 passed
- New evidence: working log kept outside the repository
- Decision: iterate

### Iteration 1

- Target criterion: C-001 to C-006
- Hypothesis: the captured 401, key-shaped material at several positions, the two 429 shapes, 402 and a mistyped 2xx body each fail against the old client for the stated reason
- Change or investigation: wrote tests/test_client_errors.rs first and ran it against the unmodified client
- Verifier executed: `cargo test -p selahcue-cloud --test test_client_errors --no-fail-fast`
- Result: 7 failed, 4 passed (the 4 were already correct); failure messages named the key fragment in the Malformed text, the serde value echo, and the transient 429 as QuotaExceeded
- New evidence: RED log kept outside the repository
- Decision: iterate

### Iteration 2

- Target criterion: C-001 to C-008, C-010
- Hypothesis: an allowlisted ErrorFields view plus one shared terminal predicate turns the file green with no other change
- Change or investigation: added src/provider_error.rs, rewrote status_error in client.rs, replaced the two serde error sites, pointed openai.rs at the shared predicate
- Verifier executed: the new file, then the whole crate on three feature sets
- Result: 11 of 11 green; 41, 61 and 90 passed across the crate; clippy clean
- New evidence: counts in C-010
- Decision: iterate

### Iteration 3

- Target criterion: C-009 and C-011
- Hypothesis: every guard turns at least one test RED when removed
- Change or investigation: mutation harness over 20 single-edit mutants (body echo in four arms, closed-list bypass, request-id shape, the two serde sites separately, 429 flattening both ways, 402, each terminal code, each field, the shared predicate, the describe positive control), then the workspace gates
- Verifier executed: the whole test_client_errors file per mutant, plus the whole crate under --features openai for the shared-predicate mutants
- Result: 19 RED, 1 equivalent survivor (L5) replaced by the real mutant L5b, RED; every restore cmp-identical and green. Workspace gates all exit 0
- New evidence: the survivor was an equivalent mutant, not a missing test. Lane B tests do not redden on D4 and D7 because their captured fixture carries both terminal codes; this change adds the code-only and type-only bodies that do
- Decision: gate-review

### Iteration 4 (review round 1)

- Target criterion: findings of the Cody, Shadow and Quinn reviews at 157f7421 (no blockers)
- Hypothesis: dropping the request-id channel, bounding the parse and pinning the hostile shapes closes the findings without changing behaviour for real envelopes
- Change or investigation: removed is_request_id, the handle field and its emission; added MAX_ERROR_BODY_PARSE_BYTES (32 KiB) checked before parsing; six new test groups and two premise controls; docs in lib.rs, client.rs and contract.rs. The new tests were written AFTER the production edits, so they have no red-first run; the RED proof is the mutants listed under C-015 and C-016
- Verifier executed: the whole test_client_errors file (17 passed), then 30 mutants, then every gate under CARGO_INCREMENTAL=0
- Result: 27 RED by failing tests, 1 compile-time catch, 2 equivalent survivors replaced by RED mutants; all gates exit 0 (counts under C-010 and C-011)
- New evidence: the trim and ignore-case survivors showed the closed-list exact match is a second filter, so a mutation of the terminal match alone changes nothing observable
- Decision: gate-review

## Risks and rollback

- Risks: a transient 429 now gives a degraded local draft instead of a quota dead end, which is the requested change. A hosted service that answers a genuine exhaustion with a 429 and no recognised code would now read as transient (and fall back) rather than as quota exceeded; the hosted service must send one of the two codes, or a 402. This is the same trade the OpenAI mapper already makes. An error body over 32 KiB is not parsed, so a terminal code inside one is not seen (a 429 reads as transient); real envelopes are under 1 KiB. A 5xx always reads as transient whatever its body says, which is intended.
- Rollback or recovery: revert the PR merge; no data, schema or wire change.

## Pause and escalation conditions

- Disk free below the stated floor (15 GiB, later 13 GiB): stop and report.
- A conflict with origin/main that needs a judgement call: stop and ask the orchestrator.
- Any need to change `NoteError` or the UI codes: escalate (frozen FE-BE contract).

## Final evaluation

- Validator command: `python3 ~/.claude/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/86akbzxjg-cloud-client-error-bodies.md --completion`
- Validator result: structural OK; completion mode fails only on C-012 (BLOCKED, make ci held) until that is run
- Independent verification result: NOT YET RUN. Code, security, QA and performance reviews are dispatched by the orchestrator; Sana is asked to review the allowlist approach specifically
- Terminal state: BLOCKED on C-012 only (make ci and the selahcue-operator build are held for disk space); every other mandatory criterion PASS
- Remaining failed or blocked criteria: C-012. Not run locally: hosted CI (billing-blocked), the three-OS matrix, the operator crate, make ci
- ClickUp final evidence comment: mutation evidence posted on 86akbzxjg
