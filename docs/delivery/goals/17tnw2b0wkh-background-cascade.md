# Goal Contract — TASK-17tnw2b0wkh

## Identity

- Goal ID: TASK-17tnw2b0wkh
- Parent goal ID: WAVE3-SELAHCUE-20
- Title: Background guards honor the matching-rule property cascade
- Role: frontend-engineer
- Status: ACTIVE
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/17tnw2b0wkh
- Created: 2026-10-30
- Updated: 2026-10-30
- Maximum iterations: 8
- Independent verification required: yes

## Objective

Every existing CSS background guard reads the background the matching rules actually declare across duplicates, including shorthand/longhand, variables and priority, so an earlier-rule-only background does not trigger a false missing-background failure and unsafe actual backgrounds still fail.

## Baseline

Actual main6843a68fd9a21326d8366d7b988fa630641f2e56 includes AYETD's validated2565 browser checks. Background sites still read __cssBg from the last __cssRule, so a later color-only duplicate hides an earlier background from the guard while the browser retains it. The existing generic __cssEffective handles priority per property but needs careful shorthand/longhand treatment for background. Filter guard semantics and raw condition blindness are separately established and out of scope.

## Inputs and evidence sources

- Full frontend-qualification/17tnw2b0wkh-live.json: complete task, null parent, no dependencies, zero comments; original linked filter-cascade work already implemented. Qualification report and AGENT-RUNBOOK.md read.
- Root freshly re-read full unchanged task/zero comments; frozen20 execution authorized. ClickUp start/status pending Mac unlock and connector cap; root owns pending update, code work expressly authorized meanwhile.
- Current scripts/operator_headless.py CSS_SRC cascade helpers, all background consumers and fixture/DOM patterns; applicable repository/runtime/frontend/Goal guidance.

## Scope

### In scope

- Inventory and migrate every last-rule background read to the actual per-property background cascade, preserving supported shorthand/longhand/var/important behavior.
- Real browser earlier-only positive controls and unsafe-background negative controls, real-site CSS witness, meaningful sensitivity/identical restoration and full normal driver.
- Narrow driver/helpers/tests and this execution contract; measured strict count only from real execution.

### Non-goals

- Filter guards, raw backstop/condition policy, selector-candidacy expansion or selector pinning follow-up, already-fixed comment hoist, shipped product CSS/UI, Rust/API/Flutter/backend/native changes.
- New CSS cascade model beyond the existing exact matching selectors/condition envelope; no claim of physical/native platform acceptance.

### Constraints

- Own isolated worktree/codex branch/one draft PR, preserve other agents' source and worktrees. Managed creation succeeded but parent attachment registration hit100 identity cap; use returned explicit path, no unrelated attachment removal.
- No local project runtime/import/tests/build/install/browser/benchmark/containers. Tiny Git/source/stdlib/static checks and hosted runtime only.
- Actual behavior RED before helper/site fix; all2565 prior checks remain and filter code stays unchanged. No ignored failures/retries/guessed counts/loosened contrast bounds.
- Author may ordinary push/draft/body-file/attempt immediate attach and exact-parent workflow-only hosted diagnostics. Root owns tracker, all4 independent reviews, remediation routing, merge and QA. No next AYETE until dispatch.

### Assumptions and unknowns

- VERIFIED: earlier background plus later unrelated declaration is a false RED in the task's actual Go Live witness; no user policy decision required.
- UNKNOWN: full shorthand/longhand/variable/important browser behavior and current test count until measured. Use real CSSOM/computed-style premises and existing parsing patterns; preserve declared supported boundaries.

## Dependencies and approvals

- AYETD verified merged6843a68f/treeb7e43a12 with all4/normal CI PASS; its QA/completed export remains pending root receipt after unlock.
- User selected20/root dispatch authorizes this standalone unit despite tracker start pending. No owner-held/dependent work imported.

## Completion predicate

All mandatory rows must PASS for VERIFIED_COMPLETE.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | All background guard consumers preserve earlier-rule-only backgrounds and reject actual unsafe values | Inventory plus real-site duplicate CSS/browser positive and negative controls | Correct resolved background at every migrated site; clean earlier-only shape passes, unsafe contrast fails | Hosted actual RED/GREEN and source mapping | PENDING |
| C-002 | yes | Shorthand/longhand/var/important backgrounds agree with actual browser cascade | Literal real DOM/CSSOM fixture matrix with both-direction controls | Resolved background matches independent browser premises, priorities/resets retained | Hosted measured matrix/raw | PENDING |
| C-003 | yes | Original filter and whole-driver controls remain sensitive and unweakened | Current-source last-rule/priority/consumer mutation controls plus identical restoration/full siblings | Intended named failures, original filter guards unchanged, restored complete suite clean | Exact-parent/raw/component hashes | PENDING |
| C-004 | yes | Normal affected configured CI passes at final source and actual count | Official whole-driver/current normal CI | Selected jobs succeed, strict measured count, skips/platform exclusions explicit | Official metadata/raw receipts | PENDING |
| C-005 | yes | Four current-source independent reviews pass | Root-owned Cody/Quinn/Vera/Shadow and valid remediation/re-review | No unresolved blocking finding | Root consolidated reports/manifest | PENDING |

