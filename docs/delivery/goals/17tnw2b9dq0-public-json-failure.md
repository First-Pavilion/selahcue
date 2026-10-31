# Goal Contract — TASK-17tnw2b9dq0

## Identity

- Goal ID: TASK-17tnw2b9dq0
- Parent goal ID: WAVE3-SELAHCUE-20
- Title: Public protocol JSON helpers return only redacted JSON failures
- Role: mobile-engineer
- Status: ACTIVE
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/17tnw2b9dq0
- Created: 2026-10-31
- Updated: 2026-10-31
- Maximum iterations: 8
- Independent verification required: yes

## Objective

Make the public protocol serialization/parsing boundary return only JsonFailure, available without the server feature, while preserving wire behavior and existing caller redaction.

## Baseline

Verified base93bf472f65a1846117eecf09b1972c4118dc0cd4. Public protocol::from_json/to_json return serde_json::Error; safe JsonFailure/Kind live in server-gated tls.rs. Existing in-tree callers convert/discard errors, so this is public-boundary hardening, not a claim of current exploitation.

## Inputs and evidence sources

- Complete existing ClickUp task/zero comments: wave3 mobile-qualification/17tnw2b9dq0.json.
- Existing protocol/tls/wire/server/app operator callers, error redaction tests and cross-language fixtures.
- Wave3 AGENT-RUNBOOK.md and parent delivery goal; root owns tracker, review coordination, merge and QA.

## Scope

### In scope

- Ungated JsonFailure/JsonFailureKind module, redacted protocol Result types and From<JsonFailure> for TransportError.
- Preserve category/position and safe Display/Debug/source chains; adapt actual caller/premise tests.
- Audit Rust/Dart/operator callers and retain exact wire fixtures and protocol behavior.

### Non-goals

- No controller.rs/autolaunch.rs, operator_headless.py/main.rs edits, wire schema, new error policy or another ticket.
- No physical device, GUI, battery, deployment or unrelated platform acceptance claim for this Rust boundary.

### Constraints

- Own codex worktree/one ticket/one PR; do not reset or revert other agents' work.
- Hosted-only project runtime/build/tests/install/benchmarks. Tiny Git/stdlib/static checks allowed.
- Tests-first actual RED with positive controls; actual normal gates, meaningful mutants and exact restoration before review closure.

### Assumptions and unknowns

- UNKNOWN actual baseline error-output exposure and feature matrix behavior; hosted regression verifier establishes them before implementation.
- Root coordinates any shared-file discovery and final source/target drift.

## Dependencies and approvals

- User authorized selected20 implementation, author remediation, CI, four reviews, conditional merge and QA.
- WT5 cross-language fixtures already merged. Root permits independent overlap with frozen13XZ; controller/autolaunch remain its exclusive ownership.
- Existing flat standalone ClickUp ticket; no task creation or owner-policy decisions.

## Completion predicate

All mandatory rows must be PASS for VERIFIED_COMPLETE.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Public helper regression exposes raw error before fix and legitimate wire controls pass | Hosted tests-first targeted tests plus raw premise controls | Intended redaction failures with executed positive controls, no setup failure substitution | wave3 public-json-failure/red-ci | PASS |
| C-002 | yes | Ungated protocol API returns redacted JsonFailure preserving category/position and safe error output/chains | Hosted no-default/server tests, API type assertions and meaningful mutants | Safe Display/Debug/source, exact categories/positions, mutants fail specifically and restore exactly | wave3 public-json-failure/supplemental-ci | PENDING |
| C-003 | yes | Existing callers and exact wire/cross-language behavior remain compatible | Full caller audit, immutable fixture hashes and configured normal CI | All applicable normal gates pass; fixtures unchanged; skips explicit | wave3 public-json-failure/normal-ci and caller-audit.md | PENDING |
| C-004 | yes | All four independent reviewers pass final source/current target | Root Cody/Quinn/Vera/Shadow reports and remediation re-review | Four final Pass reports, no open required finding | wave3 reviews/17tnw2b9dq0-*.md | PENDING |
| C-005 | yes | Source-matched PR merges and exact task reaches QA with persisted handoff | Root merge tree/parents and exact-ID tracker reload | Verified merge and qa readback | wave3 17tnw2b9dq0-merge-receipt.json and qa-receipt.json | PENDING |

## Verification plan

- Focused verification: actual helper redaction/category/position/raw-premise/serialization failure tests without server and with server; precise API type assertions after fix.
- Broader regression verification: configured affected normal Rust/operator/server/Flutter fixture gates; exact existing fixture/component hashes.
- Independent verifier: root dispatches Cody, Quinn, Vera and Shadow; original author remediates valid findings.
- Required environment: hosted configured Linux toolchains only; native/device limits explicit.

## Iteration ledger

### Iteration 1

- Target criterion: C-001.
- Hypothesis: malformed sensitive values and custom serialization messages pass through the public helpers in raw serde errors today, although callers currently redact/discard.
- Change or investigation: establish own worktree/base, complete task/caller inspection, prepare focused tests-only behavior regressions and positive controls.
- Verifier executed: structural Goal validator before code; hosted RED pending tests-only checkpoint.
- Result: baseline source inspected; all runtime criteria pending.
- New evidence: task packet and exact base identity.
- Decision: iterate

### Iteration 2

- Target criterion: C-002 and C-003.
- Hypothesis: moving the existing three-field safe type unchanged and mapping both helpers at their public boundary prevents accidental raw-error propagation without changing wire values.
- Change or investigation: actual tests-only41185544571 verified six intended failures/six controls in both ungated and server modes, plus37 existing wire tests. Implement the ungated type move, retain old TLS aliases/raw-serde transport compatibility, add safe conversion/Error implementation, update raw-premise tests and pin public type/category contracts.
- Verifier executed: actual red-ci metadata/raw/hash inspection before implementation; direct rustfmt and diff/structural checks; candidate hosted normal/mutation gates pending.
- Result: C-001 PASS; other mandatory criteria pending actual candidate evidence and independent review.
- New evidence: public-json-failure/red-ci, tests-only manifest and diagnostic sole-parent/source proof.
- Decision: iterate

## Risks and rollback

- Risks: accidental feature gating, error-type compatibility, source-chain leakage or fixture drift.
- Rollback or recovery: one scoped PR; preserve existing safe type semantics/reexports and exact fixture hashes; revert only this evidenced merge if required.

## Pause and escalation conditions

- Stop overlapping source edits for root coordination; do not change product acceptance criteria.
- Preserve actual failures; stop after three materially different failed attempts without new evidence or max8 iterations.
- Root owns external merge/QA; no self-review or completion before required receipts.

## Final evaluation

- Validator command: python3 /Users/m.oluwole/.agents/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/17tnw2b9dq0-public-json-failure.md
- Validator result: initial structural validation PASS
- Independent verification result: pending
- Terminal state: ACTIVE
- Remaining failed or blocked criteria: C-001 through C-005
- ClickUp final evidence comment: root records start and final verified handoff
