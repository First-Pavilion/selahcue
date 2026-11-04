# Goal Contract — TASK-17tnw2b2fum

## Identity

- Goal ID: TASK-17tnw2b2fum
- Parent goal ID: NONE
- Title: Existing visual/audit and page-browser gates run in local and hosted CI
- Role: devops-engineer
- Status: ACTIVE
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/17tnw2b2fum
- Created: 2026-11-04
- Updated: 2026-11-04
- Maximum iterations: 4
- Independent verification required: yes

## Objective

Local make ci and hosted CI run the existing no-browser visual/audit controls through one target; existing browser page suites run with required engines, with meaningful path triggers and failure propagation.

## Baseline

Verified at main 8a66f0ba: neither visual/audit self-test is in make ci/CI. Existing lint-workflows already installs pinned Pillow. Browser CI installs both engines but lacks components/core/home/secondary suite steps; package scripts lack home/secondary. Current responsive sweep accepts both 24 and 96 desktop container gutters. Trigger paths-ignore excludes all docs, including visual audit data.

## Inputs and evidence sources

- Live ticket criteria and historical additions in comments 1400430000059552, 1400430000059707, 1400430000059713.
- Current Makefile/workflow, browser scripts, existing visual/fidelity controls and audit files.
- Root-approved ownership extension: package scripts and gutter tightening only after verifying current layout; no page-layout fixes.

## Scope

### In scope

- Shared no-browser Makefile target and existing always-run CI job; narrow visual-audit docs trigger exception and wiring controls.
- Existing components/core/home/secondary browser scripts and CI wiring; tighten non-bare full-container gutter only if all current pages meet it.
- Required docs, actual negative controls, shallow/full-history and timing evidence.

### Non-goals

- New visual capture, changed assertions to hide defects, page-layout fixes, new dependencies, installer/runtime/deployment/provider actions.

### Constraints

- Preserve minute, installer, SBOM and NDI controls; separate ticket branch/worktree; shared checkout/user lock untouched.
- Existing no-browser runner dependencies only; target must finish under 10 seconds on actual CI runner, measured separately from browser suites.

### Assumptions and unknowns

- UNKNOWN: full existing browser suites pass on current page layouts; verify and report exact pre-existing blockers rather than weakening them.
- UNKNOWN: every non-bare page has migrated to 96/48/20 containers; inspect and measure before tightening.

## Dependencies and approvals

- User approved ten-ticket wave and public source PR; root owns all-four independent review, merge and QA.
- Root approves historical requested browser additions. Current NDI PR347 may merge during work; integrate latest main normally before handoff.

## Completion predicate

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Shared target runs existing visual/audit controls in make ci and CI | actual target and wiring control | controls pass, same target both callers, no new dependency | docs/delivery/evidence/17tnw2b2fum.md | PASS |
| C-002 | yes | Either self-test failure stops actual make ci before later gates | scratch cap mutation and scratch audit self-test defect | nonzero make ci with expected failing control | evidence logs | PASS |
| C-003 | yes | Existing browser suites run with required engines and reject focus defect | actual components/core/home/secondary scripts and current-core behavior mutation | positive suites pass; negative exits nonzero on focus | evidence logs and CI | PASS |
| C-004 | yes | Visual-only paths trigger cheap gate, unrelated docs skip | actual workflow trigger/wiring controls | scripts vp and visual docs positive, unrelated docs negative | evidence/control | PASS |
| C-005 | yes | Shallow target passes and fake commit fails with full history | scratch depth1/full clones and actual audit mutation | shallow pass, fake cited commit refused | evidence logs | PASS |
| C-006 | yes | Actual hosted no-browser gate completes under 10 seconds and docs explain coverage | CI measured target and docs inspection | elapsed less than 10s, required docs current | CI and docs | PENDING |
| C-007 | yes | Frozen source passes four independent reviews and required CI | root-coordinated Cody Shadow Quinn Vera and hosted jobs | four Pass verdicts and actual CI success | PR/root reports | PENDING |

## Verification plan

