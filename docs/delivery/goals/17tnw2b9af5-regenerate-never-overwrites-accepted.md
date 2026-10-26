# Goal Contract — 17tnw2b9af5-regenerate-never-overwrites-accepted

## Identity

- Goal ID: 17tnw2b9af5-regenerate-never-overwrites-accepted
- Parent goal ID: NONE
- Title: When the check for an existing sermon-note draft fails for any reason, regenerating notes saves nothing, tells the operator so, and leaves the accepted draft exactly as it was
- Role: backend-engineer
- Status: ACTIVE
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/17tnw2b9af5
- Created: 2026-10-26
- Updated: 2026-10-26
- Maximum iterations: 8
- Independent verification required: yes

## Objective

Regenerate-with-retention (FR-129) promises that the operator's accepted sermon-note draft is
never destroyed by regenerating. After this change, "could not tell whether a draft exists" is a
third state that the code cannot mistake for "no draft exists": the regenerate command saves
nothing, reports "Could not check for an existing draft, so nothing was saved", and the accepted
draft (including one the operator edited) is byte-for-byte unchanged.

## Baseline

Verified by reading the code at origin/main `840ec84e` (the ticket's line numbers are stale; the
code has moved):

- `persist_generated_draft` in `implementation/desktop/crates/selahcue-operator/src/main.rs`
  loads the existing draft with `state.backend.load_sermon_note_draft(id).await.ok().flatten()`.
  Any load error becomes `None`, which takes the "no accepted draft" arm and calls
  `save_sermon_note_draft` (an upsert that replaces).
