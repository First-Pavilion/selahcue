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

Make `selahcue_lan::TransportError::Json` carry only the category and the line and column of a JSON failure, never serde's message, so that `Display`, the derived `Debug` and the `source()` chain of the error that crosses the crate boundary contain nothing a frame supplied (FR-082). Pin it with a planted secret in a mistyped field of every inbound frame shape, and through the real client and server.

## Baseline

**Verified** on `origin/main` at `840ec84e` (2026-10-26), by reading the code and by running the new tests against it (they fail, see iteration 1):

- `TransportError::Json(serde_json::Error)` (`selahcue-lan/src/tls.rs`), `Display` prints `json error: {e}` and the derived `Debug` prints the whole error. `recv_json` (`wire.rs`) converts every parse failure with `TransportError::from`.
- serde quotes the offending value: `json error: invalid type: string "SECRET-SERMON-WORDS-9f3a-do-not-log", expected a sequence` (the ticket's operator-state frame, reproduced), `... expected u16` (a `Hello` whose `v` is a string), and ``unknown variant `SECRET...`, expected one of `operator`, `producer`, `assistant`, `viewer` `` (a role, a tag or a reason that is not on the list).
- Inbound shapes that go through `recv_json`: `AuthResponse` and `PairResponse` and `ServerMessage` at the client (`connect`, `pair`, `command`), `Hello` at the server. The server's request loop does not surface the parse error (it answers a fixed "malformed request"), and `ControlServer::run` discards the result of `serve_connection`, so the host does not log these errors today; the exposure is at the client (the operator's `RemoteOperator`, the native controller) and at any caller that logs `serve_connection`'s result.
- Consumers: no code outside `selahcue-lan` matches `TransportError::Json` or reads the `serde_json::Error` inside it; five comments in `selahcue-operator/src/main.rs` name this ticket as a residual.
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
| C-002 | yes | For each of 13 malformed frames, one per inbound shape and per quoting style (wrong type, unknown variant, unknown tag), the `Display`, `Debug`, alternate `Debug` and `source()` chain of the `TransportError` contain no part of the planted secret, and the error still starts with `json error: ` and names serde's own line and column | `a_mistyped_field_of_every_inbound_frame_shape_never_reaches_the_transport_error`; premise per case: serde's own error contains the secret in `Display` and `Debug` | exit 0 | iteration 2 | PASS |
| C-003 | yes | The same through the real transport: a hostile host answering `ControlClient::connect`, `pair` and `command` (the ticket's operator-state frame with a string transcript), and a hostile controller sending `ControlServer::serve_connection` a bad `Hello`: the returned error is `TransportError::Json`, says it is a JSON error, and contains no secret | the four `a_hostile_*` tests | exit 0 | iteration 2 | PASS |
| C-004 | yes | Diagnostic value is kept: syntax and truncation failures keep their category and position, and the categories read differently | `a_syntax_failure_and_a_truncated_frame_keep_their_category_and_position` | exit 0 | iteration 2 | PASS |
| C-005 | yes | Every new test fails when the redaction is undone. The six substitutions in `tls.rs` are written out in iteration 3 | the command in iteration 3, each mutation run with the redaction file and its siblings `test_server` and `test_protocol` (never `--exact`), `tls.rs` restored from a copy and checked with `cmp` | each mutation exit 101 with the named tests red; restored byte-identical | iteration 3 | PASS |
| C-006 | yes | Existing `selahcue-lan` (default and `server`), `selahcue-app --features server` and workspace tests are unchanged and green | `cargo test -p selahcue-lan --features server`, `cargo test -p selahcue-lan`, `cargo test -p selahcue-app --features server`, `cargo test --workspace`, all `--no-fail-fast` | all exit 0 (138, 103, 352 with 1 ignored, and 1,907 with 5 ignored) | iteration 4 | PASS |
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

## Risks and rollback

- Risks: a downstream crate that matched `TransportError::Json(e)` and used `e` as a `serde_json::Error` would stop compiling. None exists in `implementation/desktop` outside `selahcue-lan`; `selahcue-operator` is not built here and is the one crate to check (it depends on `selahcue-lan`). Diagnostic text for a bad frame is now our own wording plus a position; a developer who wants serde's text must reproduce the frame with `protocol::from_json`.
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
