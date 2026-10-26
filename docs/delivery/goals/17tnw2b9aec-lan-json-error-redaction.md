# Goal Contract - 17tnw2b9aec-lan-json-error-redaction

## Identity

- Goal ID: 17tnw2b9aec-lan-json-error-redaction
- Parent goal ID: NONE
- Title: A malformed inbound LAN frame can no longer put the value it choked on, a transcript or a token, into a TransportError
- Role: backend-engineer
- Status: GATE_REVIEW
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/17tnw2b9aec
- Created: 2026-10-26
- Updated: 2026-10-26
- Maximum iterations: 6
- Independent verification required: yes

## Objective

Make `selahcue_lan::TransportError::Json` carry only the category and the line and column of a JSON failure, never serde's message, so that `Display`, the derived `Debug` and the `source()` chain of the error that crosses the crate boundary contain nothing a frame supplied (FR-082), while still naming the failure's category and, when serde has one, its position. Pin it with a planted secret in a mistyped field of every inbound frame shape, and through the real client and server.

## Baseline

**Verified** on `origin/main` at `840ec84e` (2026-10-26), by reading the code and by running the new tests against it (they fail, see iteration 1):

- `TransportError::Json(serde_json::Error)` (`selahcue-lan/src/tls.rs`), `Display` prints `json error: {e}` and the derived `Debug` prints the whole error. `recv_json` (`wire.rs`) converts every parse failure with `TransportError::from`.
- serde quotes the offending value: `json error: invalid type: string "SECRET-SERMON-WORDS-9f3a-do-not-log", expected a sequence` (the ticket's operator-state frame, reproduced), `... expected u16` (a `Hello` whose `v` is a string), and ``unknown variant `SECRET...`, expected one of `operator`, `producer`, `assistant`, `viewer` `` (a role, a tag or a reason that is not on the list).
- Inbound shapes that go through `recv_json`: `AuthResponse` and `PairResponse` and `ServerMessage` at the client (`connect`, `pair`, `command`), `Hello` at the server. The server's request loop does not surface the parse error (it answers a fixed "malformed request"), and `ControlServer::run` discards the result of `serve_connection`, so the host does not log these errors today; the exposure is at the client (the operator's `RemoteOperator`, the native controller) and at any caller that logs `serve_connection`'s result.
- Consumers: no code outside `selahcue-lan` matches `TransportError::Json` or reads the `serde_json::Error` inside it; five comments in `selahcue-operator/src/main.rs` name this ticket as a residual.
- serde reports line 0 and column 0 when it has no position, which is the case for a data error inside an internally tagged enum (serde buffers the content first). `ServerMessage` (tag `event`), `AuthResponse`, `PairResponse`, `Hello` and `Command` are all tagged, so the ticket's own frame renders as `... at line 0 column 0` in a first cut. QA measured 858 of 1,194 mutated frames that failed to parse (72%) as line 0 column 0, all data errors. The first push printed that as if it were a place (found by QA, fixed in iteration 5).
- Dart controller (grep, not an audit): the connect and pair path catches `FormatException` and throws a fixed `SessionException`, and the unexpected-failure logger writes the runtime type and a bounded stack, "never `error.toString()`" (`lib/models/session.dart`, `lib/main.dart`).

## Inputs and evidence sources

- ClickUp 17tnw2b9aec (description), related 17tnw2axppb (Protocol dump, fixed) and 17tnw2axpp3 (audit of the same path)
- `selahcue-lan/src/{tls,wire,client,server,protocol}.rs`; `selahcue-app/tests/test_no_debug_dump_in_errors.rs` and `src/operator_reply.rs` (the 17tnw2axppb pattern)
- PR #230 (86akbzxjg): the cloud client keeps serde's category and position only (`selahcue-cloud/src/client.rs`, `selahcue-licensing/src/client.rs`); this change reuses that approach and does not invent a second one

## Scope

### In scope

