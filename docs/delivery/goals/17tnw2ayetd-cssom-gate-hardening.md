# Goal Contract — TASK-17tnw2ayetd

## Identity

- Goal ID: TASK-17tnw2ayetd
- Parent goal ID: WAVE3-SELAHCUE-20
- Title: Restore CSSOM fixture globals and pin the headless viewport
- Role: frontend-engineer
- Status: ACTIVE
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/17tnw2ayetd
- Created: 2026-10-30
- Updated: 2026-10-30
- Maximum iterations: 8
- Independent verification required: yes

## Objective

The operator CSSOM-PARSE global fixture swaps restore the real stylesheet even when an assertion/helper throws, and the browser gate launches with an explicit deterministic viewport, retaining all existing CSSOM/filter controls and full-driver behavior.

## Baseline

Actual main826076a6436708dd51fd8d7bee56e0bd7e25741d includes approved AYZVG and measured2556 headless checks. CSSOM-PARSE-03/05 still swap window.__CSSTEXT and manually restore without try/finally. The operator headless launcher still has no explicit --window-size. Item3 comment stripping was already hoisted by PR139 and is not new work.

## Inputs and evidence sources

- Full frontend-qualification/17tnw2ayetd-live.json task, no parent/dependencies/linked tasks; two full comments, no thread replies. Latest narrowing comment1400430000047748 explicitly leaves only items1 and2. Corroborating comment1400430000014538 records the restore-integrity concern.
- Fresh full root UI dispatch packet frontend-qualification/17tnw2ayetd-dispatch-ui.txt matches the original description/two comments and narrow items1/2; root confirms persisted In Progress and authorizes implementation. Runbook AGENT-RUNBOOK.md and frozen WAVE3 selection authorize only this selected unit.
- Current scripts/operator_headless.py CSSOM-PARSE-03/05 and shared headless launcher/test patterns; applicable repository/role/runtime guidance.

## Scope

### In scope

- Narrow try/finally protection around the existing global stylesheet fixture swaps, with meaningful exception/restoration and unsafe-reversion controls.
- Explicit supported viewport in this gate's existing launcher arguments, verified through the actual argument path and complete hosted driver.
- Focused existing-pattern tests, measured strict count only if actual assertion additions change it, child execution evidence.

### Non-goals

- Reimplementing already-fixed item3, parser/predicate/candidacy changes, condition-aware raw scanning, broader launcher redesign, new product UI or physical/native acceptance claims.
- Other selected tickets or changes to app shipping assets, API, Flutter, Rust or permissions.

### Constraints

- Own isolated worktree/codex branch/one draft PR; not alone, preserve others; no staging/reverting other agents' work.
- No local project runtime/import/install/tests/build/browser/benchmarks/containers. Tiny Git/source/stdlib/static checks only; actual behavior and complete driver run hosted.
- Preserve all existing assertions, CSSOM/F30/WKG/AYZVG controls and limits. No ignored failures/retry wrappers/guessed counts or fabricated product RED for coverage debt.
- Root owns fresh task/start, all4 independent reviews, remediation routing, merge and QA. Author owns ordinary push/draft/body-file/immediate attach and bounded exact-parent workflow-only diagnostics. No next unit.

### Assumptions and unknowns

- VERIFIED: only items1/2 remain, owner narrowing excludes comment-strip hoist from new delivery.
- UNKNOWN: exact exception-path test seam and observed viewport/whole-driver outcomes until hosted execution. Choose the smallest existing-pattern fixture/launcher checks; retain actual failures as evidence.

## Dependencies and approvals

- User authorizes selected WAVE3 workflow; root dispatch authorizes preparatory read/worktree/Goal now, implementation after fresh root UI packet.
- Previous AYZVG merged826076a6 and QA persisted; completed child evidence exported with --completion PASS, no merged source churn.

## Completion predicate

All mandatory rows must PASS for VERIFIED_COMPLETE.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | CSSOM-PARSE global swaps restore real stylesheet after normal and exceptional execution | Actual existing block exception injection and normal full driver | Original global content restored on every exit; unsafe restore reversion detected | Hosted focused integrity/raw proof | PENDING |
| C-002 | yes | Headless gate passes explicit deterministic viewport through existing launch argument path | Existing-pattern launcher argument control plus real browser observation | Exactly one chosen window-size reaches launcher; unpinned mutant fails without changing acceptance bounds | Hosted launch/viewport receipts | PENDING |
| C-003 | yes | Existing CSSOM/filter/whole-driver behavior remains valid and new integrity controls are sensitive | Full siblings plus meaningful unsafe-restore/unpinned mutations and identical restoration | Actual named failures under removed safeguards; restored complete driver clean | Current exact-parent/raw/hash proof | PENDING |
| C-004 | yes | Normal affected CI passes on final source | Normal configured whole-driver and applicable CI | All selected gates succeed with actual measured count; skipped domains explicit | Official metadata/raw receipts | PENDING |
| C-005 | yes | All four independent current-source reviews pass | Root-owned Cody/Quinn/Vera/Shadow review/remediation | No unresolved blocking finding | Root consolidated report and manifest | PENDING |

