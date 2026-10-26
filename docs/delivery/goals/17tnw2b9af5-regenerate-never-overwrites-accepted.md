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
- The JSON-decoding failure class is covered at the `from_load` unit boundary, not end to end: `Backend::load_sermon_note_draft` turns every `TransportError` into a `String` through one `.map_err(|e| e.to_string())`, and a scripted `ControlServer` host cannot send a malformed frame. A refusal from a real host reaches `from_load` as "expected sermon_note_draft, got: denied", the same shape as a wrong-type reply.

## Dependencies and approvals

- None blocking. The orchestrator runs the four-reviewer gate, marks the PR ready and moves the ticket; this goal ends at a Draft PR.

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | With a store whose load fails, `persist_generated_draft` reports the check as failed, makes no save or stage call, the accepted draft reads back identical, and a regeneration staged EARLIER is still the pending one (not replaced) | `cargo test --no-fail-fast` in the operator dir, default and `--features dev-keys,openai-notes` (tests in `regenerate_with_retention_tests`) | the new tests pass; the same tests are RED with the old `.ok().flatten()` (M1), with the failed-check arm falling into the save arm (M2) and with a "stage when unsure" fallback (M6) | Operator default 423 passed, `dev-keys,openai-notes` 437 passed, 0 failed (exit 0 both). RED: first run before the fix 5 of 22 failed; M1 4 RED; M2 4 RED; M6 3 RED, where the staged-survives assertion fires first (`left: Some("Regenerated notes")`, `right: Some("Earlier staged notes")`) | PASS |
| C-002 | yes | Over the real pinned-TLS link, a host that answers the load with the wrong reply type, and one that answers `Denied`, each leave the host receiving zero save and zero stage commands; a conforming `draft: None` reply still reaches the save (positive control); a real host controller with an unreadable store gets the same result end to end | same command, tests `a_host_that_cannot_answer_the_check_gets_no_save_and_no_stage_over_the_real_link` and `a_real_host_storage_failure_reaches_the_operator_as_a_failed_check` | pass; control passes; RED under M1, M2, M3, M6 | same runs as C-001; M3 (host answers a failed load as `draft: None`) 3 operator tests RED | PASS |
| C-003 | yes | The reply the operator console receives for a failed check is `ok: false`, code `transport` (one of the five frozen codes), the exact constant message, no `draft` and no `transcript_id` key, and the clamp echoed. That no error text can leak is held STRUCTURALLY (`ExistingDraft::CheckFailed` and `ExistingDraftCheckFailed` are unit types, the message is a `const`); the test pins the constant and does not claim more | same command, test `a_failed_check_is_reported_as_not_saved_with_a_fixed_label_only_message` | pass; RED under M1, M2, M3, M5 | same runs as C-001. An earlier draft of this test also asserted that a planted marker string was absent from the reply; the marker was planted behind the host, which drops store text, so it could never reach the operator and the assertion passed whatever the operator did. It was removed | PASS |
| C-004 | yes | The host answers a failed store load with `Denied`, not `draft: None`, and refuses a save when it cannot read the existing draft; an absent draft still answers `draft: None` and a first save still works | `cargo test -p selahcue-app --features server --test test_sermon_note_durability`; whole crate via `cargo test -p selahcue-app --features server --no-fail-fast` and `cargo test --workspace --no-fail-fast` | new tests pass (26 in the file); RED against the old handlers (M3, M4) | file 26 passed; crate 355 passed, 1 ignored, 0 failed; first run before the fix 3 of 26 RED; M3 2 RED; M4 1 RED | PASS |
| C-005 | yes | `Backend::Local` distinguishes a failed load from "no draft" (`OperatorShell::load_sermon_note_draft` returns `Result`) | test `the_in_process_shell_tells_a_failed_load_from_no_draft` (pins the constant error text) and the operator Local test | pass; RED under M5 | M5 1 selahcue-app RED, 2 operator RED | PASS |
| C-006 | yes | No wire fixture changed and the frontend is untouched | `git diff --stat origin/main -- implementation/mobile implementation/desktop/crates/selahcue-lan implementation/desktop/crates/selahcue-operator/dist` | empty | empty output, exit 0 | PASS |
| C-007 | yes | Format, lint, tests and guards are green with exit codes captured to files | `cargo fmt --check` (workspace and operator), `cargo clippy --all-targets -D warnings` (operator: default, `openai-notes`, `dev-keys,openai-notes`; workspace), `cargo test --no-fail-fast` (operator default and `dev-keys,openai-notes`; workspace), `cargo test -p selahcue-app --features server --no-fail-fast`, `sh scripts/import_guards.sh`, `python3 scripts/check_launch_reachability.py` | every exit code 0 | all exit 0 on the review-round head: fmt 0/0, clippy 0/0/0/0, operator tests 423 and 437 passed, `-p selahcue-app --features server` 355 passed and 1 ignored, workspace 1903 passed and 5 ignored (baseline 1900), import guards 0, launch reachability 0 | PASS |
| C-008 | yes | Every other host-reply swallow before a destructive save in the operator and app is listed, each marked fixed here or follow-up | grep for `.ok().flatten()`, `_ => None`, `unwrap_or` on host replies in `selahcue-operator/src`, `selahcue-app/src`, `selahcue-desktop/src` | list in the PR description and the ClickUp handoff | PR description, section "What is and is NOT fixed" | PASS |
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
- New evidence: mutation matrix M1 to M5 (see the PR description and C-001 to C-005), each restored byte-identical with `cmp`.
- Decision: iterate (gates, then PR)