## Verification plan

- Focused verification: real stylesheet/browser cascade premises, actual shared helper and actual guard sites; clean/unsafe earlier-only and longhand/shorthand/priority/variable cases.
- Broader regression verification: full operator2565 prior checks plus meaningful new cases; current-source sensitivity/restoration and normal applicable pipeline.
- Independent verifier: root coordinates four roles, actual merge tree and tracker QA receipts.
- Required environment: hosted Chrome plus configured Linux/WebKit/Rust/operator jobs as selected; no local or physical/native acceptance inferred.

## Iteration ledger

### Iteration 1

- Target criterion: C-001/C-002 source and tests-first readiness.
- Hypothesis: reading only the last rule loses an earlier background, while a browser-backed per-property read can retain background shorthands/longhands/variables/priority without altering filters.
- Change or investigation: read full task/zero comments, qualification/runbook and matching-rule/background consumers; create isolated worktree from actual6843a68f, validate bounded child before code. Add literal real-browser fifteen-case shorthand/longhand/local-var/priority/color-image matrix through existing __cssEffective and contrast outcomes, plus absent/missing controls. Prepare actual eleven-site CSS witness appending only an unrelated custom declaration to preserve browser backgrounds while exposing last-rule reads. No helper/site/filter/shipping changes before actual RED.
- Verifier executed: Goal structural and source/Git preparation; hosted tests-only RED to follow.
- Result: Actual corrected hosted41138510265 baseline2612 checks/18 new behavior failures, eleven-site witness2593 checks/29 failures (same18 plus11 real missing-background checks). All15 literal browser premises and prior non-background siblings pass both runs. The old last-rule witness skips19 guarded assertions;2593 is not a complete-suite count. Old2565 count mismatch separate. Initial wrong-DLM diagnostic41138446276 cancelled, not RED proof.
- New evidence: background-cascade qualification/objects and forthcoming hosted raw receipts.
- Decision: iterate

### Iteration 2

- Target criterion: C-001 through C-004.
- Hypothesis: browser-native composition of the exact matching CSSOM declarations retains per-longhand priority, shorthand resets and local variable substitution; all consumers must use that property read rather than the last rule.
- Change or investigation: add a background-only branch to existing __cssEffective. Compose matching declaration text in source order on one temporary style, require an actual fill declaration, resolve the full background with the live browser and always remove the probe. Migrate all11 real guard sites plus2 CSSOM background controls. Allow the existing color resolver to accept a full background declaration; keep every contrast bound/assertion/filter/raw/parser path unchanged. Pin actual complete baseline2612; the partial2593 witness count is explicitly rejected as the guard baseline.
- Verifier executed: actual raw classification, source/filter identity checks, Python AST, full baseline diffcheck, Goal structural validation; targeted complete baseline/eleven-site GREEN next.
- Result: Actual focused41139752755 on638420cf SUCCESS: both baseline and actual eleven-site earlier-only witness execute full2612checks/0FAIL. All47 new records and all original sibling assertions PASS in both. Source/dist/harness unchanged component markers inspected. Full normal CI/current mutants and four independent reviews remain pending.
- New evidence: background-cascade/red-classification.json, candidate source/object and upcoming hosted raw receipts.
- Decision: iterate

### Iteration 3

- Target criterion: C-003 through C-005 delivery readiness.
- Hypothesis: reverting real consumers to last-rule reads must recreate all11 missing-background failures while the corrected helper matrix stays green; dropping priority or longhand participation must fail the corresponding literal matrix cases.
- Change or investigation: preserve actual focused GREEN/raw, ordinarily integrate latest disjoint approved main before final publication, then prepare current-source consumer-reversion/priority/longhand mutants with exact restoration and normal affected CI. No product/helper/assertion change after the observed GREEN except target integration and this evidence ledger.
- Verifier executed: exact component/filter identity, static AST/full baseline/Goal checks; hosted current-source mutation/full normal receipts to follow.
- Result: Current runtime sensitivity/full normal CI and independent review gates pending; no task completion claim.
- New evidence: background-cascade/green-ci official raw/hash and current candidate receipts/normal/mutation archives.
- Decision: iterate

## Risks and rollback

- Risks: a shorthand masks later longhand, pending var substitution is mistaken for absence, lower-priority later values win, a stale site still reads last rule, or filter helper is accidentally broadened. Real positive/negative priority matrix and exact filter-source identity address these boundaries.
- Rollback or recovery: revert this one harness/helper PR; no product state/data/schema change.

## Pause and escalation conditions

- No source behavior fix before actual qualified RED. Escalate real new owner policy or unsupported cross-component scope; do not invent it.
- Maximum8 and no-progress bounds remain; preserve actual setup/fixture/behavior/partial outcomes and full failure history.

## Final evaluation

- Validator command: python3 /Users/m.oluwole/.agents/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/17tnw2b0wkh-background-cascade.md
- Validator result: Initial structural validation PASS before tests; source/static gates pending hosted behavior.
- Independent verification result: Pending all four root-owned reviews.
- Terminal state: ACTIVE, tests-first preparation.
- Remaining failed or blocked criteria: C-001 through C-005 pending.
- ClickUp final evidence comment: Root owns pending start/status and final QA readback.
