# Goal Contract — 86akmfn54-requested-empty-caveat-persists

## Identity

- Goal ID: 86akmfn54-requested-empty-caveat-persists
- Parent goal ID: 86akc0tua
- Title: The "requested but nothing came back" caveat on a sermon-note draft survives being saved, reloaded, edit-saved and regenerated, in a stored format an older build can still read
- Role: backend-engineer
- Status: GATE_REVIEW
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86akmfn54
- Created: 2026-10-24
- Updated: 2026-10-24
- Maximum iterations: 8
- Independent verification required: yes

## Objective

A section (or the summary, or the scripture list) the operator asked the generator for and got nothing back keeps its visible caveat after the draft is persisted and reloaded, on every path that reloads a draft (`transcript_get`, `load_sermon_note_draft`, `update_sermon_note_draft`, confirm / discard of a regeneration, and an app restart), without a new column, migration or wire change, and without making any stored draft unreadable to the build that preceded this change.

## Baseline

**Verified** on `origin/main` at `09c69736`:

- `sections_to_persist` dropped every caveated empty section before it was saved, and the `Summary` / `Scripture references` caveats (which are not sections) were never stored. A failing test reproduced it: persist then reload gave no caveat where the fresh draft had one.
- Every reload path goes through `sermon_note_draft_json`.
- `sections_json` is an opaque text column capped at `MAX_SECTIONS_JSON_BYTES` (15,000) on writes; the codec lives in `selahcue-operator`. The pre-change reader is `serde_json::from_str::<Vec<NoteSectionInput>>(..).unwrap_or_default()`, which ignores unknown keys and treats anything unreadable as "no sections".
- The notes UI is `transcripts.js`; `load_sermon_note_draft` is registered but no dist JS calls it.

## Inputs and evidence sources

- ClickUp 86akmfn54 (description, acceptance criteria), 86akc0tua and PR #46 (the original caveat and Cody's finding that led to the drop)
- `selahcue-operator/src/main.rs`, `sermon_note_caveats.rs`, `dist/transcripts.js`, `selahcue-data/src/sermon_note_repo.rs`, `selahcue-lan/src/protocol.rs`
- Round 1 reviews of PR #221 (Cody, Shadow, Quinn) and the owner's test-coverage requirement 2b

## Scope

### In scope

- Store the caveat headings with the draft in `sections_json`; read them back into the same `DraftCaveat` a fresh generation raises (one source of truth).
- Honour a stored heading only while the content it names is still empty.
- The edit surface keeps a caveated empty section and reports the caveats it was shown.
- Bound the read path as tightly as the write path.

### Non-goals

- A new column, a migration, or a `selahcue-lan` wire change.
- Recovering caveats from rows saved while the old drop was live (the sections are already gone).
- An "add item" control in the edit form, and re-surfacing a pending regeneration after a restart (both pre-existing).

### Constraints