- Focused verification: shared target, actual make ci negative controls, core browser current-behavior mutant, event-path fixtures, shallow/full-history audit cases.
- Broader regression verification: existing browser suites, actionlint/workflow/minute/installer/SBOM controls, required docs.
- Independent verifier: root dispatches Cody, Shadow, Quinn and Vera.
- Required environment: local Python/Pillow, Node22+, pinned Playwright Chromium/WebKit; existing hosted Linux jobs. Fonts may use existing allowed Google Inter requests in browser tests only.

## Iteration ledger

### Iteration 1

- Target criterion: C-001 and C-004.
- Hypothesis: shared target in existing Pillow-enabled always-run job and ordered event paths close cheap-gate omissions without creating runner/dependency cost.
- Change or investigation: shared three-command target in make ci and existing Pillow-enabled job, ordered event path exception, four existing browser-suite steps and missing package scripts, required docs and actual-wiring/path controls.
- Verifier executed: local shared target 8.068s, 20 push/PR path cases, normal marketing-check, actionlint, workflow/minute controls; scratch make ci with VP cap removed and audit minimum-title validation removed.
- Result: no-browser target passes; both real scratch make ci negatives exit2 at their expected failing control before later installer/Rust gates. Normal marketing-check passes 1246 tests/type/lint/build. Browser suites and layout probe remain running.
- New evidence: task-owned logs under /private/tmp/wave10-visual-*; components 646 checks pass. Initial concurrent layout probe collided with a suite rebuilding dist and was discarded; rerun uses immutable dist snapshot.
- Decision: iterate with clone/history and browser/mutation evidence.

### Verifier correction approved before iteration 2

- The historical arrow-key focus criterion refers to the removed Pricing billing control. Current core script explicitly asserts no radiogroup under approved 17tnw2b0x3h and has 300 checks, not the old 396. Actual wrong-index SegmentedToggle focus mutation survived core (exit0) and is not accepted as a negative.
- Root approved using a real current core disabled-download/tab-order/heading behavior mutation instead, retaining all 300 core assertions and the no-billing-UI contract. Existing shared-components gallery does not render SegmentedToggle or exercise arrow keys, so no separate focus-negative is claimed there.
- The first focus scratch build omitted its imported pilot notice document and failed infrastructure before any test; it is discarded, not mutation evidence. A correctly assembled scratch root builds and demonstrates the inapplicable mutation survival above.
- Root expanded ownership only for stale Home/Support harness repair: approved pilot CTA/trust literals, exact six-card [218,218,218,240,240,240] geometry with provenance/content-visibility checks, and Support search-region status scoping. No product source/layout/copy changes.

### Iteration 2

- Target criterion: C-003 and C-005.
- Hypothesis: stale selectors/copy rather than layout defects explain newly activated Home/Support failures; current core behavior must replace the removed-control negative.
- Change or investigation: exact harness reconciliation, verified gutter tightening after 180 non-bare route/width positives, actual shallow/full clones and event-path negatives.
- Verifier executed: Home/Secondary reruns, actual clone target runs, fake full-history audit commit, four event-path removal/reordering negatives.
- Result: Home260checksPass; Secondary362checksPass; shallow/full targetsPass and fakecommit refused; both event exceptions have expected negative failures. Actual current-core disabled-button mutant exits1 with four expected disabled/Tab-order failures in two engines. Clean immutable WebKit responsive repeat remains pending.
- New evidence: task-owned reconciled, history and trigger logs; earlier WebKit sweep collided with a concurrent dist rebuild and is discarded as infrastructure, to be rerun on immutable snapshot.
- Decision: iterate with current-core negative and stable-bundle WebKit verification; hosted timing/review gates remain pending.

## Risks and rollback

- Risks: newly enabled old tests may expose existing failures; preserve assertions and report exact dependency. Path rules must not wake heavy jobs for unrelated docs.
- Rollback or recovery: revert this ticket's isolated commit; no production data changed.

## Pause and escalation conditions

- Existing pages fail required geometry/behavior, source dependencies unavailable or under-10s budget cannot be met: report evidence to root before widening scope.
- Automatic public-publication rejection: no retries or alternate route; hand off frozen local payload for review/approval.

## Final evaluation

- Validator command: python3 /Users/m.oluwole/.agents/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/TASK-17tnw2b2fum.md
- Validator result: pending.
- Independent verification result: pending.
- Terminal state: ACTIVE.
- Remaining failed or blocked criteria: all pending.
- ClickUp final evidence comment: pending.
