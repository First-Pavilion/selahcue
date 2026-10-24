# Goal Contract — 86ak196cr

## Identity

- Goal ID: 86ak196cr
- Parent goal ID: 86ajp072p
- Title: A deck link that crosses a machine boundary resolves to the same presentation or to the visible missing-content state, never to a different presentation
- Role: backend-engineer
- Status: GATE_REVIEW
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86ak196cr
- Created: 2026-10-24T12:00:00+01:00
- Updated: 2026-10-24T21:00:00+01:00
- Maximum iterations: 8
- Independent verification required: yes

## Objective

Give every presentation a globally distinguishable identity and make the boundary a plan link crosses between machines translate through it, so that importing a plan onto a populated library whose numbering overlaps the source never stages, previews or shows a presentation other than the one linked on the source machine (FINDING-LIB-07, RULE-LIB-XFER-01).

## Baseline

Verified on origin/main 09c69736 (2026-10-24):

- `DeckLibrary::mint_id` (`selahcue-operator/src/deck_library.rs`) is a per-library counter from 1; `ItemContent::Deck { deck_id, .. }` (`selahcue-core/src/plan.rs`) stores only that number; the operator webview resolves a link with `planDecks.some(d => d.id === link.id)`.
- No shipped path carries a deck link across machines: the wire command `ImportPlan` (selahcue-lan protocol / `LiveController::import_plan`) accepts only kind, title, owner and planned seconds; the FR-139 plan bundle (86ak0qn15) is unbuilt. The defect is therefore latent and is switched on by the first plan-transfer feature.
- Reproduced with a two-library test that carries a link the only way the shipped code can (plan codec round trip, then look the number up in the receiving library): the receiving library shows "Guest Speaker - Notes" for a link to "Communion" (evidence C-001).

## Inputs and evidence sources

- ClickUp 86ak196cr (description, acceptance criteria, no comments); ClickUp 86ak0qn15 (FR-139 story)
- `docs/product/DOMAIN-library-organisation.md` section 9.2; `docs/architecture/adr/ADR-0024-presentation-import.md`
- `docs/architecture/adr/ADR-0031-cross-machine-deck-identity.md` (this change)
- `implementation/desktop/crates/selahcue-core/src/plan.rs`, `selahcue-present/src/deck.rs`, `selahcue-operator/src/deck_library.rs`, `selahcue-data/src/deck_repo.rs`

## Scope

### In scope

- A `DeckUid` identity per presentation, stored with the deck, minted on create/adopt/duplicate, backfilled and persisted for existing decks on load.
- A pure export/import rule (`selahcue_core::deck_ref`) and the library seam that uses it (`DeckLibrary::export_link`, `import_link`).
- Tests for happy paths and edge cases, with mutation results.
- ADR-0031 and the contract FR-139 must follow; a comment on 86ak0qn15 adding the non-empty-destination case to its test matrix.

### Non-goals

- Building the FR-139 plan bundle or any new import command (86ak0qn15).
- Changing how local plans store or resolve links, the LAN wire protocol, the Dart model or the webview.
- Media ids (same per-library numbering; follow-up), library grouping, library sync.
- Making a missing link heal later or survive re-export (documented limit; follow-up).

### Constraints

- Local plans and links created before this change open and resolve exactly as before (no plan-row change, no wire change, byte-identical plan codec).
- Fail closed: any case the identity cannot prove is the missing-content state.
- Memory bounded: import output per link is bounded; nothing accumulates between calls.
- No `Co-Authored-By` trailers; one ticket, one branch, one PR; PR opened as Draft.

### Assumptions and unknowns

- ASSUMED: the fix may be settled at the import boundary rather than by changing every resolution site (ADR-0031 "Options considered"); owner/architect review decides whether the "uid everywhere" option is wanted now.
- ASSUMED: a uid is an unauthenticated claim (ADR-0031 "A uid is a claim"); no ingress may keep a foreign uid until a trust decision is recorded, so `adopt` always mints. Validation owner: Security Reviewer.
- ASSUMED: copying a SQLite store between machines and attaching two differently-stocked operators to one host are out of scope (ticket: unsupported; 86ajy02zq).
- Validation owner for both: Software Architect review of ADR-0031.

## Dependencies and approvals