- The host repeats the same collapse one layer down. `selahcue-app/src/controller.rs`
  `Command::LoadSermonNoteDraft` answers a store failure with `draft: None` ("an absent draft and a
  storage failure both read the same way"), so a real storage failure on the host never reaches the
  operator as an error at all. `Command::SaveSermonNoteDraft` reads the existing draft with
  `.ok().flatten()...unwrap_or(false)` for its "once AI-generated, always AI-generated" guard, so a
  failed load also silently disables that guard.
- `OperatorShell::load_sermon_note_draft` (`selahcue-app/src/operator.rs`, the `Backend::Local`
  path) maps every reply that is not a `SermonNoteDraft` to `None`.
- Existing tests prove stage-versus-save routing only against a store whose load always succeeds.

## Inputs and evidence sources

- ClickUp 17tnw2b9af5 (description and acceptance criteria); found by Shadow reviewing PR #217 (17tnw2axppb).
- `implementation/desktop/crates/selahcue-operator/src/main.rs` (`persist_generated_draft`, `save_and_describe_generated_notes`, `note_error_code`).
- `implementation/desktop/crates/selahcue-app/src/controller.rs`, `operator.rs`, `operator_reply.rs`, `sermon_note_store.rs`.
- `implementation/desktop/crates/selahcue-operator/dist/transcripts.js` (`showGenError`, `showGenErrorInner`): how an error `message` is rendered.
- `docs/product` FR-129 (regenerate with retention), FR-082 (no draft text in any error, log or UI string).

## Scope

### In scope

- A three-way result type for "what is the accepted draft" in the operator (`Absent`, `Present`, `CheckFailed`), consumed by an exhaustive `match` with no wildcard, so the third case cannot fall into the first.
- `persist_generated_draft` returns an error (no save, no stage attempted) when the check failed; `save_and_describe_generated_notes` turns that into an `ok: false` reply with an existing frontend-known error code and a fixed, label-only message.
- Host side, same flow, no wire change: `LoadSermonNoteDraft` answers a store failure with the existing `Denied` reply instead of `draft: None`; `SaveSermonNoteDraft` refuses (`Denied`) when it cannot read the existing draft for its AI-label guard; the in-process `OperatorShell` load returns a `Result` so `Backend::Local` can tell the third state too.
- Tests that fail without each change (mutation-verified with their sibling tests running).
- A written list of every other place that swallows a host reply before a destructive save.

### Non-goals

- The timing window between the load and the save (17tnw2axpt3).
- Reporting the load error text. Errors in this path stay label-only (FR-082): no draft text, no serde value, no transcript in any error, log or UI string.
- The optional host-side refusal of `SaveSermonNoteDraft` over an existing draft without a "replacement" flag. It needs a new wire field; the LAN protocol is contract-tested cross-language, so it is a follow-up (see Risks).
- A check-before-generate preflight (avoids spending a generation when the save cannot happen). Follow-up.
- Changing `generate_sermon_notes` or the cloud client degrade rules (PR #230).

### Constraints

- The frontend/backend error codes are a frozen contract (`consent_required`, `not_configured`, `quota_exceeded`, `transport`, `malformed`). No new code; no change under `dist/`.
- No change to any pinned wire fixture (`protocol_test.dart` / `test_protocol.rs`). `Denied` and `BadRequest` already exist.
- Errors stay label-only; the fixed message is a constant, never built from the load error.
- Memory stays bounded: nothing added buffers anything.
- Edits to `selahcue-operator/src/main.rs` stay inside the regenerate/persist region and the regenerate test module, so the next ticket that edits the same file (17tnw2b9agb, `read_endpoint_at`) merges trivially.

### Assumptions and unknowns

- ASSUMED: nothing but the operator console calls `LoadSermonNoteDraft` (the mobile controller has no reference to it; verified by grep across `implementation/`), so answering a failed load with `Denied` has one consumer.
- UNKNOWN: the live console and a live host were not exercised; the evidence is unit and loopback-TLS tests.

## Dependencies and approvals

- None blocking. The orchestrator runs the four-reviewer gate, marks the PR ready and moves the ticket; this goal ends at a Draft PR.

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | With a store whose load fails, `persist_generated_draft` reports the check as failed, makes no save or stage call, and the accepted draft and pending slot are unchanged | `cargo test --no-fail-fast` in the operator dir, default and `--features dev-keys,openai-notes` (tests in `regenerate_with_retention_tests`) | the new tests pass; the same tests are RED with the old `.ok().flatten()` (mutations M1, M2) | `/private/tmp/claude-501/-Users-m-oluwole-Documents-code-scph/d44903ee-54ea-452f-a384-31ccf5382277/scratchpad/w2-17tnw2b9af5-test-op-default.log` (423 passed), `/private/tmp/claude-501/-Users-m-oluwole-Documents-code-scph/d44903ee-54ea-452f-a384-31ccf5382277/scratchpad/w2-17tnw2b9af5-test-op-devkeys.log` (437 passed); RED runs `/private/tmp/claude-501/-Users-m-oluwole-Documents-code-scph/d44903ee-54ea-452f-a384-31ccf5382277/scratchpad/w2-17tnw2b9af5-op-red.log`, `/private/tmp/claude-501/-Users-m-oluwole-Documents-code-scph/d44903ee-54ea-452f-a384-31ccf5382277/scratchpad/w2-17tnw2b9af5-M1-operator-old-ok-flatten.log`, `/private/tmp/claude-501/-Users-m-oluwole-Documents-code-scph/d44903ee-54ea-452f-a384-31ccf5382277/scratchpad/w2-17tnw2b9af5-M2-operator-checkfailed-arm-falls-through-to-save.log` | PASS |
| C-002 | yes | Over the real pinned-TLS link, a host that answers the load with the wrong reply type, and one that answers `Denied`, each leave the host receiving zero save and zero stage commands; a conforming `draft: None` reply still reaches the save (positive control) | same command, test `a_host_that_cannot_answer_the_check_gets_no_save_and_no_stage_over_the_real_link`, and `a_real_host_storage_failure_reaches_the_operator_as_a_failed_check` (real host controller) | pass; control passes; RED under M1, M2, M3 | same logs | PASS |
| C-003 | yes | The reply the operator console receives for a failed check is `ok: false`, code `transport` (one of the five frozen codes), the fixed message, no draft, and contains none of the planted error text | same command, test `a_failed_check_is_reported_as_not_saved_with_a_fixed_label_only_message` | pass; RED under M1, M2, M3, M5 | same logs | PASS |
| C-004 | yes | The host answers a failed store load with `Denied`, not `draft: None`, and refuses a save when it cannot read the existing draft; an absent draft still answers `draft: None` and a first save still works | `cargo test -p selahcue-app --features server --test test_sermon_note_durability`; whole crate via `cargo test --workspace --no-fail-fast` | new tests pass (26 in the file); RED against the old handlers (M3, M4) | `/private/tmp/claude-501/-Users-m-oluwole-Documents-code-scph/d44903ee-54ea-452f-a384-31ccf5382277/scratchpad/w2-17tnw2b9af5-app-green.log`, `/private/tmp/claude-501/-Users-m-oluwole-Documents-code-scph/d44903ee-54ea-452f-a384-31ccf5382277/scratchpad/w2-17tnw2b9af5-app-red.log`, `/private/tmp/claude-501/-Users-m-oluwole-Documents-code-scph/d44903ee-54ea-452f-a384-31ccf5382277/scratchpad/w2-17tnw2b9af5-M3-host-load-error-answered-as-no-draft.app.log`, `/private/tmp/claude-501/-Users-m-oluwole-Documents-code-scph/d44903ee-54ea-452f-a384-31ccf5382277/scratchpad/w2-17tnw2b9af5-M4-host-save-guard-skipped-on-unreadable.app.log` | PASS |
| C-005 | yes | `Backend::Local` distinguishes a failed load from "no draft" (`OperatorShell::load_sermon_note_draft` returns `Result`) | test `the_in_process_shell_tells_a_failed_load_from_no_draft` and the operator Local test | pass; RED under M5 | `/private/tmp/claude-501/-Users-m-oluwole-Documents-code-scph/d44903ee-54ea-452f-a384-31ccf5382277/scratchpad/w2-17tnw2b9af5-M5-shell-folds-refusal-into-no-draft.app.log` | PASS |
| C-006 | yes | No wire fixture changed and the frontend is untouched | `git diff --stat origin/main -- implementation/mobile implementation/desktop/crates/selahcue-lan implementation/desktop/crates/selahcue-operator/dist` | empty | command output recorded in the PR description | PASS |
| C-007 | yes | Format, lint, tests and guards are green with exit codes captured to files | `cargo fmt --check` (workspace and operator), `cargo clippy --all-targets -D warnings` (operator: default, `openai-notes`, `dev-keys,openai-notes`; workspace), `cargo test --no-fail-fast` (operator default and `dev-keys,openai-notes`; workspace), `cargo test -p selahcue-app --features server --no-fail-fast`, `sh scripts/import_guards.sh`, `python3 scripts/check_launch_reachability.py` | every exit code 0 | `/private/tmp/claude-501/-Users-m-oluwole-Documents-code-scph/d44903ee-54ea-452f-a384-31ccf5382277/scratchpad/w2-17tnw2b9af5-fmt-ws.exit`, `fmt-op`, `clippy-op-default`, `clippy-op-openai`, `clippy-op-devkeys`, `clippy-ws`, `test-op-default`, `test-op-devkeys`, `test-ws`, `import-guards`, `launch-reach` (all 0), `test-app-server` (0; 355 passed, 1 ignored; run once free disk was back at 12.2 GiB) | PASS |
| C-008 | yes | Every other host-reply swallow before a destructive save in the operator and app is listed, each marked fixed here or follow-up | grep for `.ok().flatten()`, `_ => None`, `unwrap_or` on host replies in `selahcue-operator/src`, `selahcue-app/src`, `selahcue-desktop/src` | list in the PR description and the ClickUp handoff | PR description | PASS |
| C-009 | yes | Branch is up to date with `origin/main` and the Draft PR is open against `main` | `git rev-list --count HEAD..origin/main`; `gh pr view` | `0`; state DRAFT | PR #235 (https://github.com/First-Pavilion/selahcue/pull/235), isDraft true, base main; `rev-list --count` printed 0 | PASS |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused verification: the new operator tests (C-001 to C-003), the new `selahcue-app` tests (C-004, C-005), each mutation-verified by restoring the old behaviour and running the file with its siblings (never `--exact`), then restoring byte-identical (`cmp`).
- Broader regression verification: the full operator and workspace suites, fmt, clippy in every feature set the CI uses, the import guards and the launch-reachability check.
- Independent verifier: the orchestrator's four-reviewer gate (code, performance, security, QA) after this goal ends at a Draft PR.
- Required environment: macOS worktree `w2-r2`, cargo with `CARGO_INCREMENTAL=0`, `/opt/homebrew/bin` on `PATH`.

## Iteration ledger

### Iteration 1

- Target criterion: C-001 to C-005 (write the failing tests first)
- Hypothesis: every error from the existence check falls into the "no draft" arm, so a test with a failing load will see a save or a stage and a changed accepted draft.
- Change or investigation: tests first, with a scaffold that kept the old behaviour inside the new `ExistingDraft::from_load` (Err mapped to Absent) and a shell that kept `_ => Ok(None)`.
- Verifier executed: `cargo test -p selahcue-app --features server --test test_sermon_note_durability`; `cargo test regenerate_with_retention_tests` in the operator dir.
- Result: RED as predicted. selahcue-app: 3 of 26 failed (the host answered the failed load as `draft: None`; the host saved over an unreadable draft; the shell returned no error). Operator: 5 of 22 failed.
- New evidence: with the old host handlers the operator's own save went through the host's upsert; with the new host handlers the host refused it, so the accepted draft survived there but the operator still reported a persisted-nothing outcome. Two layers, two separate gaps.
- Decision: iterate

### Iteration 2

- Target criterion: C-001 to C-005
- Hypothesis: mapping the load error to `CheckFailed` in the operator, `Denied` in the host load and save handlers, and `Err` in the shell turns every new test green without touching an existing one.
- Change or investigation: the fix in `selahcue-operator/src/main.rs`, `selahcue-app/src/controller.rs`, `operator.rs`, a doc line in `sermon_note_store.rs`.
- Verifier executed: the same two commands, then the full suites.
- Result: GREEN. App file 26 passed; operator filter 22 passed; operator default 423, `dev-keys,openai-notes` 437 (baseline 432, +5), workspace 1903 passed and 5 ignored (baseline 1900, +3).
- New evidence: mutation matrix M1 to M5 (see the PR description), each restored byte-identical with `cmp`.
- Decision: iterate (gates, then PR)

### Iteration 3

- Target criterion: C-006 to C-009
- Hypothesis: the change touches no wire fixture and no frontend file; the gates stay green.
- Change or investigation: fmt, clippy in four configurations, the guard scripts, the survey of other `.ok().flatten()`-style spots.
- Verifier executed: see C-007 and C-008.
- Result: all exit codes 0. The separate `-p selahcue-app --features server` test run waited out a dip of free disk below the 12 GiB stop and then passed (355 passed, 1 ignored).
- New evidence: exit-code files in the scratchpad with prefix `w2-17tnw2b9af5-`.
- Decision: handoff (Draft PR; orchestrator runs the reviews)

## Risks and rollback

- Risks:
  - A generation is spent (and quota consumed) even though the save is then refused, because the check happens at save time. A check-before-generate preflight would avoid this; it is a follow-up.
  - `LoadSermonNoteDraft` now answers `Denied` on a store failure. A new operator talking to an old host still gets the old `draft: None` (that host cannot be fixed from here); an old operator talking to a new host now falls into its old `.ok().flatten()` and goes on to save, where the new host's save guard refuses if its own read of the existing draft fails.
  - The optional host-side guard (refuse `SaveSermonNoteDraft` over an existing draft unless the request says it is a replacement) is not done. It needs a new wire field, which touches the cross-language pinned fixtures; do it as its own ticket with the Dart fixtures changed in step.
  - The reply code is `transport`; the console shows "Couldn't generate notes — <message>". Accurate for "nothing was saved", slightly off for "the notes were generated". A dedicated code and label need a frontend change and are a follow-up.
- Rollback or recovery: revert the single PR. No data format, migration or wire change is involved, so no data needs recovery.

## Pause and escalation conditions

- Disk below 12 GiB free: stop and report (orchestrator).
- Any need to change a pinned wire fixture or the frontend: stop and ask (orchestrator).

## Final evaluation

- Validator command: `python3 scripts/validate_goal_contract.py docs/delivery/goals/17tnw2b9af5-regenerate-never-overwrites-accepted.md` and `python3 ~/.claude/skills/goal/scripts/validate_goal_contract.py` on the same file
- Validator result: both validators exit 0 (structural and completion modes)
- Independent verification result: pending (orchestrator runs the four-reviewer gate)
- Terminal state: handoff at a Draft PR (PR #235); not VERIFIED_COMPLETE until independent review passes
- Remaining failed or blocked criteria: none; independent review, QA and `make ci` are the orchestrator's
- ClickUp final evidence comment: posted on 17tnw2b9af5 at handoff