- `implementation/desktop/crates/selahcue-lan/src/tls.rs` (the variant's type and the conversion), `src/lib.rs` (re-export), `src/protocol.rs` (a doc warning on `from_json`)
- `selahcue-lan/tests/test_json_error_redaction.rs` (new)
- `implementation/desktop/CLAUDE.md` (one bullet), this contract

### Non-goals

- Editing or building `selahcue-operator` (the five stale comments are listed in the PR for a follow-up; it is a separate cold build and another lane owns `main.rs`)
- The sibling paths found by the survey (listed in the PR body with file and line; the coordinator files follow-ups)
- The Dart client beyond the grep above
- `TransportError::Ws` (tungstenite's `Debug` can print an HTTP response body): listed in the survey, not changed here

### Constraints

- One ticket, one branch, one Draft PR off `origin/main`; not marked ready or merged by this role; no `Co-Authored-By` trailer
- No manifest or lock change; no new dependency
- The operator is not built
- Source ASCII-only

### Assumptions and unknowns

- **Verified** on macOS arm64, Rust 1.98.0: the tests and every gate in the PR.
- **Unknown**: whether the operator crate compiles against the changed variant type. Nothing outside `selahcue-lan` was found that names `TransportError::Json` (grep over `implementation/desktop`), so it should, but it is not built here. Held for the coordinator.
- **Assumed**: the `Io` category is unreachable when parsing a string and is kept only so the mapping is total.

## Dependencies and approvals

- None. Reviewers (Cody, Shadow, Quinn, Vera) are dispatched by the coordinator after the Draft PR is open.

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`. This contract stops at `GATE_REVIEW`: C-008 (independent review) and C-009 (the operator commands) are not run by this role.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | The new tests fail on the unfixed code for the stated reason (serde's quoted value is in the error's `Display`) | `cargo test -p selahcue-lan --features server --test test_json_error_redaction` on `840ec84e` plus the test file | exit 101; 5 of 7 red (the table of frame shapes and the four real-transport cases) with `json error: invalid type: string "SECRET-SERMON-WORDS-9f3a-do-not-log", expected a sequence` and the unknown-variant form; the two controls stay green | iteration 1 | PASS |
| C-002 | yes | For each of 17 malformed frames, one per inbound shape and per quoting style (wrong type, unknown variant, unknown tag, an integer, a negative integer, a float, the pairing hello), the `Display`, `Debug`, alternate `Debug` and `source()` chain of the `TransportError` contain neither the planted secret nor a distinctive fragment of it (a prefix, a middle part), and the error still starts with `json error: ` and says where when serde has a position (`at line L column C`, serde's own numbers) or `(no position)` when serde has none; every failing case is reported together | `a_mistyped_field_of_every_inbound_frame_shape_never_reaches_the_transport_error`; premise per case: serde's own error contains the secret in `Display` and `Debug` | exit 0 | iterations 2 and 5 | PASS |
| C-003 | yes | The same through the real transport: a hostile host answering `ControlClient::connect`, `pair` and `command` (the ticket's operator-state frame with a string transcript), and a hostile controller sending `ControlServer::serve_connection` a bad `Hello`: the returned error is `TransportError::Json`, says it is a JSON error, and contains no secret | the four `a_hostile_*` tests | exit 0 | iteration 2 | PASS |
| C-004 | yes | Diagnostic value is kept, and is honest about position: each category keeps its kind and its exact wording (`ended early`, `not valid JSON`, `did not have the shape`, `could not be read`); a truncated frame, a syntax error and a shape error in a plain struct carry a NONZERO position; a shape error inside a tagged enum (the ticket's own frame, where serde reports line 0 column 0) says `(no position)` and never `line 0`; an io failure from a reader quotes nothing | `each_category_keeps_its_kind_its_wording_and_a_position_where_serde_has_one`, `a_shape_error_inside_a_tagged_enum_says_it_has_no_position_instead_of_line_0` (premise: serde's own position is 0 and 0), `an_io_failure_is_its_own_kind_and_quotes_nothing_from_the_reader` | exit 0 | iterations 2 and 5 | PASS |
| C-005 | yes | Every new test fails when the redaction or the diagnostic is undone. The substitutions in `tls.rs` (M1 to M6 in iteration 3, M7 to M13 in iteration 5) are written out in the ledger | the command in iteration 3, each mutation run with the redaction file and its siblings `test_server` and `test_protocol` (never `--exact`), `tls.rs` restored from a copy and checked with `cmp`; plus two fixture mutations in the test file (iteration 5) | each mutation exit 101 with the named tests red; restored byte-identical | iterations 3 and 5 | PASS |
| C-006 | yes | Existing `selahcue-lan` (default and `server`), `selahcue-app --features server` and workspace tests are unchanged and green | `cargo test -p selahcue-lan --features server`, `cargo test -p selahcue-lan`, `cargo test -p selahcue-app --features server`, `cargo test --workspace`, all `--no-fail-fast` | all exit 0 (140, 103, 352 with 1 ignored, and 1,909 with 5 ignored) | iteration 5 | PASS |
| C-007 | yes | fmt, clippy (`-D warnings`) workspace and `selahcue-lan` on default and `server`, import guards, launch reachability, both goal-contract validators | the commands in the PR description | all exit 0 | iteration 4 | PASS |
| C-008 | yes | Independent review passed (code, security, QA, performance) at the head SHA | review report page | verdicts recorded, zero open blocking findings | held for the coordinator | PENDING |
| C-009 | no | `selahcue-operator` compile-check, clippy and tests, and one `make ci` | the operator commands in the PR description | exit 0 | held for the coordinator | PENDING |
| C-010 | yes | The survey of sibling paths is recorded with file and line | the PR description, "Sibling paths" | present | iteration 2 | PASS |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused verification: C-001 to C-005 from the worktree, every gate captured to a file and its exit code read (no piped gate)
- Broader regression verification: C-006 and C-007
- Independent verifier: Cody, Shadow, Quinn and Vera, dispatched by the coordinator
- Required environment: macOS arm64 host, Rust 1.98.0 (pinned), the workspace target cloned copy-on-write from a baseline worktree

## Iteration ledger

### Iteration 1

- Target criterion: C-001
- Hypothesis: `TransportError::Json` prints serde's message in both `Display` and `Debug`, and the existing suite pins nothing that says otherwise
- Change or investigation: wrote `test_json_error_redaction.rs` (a table of 13 malformed frames, one control that the same shapes parse when unbroken, a position-and-category test, and four real-transport cases: a hostile host against `connect`, `pair` and `command`, a hostile controller against `serve_connection`) and ran it on the unfixed code
- Verifier executed: `cargo test -p selahcue-lan --features server --test test_json_error_redaction`
- Result: exit 101, 5 red and 2 green. Red: the ticket's own frame, `json error: invalid type: string "SECRET-SERMON-WORDS-9f3a-do-not-log", expected a sequence`; a `Hello` with a string `v`, `... expected u16`; and a role, tag or reason that is not on the list, ``unknown variant `SECRET-SERMON-WORDS-9f3a-do-not-log`, expected one of `operator`, `producer`, `assistant`, `viewer` ``. Green: the control that the unbroken frames parse, and the syntax and truncation positions (which must stay as they were)
- New evidence: an unknown enum tag quotes the value too, not only a wrongly-typed field, so the fix cannot be "avoid `invalid type`"
- Decision: iterate

### Iteration 2

- Target criterion: C-002 to C-004, C-010
- Hypothesis: a variant that holds only a category and two numbers cannot leak, and `From<serde_json::Error>` as the only way in keeps it that way
- Change or investigation: `TransportError::Json(JsonFailure)`; `JsonFailure` holds a `JsonFailureKind` (syntax, data, eof, io) and the line and column, with `Display` in our own words ("the message did not have the shape the protocol defines at line L column C"); `From<serde_json::Error>` drops the error; a doc warning on `protocol::from_json`; a CLAUDE.md bullet; the survey
- Verifier executed: the redaction test file
- Result: 7 of 7 green
- New evidence: none new
- Decision: iterate

### Iteration 3

- Target criterion: C-005
- Hypothesis: the tests catch the passthrough restored in each way it could come back
- Change or investigation: six substitutions in `tls.rs` (driver script in the scratchpad, since deleted): (M1) `JsonFailure` also stores `e.to_string()` and `Display` appends it, so both renderings print it; (M2) stored, printed by the derived `Debug` only; (M3) stored, printed by `Display` only with a hand-written `Debug` that omits it; (M4) `From<serde_json::Error>` builds `TransportError::Protocol(format!("json error: {e}"))` instead; (M5) `Display` drops the position; (M6) `TransportError`'s `Display` drops the `json error: ` prefix
- Verifier executed: `cargo test -p selahcue-lan --features server --test test_json_error_redaction --test test_server --test test_protocol --no-fail-fast` per substitution, then `cmp` of `tls.rs` against the saved copy
- Result: all six exit 101, restored byte-identical. M1, M2 and M3 redden the table and the four real-transport cases; M4 reddens those and the position test; M5 reddens the table and the position test; M6 reddens the table, the position test and the `connect` and `command` cases
- New evidence: Display-only and Debug-only leaks are caught separately, because the assertions read every rendering, not one
- Decision: iterate

### Iteration 4

- Target criterion: C-006, C-007
- Hypothesis: nothing outside the variant's type moved
- Change or investigation: full gate set, results in the PR description
- Verifier executed: the gate script
- Result: every gate exit 0
- New evidence: none
- Decision: gate-review

### Iteration 5 (review polish: Cody PASS, Shadow PASS, Quinn PASS WITH CONDITIONS; 0 blocker/major)

- Target criterion: C-002, C-004, C-005, C-006
- Hypothesis: three assertions guarded nothing (`assert_ne!` of strings that already differ by position; a tautology on a frame built from the secret; a check for the whole secret only), the category mapping had no mutant, and QA found a real diagnostic gap: serde has no position for a shape error inside a tagged enum, so the first push printed `at line 0 column 0`
- Change or investigation: `Display` says `(no position)` when serde reports line 0 (the numbers stay in the type); the category test asserts `kind()` and the exact wording for each kind, and a nonzero position for a truncated frame, a syntax error and a plain-struct shape error; a new test for the tagged-enum case (premise: serde reports 0 and 0) asserting `(no position)` and no `line 0`; an io-failure test through `serde_json::from_reader` with a failing reader whose error carries the secret; `assert_no_secret` also rejects fragments of the planted value (`SECR`, `SERMON`, `9f3a`; `4815`, `162342`); the table grew to 17 frames (`Hello::Pair` with a string version and a numeric code, and an integer, a negative integer and a float in the wrong field, since serde quotes numbers in backticks) and reports every failing case together; the premise of each real-transport case is checked up front by parsing the hostile frame; the three client calls are bounded at 10 s (`pair` alone is capped only by its 150 s timeout); `JsonFailureKind` is `#[non_exhaustive]` (nothing outside `selahcue-lan` matches it) and its `Io` variant is documented as unreachable from parsing; a doc warning on `to_json`
- Verifier executed: the command in C-005 with seven further substitutions of `tls.rs`: (M7) the Syntax and Data arms of `From<&serde_json::Error>` swapped; (M8) `Display` uses one sentence for every kind; (M9) serde's message kept with everything between double quotes blanked, a string-only redactor; (M10) `if self.line == 0 {` replaced by `if false {`, so `Display` always prints the position; (M11) `Category::Eof => JsonFailureKind::Data`; (M12) `Display` appends the first 22 characters of serde's message after the unchanged position wording; (M13) `Category::Io => JsonFailureKind::Syntax`. Two fixture mutations in the test file: the connect fixture made well-formed, and a host that says nothing so `pair` would wait for its 150 s timeout. The full gate set
- Result: M7 red in the category test and the tagged-enum test; M8 red in those and the io test; M9 red in 23 findings across the table, the real `connect` and `pair` cases, the tagged-enum test and the io test (a string-only redactor leaks numbers, backticked variants and the io message); M10 red in the table (13 cases) and the tagged-enum test; M11 red in the category test only; M12 red in 7 table cases (exactly the unknown-variant ones, found by the `SECR` fragment) plus `connect`, `pair` and the io test; M13 red in the io test only; M1 to M6 re-run on the final tests, all red; all restored byte-identical (`cmp`). Fixture mutations: the well-formed connect fixture panics with `the hostile frame should not parse` before the transport is involved; the silent host fails `pair` with `pair did not return within 10 s` after 10.01 s. Every gate exit 0 (counts in C-006)
- New evidence: a whole-secret check misses a prefix leak; the first draft of the tagged-enum test failed first for the right reason (`... at line 0 column 0`, 13 of 17 table cases) before the `Display` change
- Decision: gate-review

## Risks and rollback

- Risks: a downstream crate that matched `TransportError::Json(e)` and used `e` as a `serde_json::Error` would stop compiling. None exists in `implementation/desktop` outside `selahcue-lan`; `selahcue-operator` is not built here and is the one crate to check (it depends on `selahcue-lan`). Diagnostic text for a bad frame is now our own wording plus a position; a developer who wants serde's text must reproduce the frame with `protocol::from_json`.
- Trade-off, recorded plainly (Cody F5): `Display` deliberately drops the `missing field` name that the licensing client's `missing_field` helper keeps, because every serde `Display` variant can carry peer text (`unknown field` names a key the peer chose, `unknown variant` and `invalid type` quote values) and telling a safe message from an unsafe one would mean parsing English. A missing-field failure is now identified by its position and category, not by the field's name; a developer who needs the name reproduces the frame with `protocol::from_json`.
- The kept line and column reveal roughly how far into the frame the failure was (about a byte offset), never what was there (Shadow F5).
- Follow-ups filed by the orchestrator: `from_json`/`to_json` returning `JsonFailure`; sibling error-text exposures (`TransportError::Ws` Debug, `DataError::Corrupt`, `invalid theme`, five stale operator comments). The ids will be given in the PR comment.
- Rollback or recovery: revert the change; the old variant type returns and the leak with it.

## Pause and escalation conditions

- The operator crate fails to compile against the new variant type: stop and report; the fix there is a one-line pattern change in a crate another lane is editing
- A reviewer finds a path that still carries serde's message into a `TransportError`: add it to the table and fix the conversion

## Final evaluation

- Validator command: `python3 scripts/validate_goal_contract.py docs/delivery/goals/17tnw2b9aec-lan-json-error-redaction.md`
- Validator result: recorded in the PR description
- Independent verification result: pending (coordinator)
- Terminal state: GATE_REVIEW
- Remaining failed or blocked criteria: C-008 and C-009 held for the coordinator
- ClickUp final evidence comment: written by the coordinator
