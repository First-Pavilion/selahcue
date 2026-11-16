# Goal Contract — TASK-17tnw2axpru

## Identity

- Goal ID: TASK-17tnw2axpru
- Parent goal ID: NONE
- Title: Bounded persisted transcript reads for note timestamps
- Role: backend-engineer
- Status: ACTIVE
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/17tnw2axpru
- Created: 2026-11-13
- Updated: 2026-11-13
- Maximum iterations: 8
- Independent verification required: yes

## Objective

A note-draft reload or edit-save reads at most MAX_LINK_SEGMENTS raw segment rows for timestamp linking, preserving existing valid-data timestamp outputs and full-transcript consumers.

## Baseline

Merged main 218e14140e8df0e1089dbbc3ce09096f26e08310. The matcher scans only its first 5,000 segments, but transcript_segments_for calls transcript_repo::load and materializes the entire transcript plus corrections/detections. Live ClickUp scope and zero comments were verified on 2026-11-13.

## Inputs and evidence sources

- https://app.clickup.com/t/17tnw2axpru
- implementation/desktop/crates/selahcue-data/src/transcript_repo.rs
- implementation/desktop/crates/selahcue-operator/src/main.rs
- implementation/desktop/crates/selahcue-core/src/providers.rs
- docs/superpowers/plans/2026-11-13-bounded-note-transcript-reads.md

## Scope

### In scope

- Ordered segment-only bounded SQL read and note timestamp helper integration.
- Large-fixture row-bound and output-parity regression evidence.

### Non-goals

- Memoization ticket 17tnw2axprv, changed matching policy, transcript truncation, new dependencies or schema, Windows CI setup.

### Constraints

- MAX_LINK_SEGMENTS = 5_000, referenced from core.
- Full transcript generation/export remains uncapped.
- No raw speech in diagnostics; best-effort timestamp failures remain graceful.
- One ticket and one PR; independent review and full local make ci before merge.

### Assumptions and unknowns

- UNKNOWN: physical 4 GB Windows performance; test operator/device not arranged. Local deterministic row bounds prove this change's work limit but not device qualification.

## Dependencies and approvals

- Source prerequisite 86akgqdw0 merged; live ticket has no unresolved execution dependency.
- User authorized subagent implementation, local CI, reviewed PR merge and linked task to QA.
- User explicitly cancelled Windows CI setup.

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | SQL read materializes only the requested ordered prefix from 20,001+ rows | data tests and bound mutation | cap and order assertions pass; unbounded mutation fails | 41/41 data tests. The 20,001-row fixture returned the same first 5,000 as the full read. Removing LIMIT failed on the malformed tail and restoring it passed. | PASS |
| C-002 | yes | Note timestamp JSON and full-transcript consumers retain behavior | core and operator/data regression tests | identical prefix-derived timestamps; complete full reads; graceful errors | Data 41/41 and core 19/19 passed. All 33 operator retention tests and 8 codec tests passed with default features. | PASS |
| C-003 | yes | Full local CI passes on merge candidate source | make ci | exit 0 with audit included | PENDING | PENDING |
| C-004 | yes | Independent review has no unresolved blocking findings | Cody, Shadow, Quinn, Vera plus final branch review | PASS on final source | PENDING | PENDING |
| C-005 | yes | Reviewed source merged and ticket handed to QA | live GitHub/ClickUp readback | merge tree/ancestry verified; exact qa status | PENDING | PENDING |

## Verification plan

- Focused verification: 20,001+ database rows, prefix equality, malformed tail, mutation proof, timestamp JSON equality and missing data.
- Broader regression verification: full local make ci with RustSec audit, once on final candidate.
- Independent verifier: Cody, Shadow, Quinn, Vera; final whole-branch review.
- Required environment: existing macOS local CI toolchain; Windows qualification explicitly not claimed.

## Iteration ledger

### Iteration 1

- Target criterion: C-001, C-002
- Hypothesis: SQL LIMIT and segment-only loading remove unused allocations without changing the eligible prefix.
- Change or investigation: planned isolated ticket branch from current main.
- Verifier executed: live source/ticket read.
- Result: baseline confirmed.
- New evidence: implementation plan.
- Decision: iterate

### Iteration 2

- Target criterion: C-001, C-002
- Hypothesis: The bounded reader preserves the matcher's original input and avoids decoding rows it cannot use.
- Change or investigation: Added the SQL prefix reader, shared the raw row decoder with the full loader, and wired persisted-draft timestamp linking to the core cap.
- Verifier executed: Data and core focused suites, operator timestamp filter, and a temporary SQL LIMIT removal.
- Result: Data 41/41 and core 19/19 passed. Without LIMIT the focused mutation failed on the first excluded row. After restoration it passed. All 33 operator retention tests and 8 codec tests passed with default features.
- New evidence: The API red run failed only because the prefix reader was absent. The pre-change operator run stopped during dependency compilation under host paging pressure.
- Decision: iterate

## Risks and rollback

- Risks: accidentally limiting full consumers or changing segment ordering; covered by regression tests.
- Rollback or recovery: revert the scoped PR; persisted data is untouched.

## Pause and escalation conditions

- Active host swap pressure: stop heavy tests and reassess resources without restarting Windows setup.
- New acceptance-policy requirement or destructive operation: report before proceeding.

## Final evaluation

- Validator command: python3 /Users/m.oluwole/.agents/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/17tnw2axpru-bounded-note-transcript-reads.md --completion
- Validator result: PENDING
- Independent verification result: PENDING
- Terminal state: ACTIVE
- Remaining failed or blocked criteria: C-003 through C-005 pending
- ClickUp final evidence comment: PENDING
