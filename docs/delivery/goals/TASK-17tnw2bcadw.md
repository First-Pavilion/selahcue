# Goal Contract — TASK-17tnw2bcadw

## Identity
- Goal ID: TASK-17tnw2bcadw
- Parent goal ID: NONE
- Title: Home Figma layout viewport compensation without hidden overflow
- Role: frontend-engineer
- Status: GATE_REVIEW
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/17tnw2bcadw
- Created: 2026-11-04
- Updated: 2026-11-04
- Maximum iterations: 4
- Independent verification required: yes

## Objective
Strict Home Figma geometry uses a measured 1440px document layout viewport on Linux WebKit and zero-gap browsers, while nominal responsive and true horizontal-overflow checks remain effective.

## Baseline
Fresh main c0325d52e809847fac141a605b74a7e6d7de7021. Home measure sets outer1440 without compensating document client1428 on Linux WebKit; PR350 CI reports eight strict geometry failures. Core has a measured fit_figma_frame helper and separate nominal overflow regression. Home detects overflow using innerWidth, which may include external scrollbar chrome.

## Inputs and evidence sources
- Root-created live ticket17tnw2bcadw, High priority, approved description in /private/tmp/wave2-home-harness-ticket.md; root saved/read back In Progress and visible start comment before code.
- https://github.com/First-Pavilion/selahcue/actions/runs/41756526885/job/126333884624
- Current Home/Core/Secondary harnesses and Core frame regression.

## Scope
### In scope
- Home nominal1440 Figma frame measurement and focused browser regression.
- Reuse measured compensation approach; preserve exact nominal viewport requests and actual overflow detection.
### Non-goals
- Product CSS, geometry values/tolerances, browser/runner version changes, skip conditions.
- Frozen PR352 hardening source, API/installer/provider/deployment work or user mobile lockfile.
### Constraints
- Separate owned worktree/branch and one ticket/PR; never mutate shared dist during concurrent checks.
- All required verifier processes must finish before final handoff.
### Assumptions and unknowns
- UNKNOWN: actual hosted Linux green; root owns real CI freshness and all four reviews before merge/QA.

## Dependencies and approvals
- Root and Diego created/approved this scoped CI unblock; root owns ClickUp UI writes while MCP quota is exhausted.
- Wait for root verified In Progress receipt before implementation.

## Completion predicate
| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Simulated12px external chrome reproduces baseline1428 failure then fixed1440 geometry passes original strict assertions | focused Home frame regression RED/GREEN | baseline nonzero; final exit0 | docs/delivery/evidence/17tnw2bcadw/results.md | PASS |
| C-002 | yes | Zero-gap outer width remains1440; compensation only applies to explicit Figma measurement, never nominal responsive requests | focused Home frame regression | exact recorded widths and real layout assertions pass | docs/delivery/evidence/17tnw2bcadw/results.md | PASS |
| C-003 | yes | Real injected horizontal overflow is rejected even when innerWidth includes external chrome | focused negative real-DOM regression | actual overflow check fails for fixture, test exits0 | docs/delivery/evidence/17tnw2bcadw/results.md | PASS |
| C-004 | yes | Actual Home130+130 checks and existing Core strict geometry/nominal overflow controls pass | required Home and Core suites; make marketing-check | all exit0, no skips/tolerance changes | docs/delivery/evidence/17tnw2bcadw/results.md | PASS |
| C-005 | yes | Current hosted Linux CI and four independent reviews approve current head before main/QA | root Cody Shadow Quinn Vera and actual GitHub checks | four PASS and hosted CI green, merge/main/QA verified by root | root delivery receipts pending | PENDING |

## Verification plan
- Focused verification: simulated12px external viewport with genuine DOM, zero-gap control, explicit nominal width records, actual overflow injection.
- Broader regression verification: real Home both engines and existing Core browser/frame gates; shared marketing type/lint/unit/build.
- Independent verifier: Cody, Shadow, Quinn and Vera via root.
- Required environment: isolated worktree, built marketing dist, pinned Playwright1.60.0 Chromium/WebKit; real Linux hosted CI.

## Iteration ledger
### Iteration 1
- Target criterion: C-001 through C-004.
- Hypothesis: measured frame compensation only on explicit Home Figma measurement fixes the12px frame loss, and document clientWidth preserves true overflow detection.
- Change or investigation: inspect fresh owning source and create isolated branch; awaiting root In Progress receipt before code.
- Verifier executed: git fetch origin main, current harness/source inspection.
- Result: baseline current source and exact eight CI geometry losses confirmed.
- New evidence: approved ticket and hosted CI job link above.
- Decision: iterate

### Iteration 2
- Target criterion: C-001 through C-004.
- Hypothesis: current-load measured gap (not a platform constant or previous navigation gap) preserves strict geometry under changing native scrollbar reservation.
- Change or investigation: captured unchanged-main RED client1428/eight exact failures, reused Core helper only for explicit Figma1440, moved original eight assertions verbatim to a shared callable, used layout scrollWidth/clientWidth for real overflow. Fixture diagnostics showed host-native WebKit reservation can change after resize; regression instruments actual current-load measurements without faking DOM.
- Verifier executed: focused real-DOM regression; sequential make marketing-check and actual Home both-engine suite with automatic focused subprocess; Core gate running next.
- Result: focused regression exits0: zero-gap unchanged, eight strict widths pass after compensation, exact five nominal requests, five zero-overflow controls,15 real1px/12px/24px overflow rejections. Home130+130 checks PASS; marketing1246 tests PASS. Core/syntax final results pending completion.
- New evidence: docs/delivery/evidence/17tnw2bcadw/baseline-red.txt, home-green.txt and verifier-status.json.
- Decision: iterate

### Iteration 3
- Target criterion: final current-target verification and C-004.
- Hypothesis: normally integrating the merged API uv main preserves this independent Home fix while keeping uv CI/helper/lock/dependency-graph changes intact.
- Change or investigation: integrated fresh main b3ae75f824fe8e43b18836d3d661dc996dce98bc normally, preserving disjoint Home changes. Automatic focused regression runs after both original engines actually complete, preserving existing single-engine and optional missing-engine CLI behavior; required both-engine CI still fails closed.
- Verifier executed: current-target shared marketing, actual Home and Core suites plus focused automatic regression, syntax and whitespace.
- Result: final current-target checks all finished exit0: marketing1246 tests; actual Home130+130 plus focused subprocess; Core300 checks plus20 nominal/20 real overflow negatives; syntax/whitespace. Fresh main b3ae read back, zero behind.
- New evidence: docs/delivery/evidence/17tnw2bcadw/verifier-status.json.
- Decision: gate-review

## Risks and rollback
- Risks: widening nominal windows could hide overflow; require strict recorded-request and negative actual-overflow probes.
- Rollback or recovery: revert this isolated harness commit; no application behavior or data changes.

## Pause and escalation conditions
- Wait for root status receipt before code. Publication rejection, scope change, unavailable mandatory environment or iteration limit: report exact evidence to root without bypass.

## Final evaluation
- Validator command: python3 /Users/m.oluwole/.agents/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/TASK-17tnw2bcadw.md --completion
- Validator result: structural exits0; completion correctly exits1 while C-005 independent reviews/hosted CI/main/QA remain pending
- Independent verification result: root to dispatch Cody, Shadow, Quinn and Vera on frozen head; hosted Linux CI pending
- Terminal state: GATE_REVIEW
- Remaining failed or blocked criteria: C-005 pending root review/hosted CI/merge/main/QA gate
- ClickUp final evidence comment: prepared local payload for root authenticated UI; no connector retry