- 86ak0qn15 (FR-139) consumes the seam; it is not blocked by this change and is not completed by it.
- No new product decision is needed: the unresolved state is the existing missing-content state named in the ticket.

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`. **Evidence stamps:** base `09c69736`; Rust gates and focused tests at the tested head `e0be500e` (the merge of origin/main into `fd8fe4eb`; a docs-only commit follows it); the one full `make ci` at `4a719164`, not re-run since (the PR CI runs it). This contract is at GATE_REVIEW, not VERIFIED_COMPLETE: row C-013 (independent verification) stays PENDING until the orchestrator confirms the round 2 conditions.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | The defect reproduces: carrying a link by number into an overlapping library shows a different presentation | At the base SHA the by-number form of the acceptance test failed (message in the PR body); at the head `characterisation_lookup_by_number_alone_still_shows_a_different_presentation` pins the same wrong-deck behaviour | red at base naming the wrong deck; the characterisation passes at head | PR body, red evidence at base `09c69736`; `characterisation_lookup_by_number_alone_still_shows_a_different_presentation` passes at `e0be500e` | PASS |
| C-002 | yes | Two overlapping libraries: every imported link is the same presentation or explicitly missing, never a different one | operator `identity_tests` overlap tests | pass | operator whole-crate run at `e0be500e` (`identity_tests` overlap tests: `a_link_carried_through_the_boundary_never_shows_a_different_presentation`, `every_link_into_an_overlapping_populated_library_is_missing_never_another_deck`, `a_mixed_plan_binds_each_link_on_its_own_merits`) | PASS |
| C-003 | yes | IN-PROCESS ONLY: a presentation present in both libraries under different numbers resolves to the receiving library's own deck (decks moved between two libraries with `adopt_trusted_identity`) | operator `identity_tests` | pass | operator `identity_tests::a_presentation_present_on_both_machines_under_different_numbers_resolves_to_the_receivers_own` at `e0be500e` (in-process only; see C-014) | PASS |
| C-004 | yes | A presentation absent from the receiving library is the missing-content state carrying its last known name | operator + core tests | pass; `unresolved_content` lists the item | `identity_tests::a_link_carried_through_the_boundary_...` (`unresolved_content` lists the item) and core `test_deck_ref` at `e0be500e` | PASS |
| C-005 | yes | Existing decks are backfilled with a uid once, persisted to the row they were read from only, and stable across reloads; every stored deck is unchanged apart from the uid (and, for a row whose key equals its healed name, the healed name and number); a row whose key differs from its deck name is never rewritten; the backfill stops at the first failed write | operator legacy-row equivalence, row-key, blank-name and failed-write tests | pass | operator `decks_stored_before_identities_existed_...`, `the_backfill_never_overwrites_a_row_other_than_the_one_it_read`, the unreadable-row, key-spelling, blank-name and failed-write tests at `e0be500e` | PASS |
| C-006 | yes | Duplicate gets a new uid; rename, store, replace, restore keep it; `adopt` and `adopt_with_policy` always mint a fresh uid (a hostile deck cannot choose its identity); `adopt_trusted_identity` keeps a free uid and never a held one; no two decks share one | operator library tests | pass | operator `identity_tests` adopt, duplicate, store, replace and restore tests at `e0be500e`; `adopt_trusted_identity` is `#[cfg(test)]` (a production call fails to compile, verified) | PASS |
| C-007 | yes | Hostile/malformed identity or label input never panics, never reaches the library, and output is bounded | core `test_deck_ref` | pass | core `test_deck_ref` (27 tests) at `e0be500e` | PASS |
| C-008 | yes | A corrupt stored uid never costs the operator the deck | present `test_deck` + operator heal test | pass | present `test_deck::a_damaged_uid_costs_the_deck_its_identity_but_never_the_deck` and operator `healing_never_leaves_two_decks_...` at `e0be500e` | PASS |
| C-009 | yes | Wire and plan storage unchanged | `git diff origin/main` shows no change to the plan encode/decode, the wire views, `selahcue-lan`, the Dart app or `dist/`; `plan.rs` changes one added `use` line, one visibility keyword and one label-carry guard for the unresolved number; `selahcue-lan` protocol tests pass | no change to encode/decode or the wire views; pass | `git diff origin/main` touches no file under `selahcue-lan`, the Dart app or `dist/` and no plan encode/decode or wire view; `plan.rs` changes one added `use` line, one visibility keyword and one label-carry guard for the unresolved number | PASS |
| C-010 | yes | Each guard test goes red when its guarded behaviour is mutated | mutation table in the PR body | every mutation caught | PR body mutation results: round 1 (34), round 2 (12 plus a re-run), round 3 (6 plus the earlier ones re-run against the changed code); every one turns a named test red | PASS |
| C-011 | yes | `cargo fmt --check`, clippy `-D warnings`, workspace and operator tests, and `make ci` pass | commands in PR body | exit 0 | fmt, clippy `-D warnings`, core+present and whole-operator tests, `import_guards.sh` and launch reachability at `e0be500e` (exit codes in the PR body); full `make ci` green at `4a719164`, not re-run since | PASS |
| C-012 | yes | FR-139 test matrix carries the populated-destination case and the contract | A comment with the matrix addition and the contract was posted on 86ak0qn15 by the author on 2026-10-24 (before the adopt change; ADR-0031's contract section supersedes it). The orchestrator updates the ticket's description and acceptance criteria. | comment exists; orchestrator update pending | The author posted a comment with the matrix addition and the contract on 86ak0qn15; the orchestrator has since corrected it (its last bullet begins "CORRECTED after PR #222 review round 1") and appended the deck-link requirements to the ticket description. ADR-0031's contract section is the source of truth. | PASS |
| C-013 | yes | Independent review requirement satisfied | Cody, Shadow, Quinn (orchestrator dispatches) | verdicts posted | review report | PENDING |
| C-014 | no | Ticket acceptance criterion 3, in production: the same presentation travelling with a plan resolves on another machine | needs a feature that carries a uid-bearing deck between machines; none exists (`ImportItemView` has no deck, the FR-139 bundle does not carry decks, there is no deck export). Until then every cross-machine deck link imports as missing, the safe direction. | DEFERRED to that feature, not met | ADR-0031 "What this does and does not enforce" | BLOCKED |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused verification: `cargo test -p selahcue-core --test test_deck_ref`; `cargo test -p selahcue-present --test test_deck`; operator `cargo test ... deck_library`.
- Broader regression verification: `cargo test --manifest-path implementation/desktop/Cargo.toml`; `cargo clippy ... --all-targets -- -D warnings` for workspace and operator; `make ci`.
- Independent verifier: Cody (code), Shadow (security), Quinn (QA), Vera (performance) via the orchestrator.
- Required environment: macOS dev machine, operator built into a private CARGO_TARGET_DIR.

## Iteration ledger

### Iteration 1

- Target criterion: C-001 .. C-009
- Hypothesis: translating at the boundary through a per-deck uid satisfies the acceptance criteria without touching the live path.
- Change or investigation: see PR.
- Verifier executed: see PR.
- Result: see PR.
- New evidence: see PR.
- Decision: gate-review

## Risks and rollback

- Risks: a downgrade-then-upgrade can drop a deck's uid (fails closed to missing, never wrong); `getrandom` becomes a non-optional operator dependency.
- Rollback or recovery: revert the PR. The only stored change is an optional `uid` key inside `deck_json`, which older builds ignore; nothing else reads it.

## Pause and escalation conditions

- Architect asks for "uid everywhere" in this ticket instead of a follow-up: escalate to the owner, the wire and webview change becomes a separate, larger ticket.
- A reviewer finds a reachable path that moves a plan without the boundary: escalate (a second fix, not a widening of this one).

## Final evaluation

- Validator command: `python3 ~/.claude/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/86ak196cr-deck-identity.md`
- Validator result: structural check exits 0; with `--completion` (the flag in this validator version) it fails only on C-013 (independent verification pending), which is the expected GATE_REVIEW state
- Independent verification result: round 1 Cody APPROVE WITH CONDITIONS, Shadow PASS WITH CONDITIONS, Quinn PASS WITH CONDITIONS (fixed); round 2 Cody APPROVE, Shadow APPROVE WITH CONDITIONS, Quinn APPROVE WITH CONDITIONS (conditions fixed in the round 3 push, awaiting the orchestrator's confirmation)
- Terminal state: GATE_REVIEW
- Remaining failed or blocked criteria: C-013 (pending confirmation); C-014 BLOCKED by design (needs a deck-carrying feature that does not exist; DEFERRED, not met)
- ClickUp final evidence comment: the orchestrator posts it
