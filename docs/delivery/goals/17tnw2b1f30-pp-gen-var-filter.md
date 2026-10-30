# Goal Contract — TASK-17tnw2b1f30

## Identity

- Goal ID: TASK-17tnw2b1f30
- Parent goal ID: WAVE2-SELAHCUE-20
- Title: PP-GEN rejects brightness filters delivered through CSS variables
- Role: frontend-engineer
- Status: ACTIVE
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/17tnw2b1f30
- Created: 2026-10-30
- Updated: 2026-10-30
- Maximum iterations: 8
- Independent verification required: yes

## Objective

The real PP-GEN hover guard rejects a CSS-variable-delivered brightness filter, retains meaningful browser-backed regression controls, and still accepts the clean shipped stylesheet.

## Baseline

Fresh actual main31c2e754ab268838f7c5a17c7a56d61de8b87a42 includes merged JH and its measured2401 strict count. In scripts/operator_headless.py, PP-GEN still calls registered __cssNoBrightnessFilter. That helper checks CSSOM/raw text for the literal brightness word. CSSOM can retain var(--token) while the browser resolves the token to brightness; the matching rule's raw body does not contain that word. The four sibling sites use __cssFilterGuardOk's conservative no-filter/exact-none CSSOM clause plus condition-blind raw declaration backstop. Shipped .pp-generate:hover contains only a background, no legitimate filter.

## Inputs and evidence sources

- Complete task/comments: wave2-20261029/frontend-qualification/17tnw2b1f30-live.json; successful comments count0 and no blockers.
- qualifications.md, current helper definitions, five-site static registry, CSSOM-PARSE fixtures and actual PP-GEN call site/app.css.
- Root/desktop CLAUDE.md, frontend/Goal operating contracts. Root explicitly serializes shared-harness tickets and permits this unit after actual JH merge.

## Scope

### In scope

- Existing PP-GEN predicate and narrowly scoped self-test controls; reuse sibling no-filter/exact-none composed predicate while retaining registered call-site identity.
- Browser-computed var() premise, clean positive, actual candidate-CSS rejection, exact old-predicate mutation/restoration sensitivity.
- Hosted behavioral RED before predicate change, measured strict count, full applicable CI and four independent reviews.

### Non-goals

- Changing production CSS/buttons/contrast design, unrelated selector/cascade/parser expansion or disabling a guard.
- Ticket17tnw2b0wkg exact-none/backdrop-filter raw-scan work; leave it queued until this PR merges.
- Condition-scoping the raw scanner: its intentional condition blindness, parser-dropped filters and nonmatching-condition protection must remain untouched, per owner1400430000047749 on the queued unit.

### Constraints

- New isolated managed worktree, one ticket/branch/PR; preserve other agents. Ordinary fresh-main integration before first publication.
- No local project runtime/build/browser/bench while host paging. All actual browser evidence hosted; no native/OS acceptance inference.
- Own bounded diagnostics, ordinary feature push/draft/body-file/immediate attachment allowed; root owns four reviews, tracker/status, merge and QA. No force push/protected edits/subagents/next scope.
- Preserve existing CSSOM-PARSE and five registered selector controls, full sibling suite and strict measured count; no ignored assertions/retry wrappers.

### Assumptions and unknowns

- VERIFIED: current helper and actual call-site gap remain; original task is actionable with no further owner decision.
- VERIFIED: actual hosted RED and candidate-CSS witness41056296534 each measured2406 checks with the one intended F30 predicate failure; old2401 strict-count guard additionally exited4. Browser var/raw premises, clean and sibling controls, existing CSSOM-PARSE and other full-suite assertions passed. Mutation/restoration and normal final CI remain pending.

## Dependencies and approvals

- JH PR291 actually merged31c2e754; shared harness now available for this serialized unit.
- User-selected wave authorization applies; root handles ClickUp In Progress/start and final QA. DP2 API changes may merge concurrently; integrate actual main before publication.

## Completion predicate

