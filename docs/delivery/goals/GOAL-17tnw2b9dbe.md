# Goal Contract — GOAL-17tnw2b9dbe

## Identity
- Goal ID: GOAL-17tnw2b9dbe
- Parent goal ID: NONE
- Title: Replace the yanked chacha20 lock entries with the compatible 0.10.2 patch
- Role: backend-engineer
- Status: GATE_REVIEW
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/17tnw2b9dbe
- Created: 2026-11-04
- Updated: 2026-11-04
- Maximum iterations: 4
- Independent verification required: yes

## Objective
Remove the chacha20 yanked warning in both affected Cargo roots through only a targeted compatible lockfile patch.

## Baseline
Verified freshly fetched main8a66f0ba168e422ef1f60a7b3c8418ae8bb1f2f7; task moved to in progress and read back, start comment1400430000278343. Official sparse registry currently marks0.10.1 yanked and0.10.2 not yanked, published2026-08-27 with rust-version1.85; primary crates.io API itself returned403. New worktree is isolated; the reviewed hygiene3ba branch stays untouched.

## Inputs and evidence sources
- Live ClickUp ticket and comments (none initially); no dependency edges.
- Official https://index.crates.io/ch/ac/chacha20 metadata, Cargo manifests/locks, rand reverse trees, RustSec audit outputs.

## Scope
### In scope
- Exactly chacha20 package version/checksum changes in desktop and operator Cargo.lock.
- Scoped verification/evidence and this goal.
### Non-goals
- No manifest, source, dependency-wide update, third Cargo-root lock update, deployment or installer packaging.
- Permissions, tenancy, API/data schema, migrations/jobs/transactions and data ownership do not apply to this lock-only change.
### Constraints
- One ticket/branch/PR from main; no user checkout or other agent edits.
- Exact compatible0.10.2 patch, not an unbounded latest update.
### Assumptions and unknowns
- UNKNOWN until actual audits: whether the live advisory database adds unrelated warnings since the ticket; compare current baseline/head honestly.

## Dependencies and approvals
- User authorized work and root-owned four-review/merge/QA flow. Preserve manual/main-only packaging; no production calls.

## Completion predicate
All mandatory criteria must be PASS for VERIFIED_COMPLETE.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Official metadata and rand requirement accept non-yanked0.10.2 | Fresh official sparse index, Cargo reverse tree, rand manifest |0.10.2 not yanked and satisfies current rand^0.10 requirement | docs/delivery/evidence/17tnw2b9dbe.md | PASS |
| C-002 | yes | Only the two intended lock package entries change | Targeted cargo update, parsed before/after lock comparison, locked metadata | Version/checksum only; no manifests or other package resolution changes | docs/delivery/evidence/17tnw2b9dbe.md | PASS |
| C-003 | yes | Yanked warning removed and remaining baseline warnings preserved | Baseline/head cargo audit JSON, make audit | No chacha20 warning; no vulnerability; other allowed warnings unchanged | docs/delivery/evidence/17tnw2b9dbe.md | PASS |
| C-004 | yes | Consumer compatibility gates pass | Locked metadata,fmt,clippy,rand-consumer crate tests | All commands exit0; actual failures/limits disclosed | docs/delivery/evidence/17tnw2b9dbe.md | PASS |
| C-005 | yes | All independent reviews and hosted integration gate pass | Cody,Shadow,Quinn,Vera plus exact-headCI | Root confirms all4pass before merge/main/QA | PR and ClickUp handoff | PENDING |

## Verification plan
- Focused verification: exact package-map lock delta, actual audits and reverse dependency consumers.
- Broader regression verification: suites of affected first-party consumers, formatting and clippy in both roots; source CI.
- Independent verifier: root dispatches four separate reviewers.
- Required environment: local Rust1.98.0/macOS with registry/advisory network; no providers or production actions.

## Iteration ledger
### Iteration1
- Target criterion: C-001 through C-004.
- Hypothesis: targeted0.10.2 update changes only chacha20 while removing the existing allowed yanked warning.
- Change or investigation: current metadata/baseline and consumer tracing, then targeted update and gates.
- Verifier executed: official registry metadata, parsed two-lock comparison, locked metadata, baseline/head JSON audits, make audit, both fmt roots, consumer suites and clippy.
- Result: C-001 through C-004 PASS. Both audit warning maps differ only by removal of chacha20 yanked warning; all other package entries unchanged. Workspace consumer734 tests pass/11 ignored, operator455 pass/1 ignored, both clippy commands exit0.
- New evidence: docs/delivery/evidence/17tnw2b9dbe.md records commands, counts, exact advisory snapshot, existing ignored cases and local architecture limits. All required local processes completed.
- Decision: gate-review.

### Iteration2
- Target criterion: C-004 integration freshness, preserving C-001 through C-003.
- Hypothesis: the new main NDI CI/helper-only delta leaves lock/audit/consumer evidence unchanged, while its newly required NDI check also accepts the targeted patch and still detects gated-code faults.
- Change or investigation: normal merge maincfed597161fb3150db8d79d1bfeca58185e431ee as c588cc61; full4-file target delta inspected, no appsource/manifests/locks changed. Parsed exact two-lock delta rechecked against newmain.
- Verifier executed: NDI helper self-test4pass; actual check/clippy/mutation-proof/restored-check exit0. Expected gated E0308 observed with marker. Restored video_sink.rs verified byte-identical by clean git diff;0behind target.
- Result: required new gate PASS with updated lock. Previous734+455 consumer suites and metadata/audits retained because exact inputs are unchanged. No active verifier, SDK/runtime download, linked build or packaging action.
- New evidence: docs/delivery/evidence/17tnw2b9dbe.md integration section and /private/tmp/17tnw2b9dbe-ndi-mutation.log.
- Decision: gate-review.

## Risks and rollback
- Risks: transitive resolution drift; parsed lock comparison will refuse anything beyond expected package entry.
- Rollback or recovery: revert the isolated two-lock patch; no persistent-data change.

## Pause and escalation conditions
- Stop for incompatible exact patch, unrelated advisory gate failure requiring broader source/dependency change, changed scope or publication rejection; report to root.
- Stop after three materially different unsuccessful attempts without new evidence or maximum4iterations.

## Final evaluation
- Validator command: python3 /Users/m.oluwole/.agents/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/GOAL-17tnw2b9dbe.md
- Validator result: structural validator passes before execution and at handoff; completion intentionally remains pending C-005.
- Independent verification result: pending root review.
- Terminal state: GATE_REVIEW.
- Remaining failed or blocked criteria: C-005 pending root-owned four reviews, publication and exact-head hosted CI. NDI maincfed5971 is integrated and its actual mutation-proof gate passes with the updated lock; root refreshes affected reviews on the new frozen snapshot.
- ClickUp final evidence comment: pending.