### Iteration 3

- Target criterion: C-006 to C-009
- Hypothesis: the change touches no wire fixture and no frontend file; the gates stay green.
- Change or investigation: fmt, clippy in four configurations, the guard scripts, the survey of other `.ok().flatten()`-style spots.
- Verifier executed: see C-007 and C-008.
- Result: all exit codes 0. The separate `-p selahcue-app --features server` test run waited out a dip of free disk below the 12 GiB stop and then passed (355 passed, 1 ignored).
- New evidence: the exit codes and counts are recorded inline in the predicate table above.
- Decision: handoff (Draft PR; orchestrator runs the reviews)

### Iteration 4

- Target criterion: C-001 to C-003, C-008 (review round on the same branch: Cody PASS WITH CONDITIONS, Shadow PASS WITH CONDITIONS and signs off on security)
- Hypothesis: two assertions were vacuous (the discard-read pending check; the planted-marker checks), so a regression could pass them; replacing them with a stronger check turns a "stage when unsure" fallback RED.
- Change or investigation: the shared helper now stages an earlier regeneration first and, after the failed check, confirms and asserts the EARLIER staged title is what was promoted; the marker assertions are removed; the `from_load` test uses the real refusal text; the `ExistingDraft` doc no longer overstates what the compiler enforces; the contract paths are inline evidence.
- Verifier executed: the full gate list again, plus mutation M6 ("stage when unsure" in the failed-check arm).
- Result: GREEN on the same counts; M6 RED, the new staged-survives assertion firing first; M1 restored RED. Each restored byte-identical with `cmp`.
- New evidence: see C-001 to C-003.
- Decision: handoff

## Risks and rollback

- Risks:
  - A failed check now returns `ok: false` with no draft, so the GENERATED TEXT IS DISCARDED. Before this change the console showed it, unsaved. The generation (and its quota) is already spent when the save is refused, because the check happens at save time.
  - A persistent failure (for example a host row that cannot decode, `row_to_record` in `selahcue-data/src/sermon_note_repo.rs` about line 406) makes EVERY Regenerate spend another generation and show the same error. Only a check-before-generate preflight fixes that: https://app.clickup.com/t/17tnw2b9dq9.
  - The console clears its result box on any error (`showGenError` calls `genResultEl()`, `transcripts.js` about lines 1060 to 1065), so a draft shown before Regenerate disappears from the screen. "Your current notes are unchanged" is true in storage, not on screen, until the transcript is reopened. This applies to every error code and is not a regression.
  - VERSION SKEW, both directions. The protocol version number is unchanged by design, so neither side can detect the other's age; the likely case is an old host process outliving an app update.
    - NEW operator with an OLD host: the old host answers a store read failure with `draft: None` and its save guard uses `.ok().flatten()`, so the new operator sees "no draft", saves, and the upsert (`sermon_note_repo.rs` about lines 324 to 339) overwrites. A corrupt pending slot is a realistic trigger: `row_to_record` fails while the upsert still succeeds.
    - OLD operator with a NEW host: the new guard (`controller.rs` about lines 3543 to 3546) covers only a failed read on the HOST side. A failure on the operator side (wrong reply type, decode error) still becomes "no draft" in the old operator; the host then reads a present AI draft, the guard passes, and the upsert replaces it. So this change protects an older operator much less than it may seem.
    - The real fix is https://app.clickup.com/t/17tnw2b9dqa: the host refuses `SaveSermonNoteDraft` over an existing accepted draft.
  - Open question for that follow-up: Cody's review suggests no new wire field is needed. The only production caller of `SaveSermonNoteDraft` is the operator's first-save arm in `persist_generated_draft` (verified by grep over operator, app and desktop; the mobile app has no reference), because edits use `UpdateSermonNoteDraft` and regenerates use `StageSermonNoteRegeneration`. If so, the host can refuse every Save over an existing draft. That would change the positive control of this PR's own host test `a_save_is_refused_when_the_existing_draft_cannot_be_read` (it saves over an existing draft once reads work) and would make the Save handler's no-downgrade guard redundant. Left to that ticket.
  - NOT FIXED here, so nobody reads this as closing every overwrite route: https://app.clickup.com/t/17tnw2b9dq6 (after a failed regenerate the console can show the unsaved AI draft as the saved notes with an Edit button; saving it replaces the accepted draft; a pre-existing second route via `ok: true` with `transcript_id: null`), and https://app.clickup.com/t/17tnw2b9dq7 (sibling spots: the host's write-then-read-back, `sweep_orphaned_transcripts`, the `update_sermon_note_draft` caveat read, and a `transcript_id` mismatch defence in depth).
  - `LoadSermonNoteDraft`'s doc in `selahcue-lan/src/protocol.rs` does not say a store failure now answers `Denied`. Left alone on purpose: PR #234 edits that file and this PR makes no `selahcue-lan` change.
  - The reply code is `transport`; the console shows "Couldn't generate notes — <message>", slightly off for "the notes were generated but not saved". Any unknown code already renders through the same default arm with no frontend change; the real obstacle to a dedicated code is the frozen five-code contract (C-007 of 86akbzxjg's contract).
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