All mandatory rows must be PASS for VERIFIED_COMPLETE.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | PP-GEN rejects variable-delivered brightness using the sibling conservative composed predicate or equivalent var rejection | Real CSSOM-PARSE browser fixture and actual candidate CSS | Browser computes brightness; real PP-GEN predicate rejects it; clean accepts | Hosted actual RED/GREEN logs | PENDING |
| C-002 | yes | A meaningful var control fails if the predicate reverts, with clean and sibling controls retained | Full sibling old-predicate mutation and restoration | Named F30 failure under exact regression, clean/positive controls remain meaningful, restored suite passes | Hosted immutable mutation receipt/raw | PENDING |
| C-003 | yes | Existing raw condition-blind/parser-rejected/fail-closed and five-site wiring controls stay intact | Full CSSOM-PARSE tests, source diff and static registry controls | Existing controls pass; no queued raw-none/backdrop/condition behavior change | Hosted siblings and source proof | PENDING |
| C-004 | yes | Full applicable normal CI passes with exact measured suite count | Normal path-filtered CI and full browser gates | Every applicable configured gate green, ignored/unexecuted domains reported honestly | Hosted raw CI/receipt | PENDING |
| C-005 | yes | All four independent reviewers approve frozen source | Cody, Quinn, Vera and Shadow | No unresolved blocking findings after remediation/re-review | Root consolidated review | PENDING |

## Verification plan

- Focused verification: existing _cascadeCase/__cssFixture using actual getComputedStyle, CSSOM and raw matching-block read; real composed predicate, no copied oracle expression.
- Broader regression verification: whole operator_headless.py, candidate CSS through actual .pp-generate:hover guard, isolated exact old-helper mutation/restoration and normal operator CI/WebKit.
- Independent verifier: root coordinates all four final-source reviewers.
- Required environment: hosted Chrome and normal pinned Linux CI toolchains/WebKit; local source/Git/stdlib AST/structural/actionlint only.

## Iteration ledger

### Iteration 1

- Target criterion: C-001 through C-003.
- Hypothesis: current PP-GEN accepts var() because neither its effective CSSOM value nor matching raw block literally contains brightness, although getComputedStyle resolves brightness.
- Change or investigation: full original task/comments/current main inspected; prepare tests-only actual browser premise, predicate rejection and clean/sibling controls, without changing CSS_SRC helper or production CSS.
- Verifier executed: structural validator and stdlib/static baseline checks; hosted41056296534 on tests-only1eded83cb336a58290d7a08f429fd6c003ec3bf3, diagnosticffda38b9b7b2d1c5b3bda67d5393f65e6626394e.
- Result: Actual baseline2406 checks,1 intended F30 failure; clean/sibling/browser premises and all other behavioral assertions pass. Old2401 strict-count guard additionally exits4. Isolated actual-site adversarial var CSS also has2406/1, while the old actual PP-GEN site incorrectly passes; this is a site-level false-green witness, not a whole-suite pass.
- New evidence: ppgen-var/red.log, red-status.json and red-receipt.json retain raw evidence, including122 existing CSSOM-PARSE pass records across both runs.
- Decision: iterate

### Iteration 2

- Target criterion: C-001 through C-004.
- Hypothesis: delegating the registered PP-GEN helper to the existing sibling composed predicate rejects variable-delivered brightness while preserving all shared conservative protections and clean CSS.
- Change or investigation: replace only the weak helper body and its obsolete comment, retain every assertion/raw scanner/registered site, pin2406 from the actual two RED measurements, ordinary-integrate fresh main1cf675c4 (DP2 API-only).
- Verifier executed: stdlib AST, full baseline diff check and structural validator; hosted clean/old-helper mutation/actual-site CSS mutation/restoration and normal CI prepared for this frozen source.
- Result: Source checks pass; hosted corrected behavior and full CI pending.
- New evidence: own current-source receipt/raw logs will be attached at immutable handoff; neither pending runtime gates nor independent review are claimed green.
- Decision: iterate

## Risks and rollback

- Risks: a text-only fixture could be vacuous; calling a copied predicate would miss the real guard; narrowing raw scanning can drop condition/parser protection; count drift can hide missing checks. Tests and immutable source proof address these boundaries.
- Rollback or recovery: revert this one test-guard PR; no data/schema/production-CSS change.

## Pause and escalation conditions

- Stop before helper implementation until actual hosted behavior RED is inspected.
- Escalate new owner/product/parser scope; no silent iteration extension, assertion weakening or native acceptance claim.

## Final evaluation

- Validator command: python3 /Users/m.oluwole/.agents/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/17tnw2b1f30-pp-gen-var-filter.md
- Validator result: Initial structural validation PASS; revalidated with each source checkpoint.
- Independent verification result: Pending root-owned reviews.
- Terminal state: ACTIVE, observed test-first defect; corrected candidate awaiting hosted verification and independent review.
- Remaining failed or blocked criteria: C-001 through C-005 pending.
- ClickUp final evidence comment: Root owns delivery updates and persisted QA readback after passing merge gates.