## Verification plan

- Focused verification: real global fixture exception restoration and actual launcher argument control, not a separate copied safety oracle. Meaningful mutants must prove the precise protections.
- Broader regression verification: complete operator headless CSSOM/F30/WKG/AYZVG/geometry siblings at chosen explicit viewport; normal affected pipeline. Pin count only after actual measurement.
- Independent verifier: root coordinates all four roles, target freshness and actual merge/QA evidence.
- Required environment: hosted Linux Chrome and normal applicable jobs. No physical/native/macOS/Windows acceptance inferred.

## Iteration ledger

### Iteration 1

- Target criterion: C-001 through C-002 readiness.
- Hypothesis: two narrow harness changes can close the latent restore and implicit-viewport gaps while preserving existing behavior; already-fixed comment-strip code needs no change.
- Change or investigation: read full saved task/two comments, runbook and fresh dispatch; create isolated branch from actual826076a6 and validate child contract. Tests-only extraction of existing unsafe CSSOM03/05 bodies into local functions retains original normal semantics and manual restores. Add actual helper-exception probes at all three swapped states, with later-sibling isolation after observing real cleanup. Add real operator-caller argument contract in already-CI-wired test_pipe_safe_launchers.py and actual browser viewport observation. No safe restoration or explicit flag yet.
- Verifier executed: Goal structural validator, stdlib AST and source/Git preparation; hosted unchanged-safeguard RED/controls next.
- Result: Actual hosted41134054406 on tests-onlyf85996cc ran2565 checks with4 intended behavioral failures: all3 cleanup cases and actual implicit viewport780x580/780x493. Every prior assertion, real throw premise and isolation control PASS; old2556 strict-count mismatch separate. Actual caller test fails once because no window-size reaches the launcher; subsequent caller assertions are unexecuted at this RED, not implied passes.
- New evidence: cssom-gate-hardening preparation/dispatch receipts in wave3 evidence root.
- Decision: iterate

### Iteration 2

- Target criterion: C-001 through C-004.
- Hypothesis: finally restoring each actual global-swap function and explicitly passing800x600 removes the observed integrity/implicit-geometry gaps without changing parser/predicate semantics or acceptance bounds.
- Change or investigation: add two narrow try/finally blocks, one launcher window-size argument, adjacent outdated viewport comment, and pin actual measured2565. Preserve all original/new assertions and CSS_SRC/comment hoist byte-for-byte.
- Verifier executed: actual RED/raw classification, stdlib AST, full baseline diffcheck, structural Goal validation; exact-source hosted sensitivity/full restoration and normal CI next.
- Result: Static preparation PASS; current runtime/normal CI/four independent reviews pending, no completion claim.
- New evidence: cssom-gate-hardening/red-ci metadata/raw/hash archive, red-classification.json and current candidate receipts.
- Decision: iterate

## Risks and rollback

- Risks: a copied test oracle misses the actual global block, deliberate exception aborts unrelated suite, explicit geometry exposes layout assumptions, or old guards are accidentally weakened. Exercise actual block/argument path with bounded diagnostic copies and restore exact source/components.
- Rollback or recovery: revert this single scoped harness PR; no data/schema/product state change.

## Pause and escalation conditions

- No code before fresh root UI packet. Escalate genuine scope/policy/native requirements rather than inventing them.
- Maximum8 iterations and three materially different no-progress attempts remain binding. Preserve actual failures and classify setup/oracle defects separately.

## Final evaluation

- Validator command: python3 /Users/m.oluwole/.agents/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/17tnw2ayetd-cssom-gate-hardening.md
- Validator result: Initial structural validation PASS before tests; no completion claim.
- Independent verification result: Pending all four root-owned reviews.
- Terminal state: ACTIVE, preparatory gate only.
- Remaining failed or blocked criteria: C-001 through C-005 pending.
- ClickUp final evidence comment: Root owns external tracker updates and persisted QA readback.
