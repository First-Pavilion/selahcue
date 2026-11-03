# Goal Contract — TASK-17tnw2b2gmm

## Identity
- Goal ID: TASK-17tnw2b2gmm
- Parent goal ID: NONE
- Title: Accessible Sign up and Forgot password cards
- Role: frontend-engineer
- Status: ACTIVE
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/17tnw2b2gmm
- Created: 2026-11-03
- Updated: 2026-11-04
- Maximum iterations: 6
- Independent verification required: yes

## Objective
Both cards dim inputs once, keep labels readable, focus and describe the first invalid field, and use approved decorative crosses; busy signup password toggles are disabled.

## Baseline
Verified origin/main 9801fc587adba59a30ddee066efb5d0da26fc425 has duplicate field opacity, enabled reveal controls, no invalid-submit focus, default circle errors. Ticket has no dependencies; referenced legacy epic is cancelled after backlog flattening.

## Inputs and evidence sources
ClickUp ticket and Uma comment 1400430000277443; existing SignIn and Reset patterns; auth browser driver.

## Scope
SignUpView.vue, ForgotPasswordView.vue and focused browser regressions. No shared components, tokens, copy, API/provider, deployment or collection changes. Analytics/permissions/API remain existing behavior; no new events or authorizations.

## Dependencies and approvals
User authorized public SelahCue branch/PR delivery. Uma glyph decision recorded. Root owns independent review, merging and QA transition.

## Completion predicate
| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Busy input effective opacity 0.5, labels 1 on both cards | npm run test:states | no failures | docs/delivery/evidence/17tnw2b2gmm/states.log | PASS |
| C-002 | yes | Both busy signup reveals excluded from keyboard focus | npm run test:states | no failures | docs/delivery/evidence/17tnw2b2gmm/states.log | PASS |
| C-003 | yes | Invalid submit focuses first input/select/checkbox with associated error | npm run test:states | no failures | docs/delivery/evidence/17tnw2b2gmm/states.log | PASS |
| C-004 | yes | Approved decorative crosses and wrapping on narrow/desktop cards | browser state checks | no failures at 375/1440 | docs/delivery/evidence/17tnw2b2gmm/states.log | PASS |
| C-005 | yes | Each restored regression is rejected | mutant browser runs | behavioral failures for each fault | docs/delivery/evidence/17tnw2b2gmm/negative.log | PASS |
| C-006 | yes | Unit, lint, type, build and full state regressions pass | npm test; npm run lint; npm run test:states | exit zero | docs/delivery/evidence/17tnw2b2gmm/checks.log | PENDING |
| C-007 | yes | Independent Cody Shadow Quinn Vera reviews pass | root coordinated review | all four pass exact source | root handoff | PENDING |

## Verification plan
Real production bundle with scripted GraphQL responses; actual Chrome rendering, focus, ARIA and CSS. No real account or provider calls. Full state suite retains enumeration comparisons. Negative proof restores each defect independently.

## Iteration ledger
### Iteration 1
- Target criterion: C-001 through C-004
- Hypothesis: view-scoped reuse of fieldset and DOM-order invalid focus fixes defects without shared changes.
- Change or investigation: write behavioral browser checks before implementation.
- Verifier executed: focused production-browser regression against baseline
- Result: all target defects failed before implementation (red.log).
- New evidence: first-invalid focus, glyph and effective opacity failures observed.
- Decision: iterate

## Risks and rollback
Scoped focus behavior and disabled fieldset spacing; test real rendering. Revert ticket commit to roll back.

## Pause and escalation conditions
Stop for new design/API decisions or unsafe external effects; root handles review gate. Six maximum iterations, stop after three materially different unsuccessful attempts without new evidence.

## Final evaluation
- Validator command: python3 /Users/m.oluwole/.agents/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/TASK-17tnw2b2gmm.md
- Validator result: pending
- Independent verification result: pending root review
- Terminal state: pending
- Remaining failed or blocked criteria: reviews pending
- ClickUp final evidence comment: pending

### Iterations 2–5
- Implemented only the two views using existing fieldset/glyph patterns and scoped form focus.
- Verified all nine restored defects fail their target browser assertions (negative.log).
- True375px/1440px companion: six cases pass (responsive.log); inspected errors-375.png and errors-1440.png.
- Full production-driver measurement:77 scenarios/2765 checks/zero behavioral failures; old strict2645 count alone exited4, now updated to observed2765. Full measurement is diagnostic, not a passing command (full-measurement.log).
- Final unit1246, lint and type checks passed.

### Iteration 6 — frozen-source handoff
- Exact npm run test:states confirmation and hosted checks remain pending at draft publication. Root explicitly requested publishing the frozen draft while keeping Farah and the verifier alive.
- Final receipts will be posted to PR and ClickUp; pending labels in this frozen evidence are the publication-time snapshot.
- C-006 remains PENDING until exact CLI completes; C-007 remains PENDING for root's independent review. No completion claim or merge.
