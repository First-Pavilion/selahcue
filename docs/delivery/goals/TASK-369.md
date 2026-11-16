# Goal Contract — TASK-369

## Identity
- Goal ID: TASK-369
- Parent goal ID: TASK-17tnw2b2jvz
- Title: Native mobile menu remains operable at the breakpoint
- Role: frontend-engineer
- Status: BLOCKED
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/17tnw2bcj0n — native Bug created and In Progress read back by coordinator after access recovery; issue https://github.com/First-Pavilion/selahcue/issues/369
- Created: 2026-11-04
- Updated: 2026-11-04
- Maximum iterations: 3
- Independent verification required: yes

## Objective
Establish the actual native WebKit menu failure and correct only the evidenced cause while preserving native navigation, accessibility and scroll recovery.

## Baseline
Verified base2f4dcc25. At nominal768 WebKit desktop Pricing is hidden and Menu visible; prior ordinary sheet Pricing click detached. Cause unknown. Original cards Goal iterations1–6 remain unchanged.

## Inputs and evidence sources
- Coordinator issue369 assignment and retained nav768/iteration6 receipts.
- Current Navbar.vue and pageScrollLock.

## Scope
### In scope
- One unchanged-bundle native WebKit diagnostic; narrowly evidenced menu fix and meaningful regression.
### Non-goals
- API/card contracts, timeout changes, full responsive sweep, forced clicks, release/deployment.
### Constraints
- Preserve viewport, CSS breakpoints, focus/inert, modal lifecycle and strict assertions.
- Owned codex branch/worktree only; four independent reviews and actual CI before root merge.
### Assumptions and unknowns
- UNKNOWN whether scroll locking flips the breakpoint; measure before implementation.

## Dependencies and approvals
- User authorizes delivery/fix loop. Root verified native In Progress after access recovery; final handoff evidence write/readback and four reviews/merge remain root-owned.

## Completion predicate
| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Actual failure causality observed | native WebKit diagnostic | before/open/media/viewport/ordinary click evidence | docs/delivery/evidence/369.md | PASS |
| C-002 | yes | Native menu Pricing and recovery work with original negative control | focused browser regression | original failure and corrected ordinary clicks pass | docs/delivery/evidence/369.md | PASS |
| C-003 | yes | Relevant unit, type, lint and browser regression pass | marketing scoped checks | exit0 with preserved controls | docs/delivery/evidence/369.md | PASS |
| C-004 | yes | All four independent reviews and applicable hosted CI pass | root reviews/current CI | Cody Shadow Quinn Vera and actual CI success | root handoff | BLOCKED |
| C-005 | yes | Native ticket status/evidence saved and read back | coordinator ClickUp backfill | verified In Progress and linked evidence | coordinator verified17tnw2bcj0n In Progress; final evidence write pending | BLOCKED |

## Verification plan
- Focused verification: one unchanged native WebKit768 diagnostic, real normal clicks; then negative/fixed regression if cause established.
- Broader regression verification: relevant navigation/focus/scroll tests, lint/type/build as needed.
- Independent verifier: Cody, Shadow, Quinn, Vera, root-owned.
- Required environment: native Playwright WebKit/Chromium, synthetic local HTTP only.

## Iteration ledger
### Iteration 1
- Target criterion: C-001.
- Hypothesis: UNKNOWN; test whether opening scroll lock changes actual media query and removes sheet.
- Change or investigation: Read-only native timeline diagnostic on immutable current-main Navbar bundle.
- Verifier executed: pending.
- Result: pending.
- New evidence: pending.
- Decision: iterate only on observed causality, otherwise blocked.

## Risks and rollback
- Risks: modal lock/focus lifetime regression; preserve explicit controls.
- Rollback or recovery: revert own narrow patch only.

## Pause and escalation conditions
- Unknown cause after bounded diagnostic; role/scope decision; actual publication rejection; max3 exhausted.

## Final evaluation
- Validator command: python3 /Users/m.oluwole/.agents/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/TASK-369.md
- Validator result: pending.
- Independent verification result: pending root.
- Terminal state: pending.
- Remaining failed or blocked criteria: C004/C005 root.
- ClickUp final evidence comment: pending external access/root.

## Completed iteration ledger

### Iteration 1 result
- Actual unchanged native WebKit diagnostic failed ordinary Pricing click: overflow lock changes client756→768 with unchanged inner768, then queryfalse closes modal. C001 PASS causal evidence in369/proof.json. Sandbox bind denial was before any test.

### Iteration 2
- Target criterion: C002.
- Hypothesis: temporary stable scrollbar gutter prevents the self-induced query change.
- Change or investigation: exact-restoring/refcounted temporary gutter lock plus regression.
- Verifier executed: old unitnegative, candidate37unit/type/build, actual nativepositive.
- Result: nativepositive FAIL same width/query/detachment; candidate fully reverted.
- New evidence: retained gutterpositive timeline and logs; no shippinggutterchange.
- Decision: iterate with new causal evidence, finaliteration3 only.

### Iteration 3
- Target criterion: C002/C003.
- Hypothesis: Navbar owns modal lifetime through self-induced query changes, but closes on actual viewport growth.
- Change or investigation: opening width snapshot, paired actualresize listener, remove only redundant modal-layer CSS hide.
- Verifier executed: nativecorrected regression93checks/four scenarios; npm1250, responsive36, lint/type/build/whitespace.
- Result: PASS scoped candidate. First broad verifier role observation failed due correctbackgroundinert; coordinator explicitly allowed one DOM-only observation correction on unchangedcandidate. Preserved failure; actualclicks/assertions/deadlines unchanged.
- New evidence: docs/delivery/evidence/369.md and369/{browser,proof}.json.
- Decision: blocked for root-owned four reviews and currentCI; no further implementation iteration authorized.

## Handoff evaluation
- Structural validator: run before iteration1 and finalhandoff.
- C001/C002/C003 PASS; C005 nativeInProgress created/readback by root. C004 BLOCKED until allfourreviews and actualCI; C005 final native evidence write pending.
- Terminal state: BLOCKED, independent review/CI pending. This is not VERIFIED_COMPLETE, merged or QA.
