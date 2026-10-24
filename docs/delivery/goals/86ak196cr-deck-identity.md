# Goal Contract — 86ak196cr

## Identity

- Goal ID: 86ak196cr
- Parent goal ID: 86ajp072p
- Title: A deck link that crosses a machine boundary resolves to the same presentation or to the visible missing-content state, never to a different presentation
- Role: backend-engineer
- Status: ACTIVE
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86ak196cr
- Created: 2026-10-24T12:00:00+01:00
- Updated: 2026-10-24T12:00:00+01:00
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
- ASSUMED: copying a SQLite store between machines and attaching two differently-stocked operators to one host are out of scope (ticket: unsupported; 86ajy02zq).
- Validation owner for both: Software Architect review of ADR-0031.

## Dependencies and approvals

- 86ak0qn15 (FR-139) consumes the seam; it is not blocked by this change and is not completed by it.
- No new product decision is needed: the unresolved state is the existing missing-content state named in the ticket.

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | The defect reproduces: carrying a link by number into an overlapping library shows a different presentation | `a_link_carried_by_number_never_shows_a_different_presentation` run on the unmodified library at the base SHA | test FAILS naming the wrong deck | PR body, "red" evidence | PENDING |
| C-002 | yes | Two overlapping libraries: every imported link is the same presentation or explicitly missing, never a different one | operator `identity_tests` overlap tests | pass | operator test output | PENDING |
| C-003 | yes | A presentation present in both libraries under different numbers resolves to the receiving library's own deck | operator `identity_tests` (identity travels via adopt) | pass | operator test output | PENDING |
| C-004 | yes | A presentation absent from the receiving library is the missing-content state carrying its last known name | operator + core tests | pass; `unresolved_content` lists the item | test output | PENDING |
| C-005 | yes | Existing decks are backfilled with a uid once, persisted, and stable across reloads; ids, names, slides and plan links unchanged | operator legacy-row equivalence tests | pass | test output | PENDING |
| C-006 | yes | Duplicate gets a new uid; rename, store, replace, restore keep it; adopt never keeps a held uid; no two decks share one | operator library tests | pass | test output | PENDING |
| C-007 | yes | Hostile/malformed identity or label input never panics, never reaches the library, and output is bounded | core `test_deck_ref` | pass | test output | PENDING |
| C-008 | yes | A corrupt stored uid never costs the operator the deck | present `test_deck` + operator heal test | pass | test output | PENDING |
| C-009 | yes | Wire and plan storage unchanged | `git diff origin/main` touches no protocol/fixture/plan-codec file; `selahcue-lan` protocol tests pass | empty diff on those paths; pass | PR body | PENDING |
| C-010 | yes | Each guard test goes red when its guarded behaviour is mutated | mutation table in the PR body | every mutation caught | PR body | PENDING |
| C-011 | yes | `cargo fmt --check`, clippy `-D warnings`, workspace and operator tests, and `make ci` pass | commands in PR body | exit 0 | PR body | PENDING |
| C-012 | yes | FR-139 test matrix carries the non-empty-destination case | comment on 86ak0qn15 | comment posted | ClickUp | PENDING |
| C-013 | yes | Independent review requirement satisfied | Cody, Shadow, Quinn (orchestrator dispatches) | verdicts posted | review report | PENDING |

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
- Validator result: PENDING
- Independent verification result: PENDING
- Terminal state: PENDING
- Remaining failed or blocked criteria: PENDING
- ClickUp final evidence comment: PENDING
