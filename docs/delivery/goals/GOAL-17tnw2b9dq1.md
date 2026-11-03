# Goal Contract — GOAL-17tnw2b9dq1

## Identity
- Goal ID: GOAL-17tnw2b9dq1
- Parent goal ID: NONE
- Title: Error diagnostics retain categories without peer or stored values
- Role: backend-engineer
- Status: GATE_REVIEW
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/17tnw2b9dq1
- Created: 2026-11-04
- Updated: 2026-11-04
- Maximum iterations: 4
- Independent verification required: yes

## Objective
Remove the ticket's known value-quoting diagnostics while preserving useful error categories and normal behavior.

## Baseline
Verified main 9deb975872eda7f16e67b4bee2c00dc8707af18b derives TransportError Debug, embeds stored item-kind/retention values in corruption errors, and formats theme serde messages. Ticket status changed to in progress and read back; start comment 1400430000278178. These are existing low/info hygiene paths, not a demonstrated production exploit.

## Inputs and evidence sources
- Live ClickUp task and its five scoped items; no dependencies or comments at start.
- tls.rs, plan_repo.rs, transcript_repo.rs, operator preview_theme and webview caller, Dart session/model decode paths.

## Scope
### In scope
- Redact WebSocket Debug payloads, stored corruption strings and theme decode values; update five stale comments.
- Sentinel-based Rust regressions and a short Dart error audit, with focused correction only if directly demonstrated.
### Non-goals
- Lockfile or protocol changes, new mobile features, production deployment or installer packaging.
- No permissions, transactions, jobs, migrations, tenancy, network destinations or data ownership change; those backend criteria are inapplicable to this scoped diagnostic change.
### Constraints
- One owned worktree and branch; do not touch the user's modified primary mobile lockfile or other agents' work.
- Preserve error category/status/position and original control flow.
### Assumptions and unknowns
- UNKNOWN: whether Dart cast/decoder errors quote incoming values; settle with source and a focused real-runtime probe.

## Dependencies and approvals
- User authorized implementation/public PR and root-owned four-review/merge/QA workflow. Root owns integration gates.

## Completion predicate
All mandatory rows must be PASS for VERIFIED_COMPLETE.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | WebSocket Debug omits peer header/body sentinel and retains status | LAN sentinel regression plus crate suite | Regression red before fix, green after; suite exits 0 | docs/delivery/evidence/17tnw2b9dq1.md | PASS |
| C-002 | yes | Corrupt item-kind and retention diagnostics omit stored sentinel | Real database regression and data crate suite | Errors retain fixed category, omit sentinel; tests exit 0 | docs/delivery/evidence/17tnw2b9dq1.md | PASS |
| C-003 | yes | Theme decode error omits invalid values and preserves category/position; stale comments corrected | Operator regression and lint/test; webview call-path inspection | Sentinel absent; valid theme still decodes; comments accurate | docs/delivery/evidence/17tnw2b9dq1.md | PASS |
| C-004 | yes | Dart decode audit settles value quoting with source and runtime evidence | Focused Dart probe and model/session tests if affected | Observed errors documented; no unaddressed directly scoped leak | docs/delivery/evidence/17tnw2b9dq1.md | PASS |
| C-005 | yes | Required independent reviews and integration gates pass | Cody, Shadow, Quinn, Vera and hosted CI | All four pass at frozen source; root verifies merge and QA | PR and ClickUp handoff | PENDING |

## Verification plan
- Focused verification: sentinel errors through actual production functions and database reads, no source-spelling assertions.
- Broader regression verification: cargo test for touched crates, fmt and clippy; hosted applicable matrix.
- Independent verifier: root dispatches Cody, Shadow, Quinn and Vera.
- Required environment: local Rust/macOS and Dart, no live providers; normal hosted source CI.

## Iteration ledger
### Iteration 1
- Target criterion: C-001 through C-004.
- Hypothesis: formatting only safe metadata instead of value-bearing inner messages removes the known quoting paths without changing control flow.
- Change or investigation: trace production callers and write sentinel regressions before implementation.
- Verifier executed: real LAN, database and theme sentinel tests; actual Dart model-cast probe.
- Result: each known Rust value-quoting path failed the sentinel contract. Valid theme positive control passed. Six corrected Dart cast fixtures all omitted sentinel values; no mobile change justified.
- New evidence: detailed command outcomes and initial fixture corrections in docs/delivery/evidence/17tnw2b9dq1.md.
- Decision: iterate.

### Iteration 2
- Target criterion: C-001 through C-004.
- Hypothesis: safe status/category/position and fixed corruption labels satisfy diagnostics without changing behavior.
- Change or investigation: manual Ws Debug using existing Display, fixed stored-value errors, category/position-only theme error, five historical comment corrections.
- Verifier executed: complete LAN229 passed/4 ignored, data177 passed, operator457 passed/1 ignored; both root fmt checks, touched-crate clippy warnings denied, diff check. All commands completed exit0.
- Result: C-001 through C-004 PASS; C-005 remains pending independent reviewers and hosted CI.
- New evidence: branch integrated current main d9fcd524634ab9328231b6d984bd16be11d2ea78, 0 behind. No active verification process, dependency/lock/mobile production changes or deployment.
- Decision: gate-review.

## Risks and rollback
- Risks: overly broad formatting can remove useful categories; tests must retain category/status/position.
- Rollback or recovery: revert this isolated PR, no schema or persisted-data change.

## Pause and escalation conditions
- Escalate a directly demonstrated mobile change beyond diagnostics, conflicting edits, failed independent gates, or a required unsafe external operation to root.
- Stop after three materially different attempts without new evidence or four iterations; no silent scope/gate waiver.

## Final evaluation
- Validator command: python3 /Users/m.oluwole/.agents/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/GOAL-17tnw2b9dq1.md
- Validator result: structural validator passes before execution and at handoff; completion is intentionally pending C-005.
- Independent verification result: pending root review.
- Terminal state: GATE_REVIEW.
- Remaining failed or blocked criteria: C-005 pending root-owned four reviews and hosted CI.
- ClickUp final evidence comment: pending.