- A draft with no caveat is stored byte for byte as before.
- Stored format changes are additive only: new keys, never a new top-level shape for a draft that has sections.
- A caveat must never be the reason a draft is refused by the store.
- No sermon text in any error or log (FR-082, PR #217).

### Assumptions and unknowns

- ASSUMED: "requested" is advisory presentation state reported by the operator's own webview, honoured only while the content is empty and the heading still names a current section or one of the two fixed labels. It confers no authority. Owner: orchestrator.
- ASSUMED: rows over the write cap (from a build with the old 200,000-byte cap) should keep loading their sections exactly as before, without caveat work. Owner: reviewers.

## Dependencies and approvals

- None. No migration, no deployment step.

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | A requested-empty section / Summary / Scripture caveat survives persist and reload, through a real file and a restart | `cargo test -p selahcue-operator sermon_note_caveats` | exit 0, all pass | operator suite 348 passed (352 with `openai-notes`) on 6e819988 | PASS |
| C-002 | yes | The command hookups carry it: generate-persist seam, `update_sermon_note_draft` (list given, empty, omitted), load, confirm, discard | `cargo test -p selahcue-operator regenerate_with_retention_tests` | exit 0; mutants that bypass `draft_input_for` or pass `None` go red | PR #221 body | PASS |
| C-003 | yes | A draft with no caveat is stored byte for byte as before; an older build reads every section of a draft that has caveats | the literal-bytes test and the old-reader test | exit 0 | PR #221 body | PASS |
| C-004 | yes | A damaged `requested_empty` costs only the caveats; the read path is bounded (size check, first-byte shape, 256-entry result window) | wrong-typed, window and over-cap tests | exit 0; removing each bound turns one red | PR #221 body | PASS |
| C-008 | yes | The reader never shows fewer sections than the pre-change reader (a list of `NoteSectionInput`), whatever the caveat key looks like (duplicate key, deep nesting, 1e999, lone surrogate, tuple form) | the 42-row differential test against the old reader | exit 0; a mutant that decodes sections through flatten / `Value` again turns it red | PR #221 body | PASS |
| C-005 | yes | A caveat is dropped once its content is filled, and a stale heading never hides populated content | filled / namesake / sub-point tests | exit 0 | PR #221 body | PASS |
| C-006 | yes | The webview reports the caveats it shows (rename, Summary, Scripture, none) | `python3 scripts/operator_headless.py` | `=== 2290 checks, 0 FAIL ===` | exit 0, 2290 checks on 6e819988 | PASS |
| C-007 | yes | Repo gates | `make ci` (now includes the API and marketing gates) | exit 0, "ALL GREEN" | `make ci` exit 0 on 6e819988, the code of the final head (the commits after it edit only this file and the PR text); earlier: exit 0 on 47eabdd0 | PASS |

## Verification plan

- Focused verification: the operator tests above, plus mutation of every new test (each mutant applied alone, test goes red, restored).
- Broader regression verification: `make ci`.
- Independent verifier: Cody, Shadow, Quinn on the PR.
- Required environment: macOS, own `CARGO_TARGET_DIR`.

## Iteration ledger

### Iteration 1

- Target criterion: C-001
- Hypothesis: store the heading list inside `sections_json`; derive everything else.
- Change or investigation: new `sermon_note_caveats` module; reload through `sermon_note_draft_json`.
- Verifier executed: operator tests, headless gate, `make ci`.
- Result: pass; round 1 review found the stored envelope unreadable to an older build, the read path unbounded, two untested hookups.
- New evidence: reviewers showed `requested_empty.as_deref()` -> `None` left 278 tests green.
- Decision: iterate

### Iteration 2

- Target criterion: C-002, C-003, C-004
- Hypothesis: keep the array shape with one extra key; bound the read; test the commands.
- Change or investigation: see PR #221 round 1 remediation.
- Verifier executed: as above.
- Result: see PR #221 body.
- New evidence: mutation results in the PR body.
- Decision: iterate

### Iteration 3

- Target criterion: C-008
- Hypothesis: decode the sections with exactly the pre-change type and read the caveat headings in a separate best-effort pass, so the reader can never be stricter than the one it replaces.
- Change or investigation: removed the flatten / untagged-enum decode; headings now come from `serde_json::Value` (first section, 256-entry result window); differential test over 42 rows plus the object-shape duplicate-key case.
- Verifier executed: operator tests both ways, clippy both ways, headless, `make ci`, 10 further mutants.
- Result: all pass; round 2 reviewers: Cody APPROVE, Shadow and Quinn APPROVE WITH CONDITIONS (the condition is this iteration).
- New evidence: a mutant that decodes sections through flatten again fails 4 tests; one that couples sections to the heading pass fails 2.
- Decision: handoff

## Risks and rollback

- Risks: a stored `requested_empty` key on the first section is a convention an older build ignores; a draft within a few hundred bytes of the cap loses its caveat (not the draft); a Transcribe-tier LAN device can write any `sections_json` (it can only label genuinely empty content, never hide content).
- Rollback or recovery: revert the PR. Drafts written with the key stay readable by the reverted build (the key is ignored); no data migration is involved.

## Pause and escalation conditions

- A product decision on advisory-vs-authoritative "requested" or on rows over the old cap: orchestrator / owner.

## Final evaluation

- Validator command: `python3 ~/.claude/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/86akmfn54-requested-empty-caveat-persists.md`
- Validator result: OK (structural): satisfies the Goal Contract schema
- Independent verification result: round 1 three APPROVE WITH CONDITIONS; round 2 Cody APPROVE, Shadow and Quinn APPROVE WITH CONDITIONS (fixed in iteration 3); round 3 pending
- Terminal state: GATE_REVIEW
- Remaining failed or blocked criteria: none known
- ClickUp final evidence comment: on the ticket
