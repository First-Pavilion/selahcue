# Goal Contract — TASK-17tnw2ay5jh

## Identity

- Goal ID: TASK-17tnw2ay5jh
- Parent goal ID: WAVE2-SELAHCUE-20
- Title: Output-health status changes have persistent polite live-region feedback
- Role: frontend-engineer
- Status: ACTIVE
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/17tnw2ay5jh
- Created: 2026-10-30
- Updated: 2026-10-30
- Maximum iterations: 8
- Independent verification required: yes

## Objective

Expose genuine selected-output health text changes through a pre-existing polite atomic live region without focus movement or repeated identical announcements, preserving existing NDI feedback and output controls.

## Baseline

Verified fresh main `894069e6e1f8f61015d7025e1b75e1f22ed8592f`: NDI .scr-signal already has role=status and changes its existing node for validation. The OutputHealth footer remains a plain div created/populated during each inspector rebuild. renderOutputs gates identical snapshots and defers full rebuilds for focused select controls. Merely adding role=status to a populated, newly inserted footer would not establish a pre-existing live region for updates.

## Inputs and evidence sources

- Complete original task and empty comments: wave2-20261029/frontend-qualification/17tnw2ay5jh-live.json; qualifications.md. The brief's non-live filename is absent.
- Current app.js renderOutputs/renderInspector/syncEnableState, status text branches and NDI validation.
- Existing persistent route-status/notif-live HTML pattern and operator_headless.py real Screens/NDI/focus controls.
- Applicable root/desktop CLAUDE.md and frontend/goal operating contracts.

## Scope

### In scope

- Residual selected-output health announcement boundary and minimal persistent live-region markup using existing patterns.
- Real DOM/status-change/deduplication/focus/escaping/clear controls; existing NDI behavior retained.
- Hosted test-first RED, bounded correction, full applicable CI, meaningful isolated mutation/restoration and measured strict count.

### Non-goals

- Reimplementing already-fixed NDI validation, output control policy, telemetry fabrication or new native output capabilities.
- New UX policy, broad screen-render refactor, unrelated CSS/PP-GEN/filter tickets or deferred R6 acceptance.
- Claiming actual VoiceOver/native macOS/Windows speech acceptance from portable DOM metadata or Linux browser tests.

### Constraints

- One new isolated managed worktree/branch/PR; preserve concurrent agents' work. Ordinary current-main integration before first PR publication.
- No local project runtime/build/browser/benchmark while host is paging. Actual hosted behavioral RED precedes production edits.
- Own bounded diagnostic/ordinary feature push/draft PR and immediate attachment allowed; root owns ClickUp/UI/status, four independent reviews, merge and QA.
- Preserve output focus/deferred-change/clear behavior, plain-text escaping and existing live regions; avoid duplicate announcements and repeated unchanged telemetry writes.

### Assumptions and unknowns

- VERIFIED: only the OutputHealth signal remains without an announcement channel; original NDI rejection role and real behavior controls exist.
- UNKNOWN: actual hosted failures/count and final runtime/CI/review outcomes until executed.

## Dependencies and approvals

- Root selected this residual slice after NAX PR287 merged; no concurrent owner edits to app.js for this ticket. Implementer owns only health status UI, focused tests and this Goal.
- User-authorized implementation/review/remediation pipeline applies. Root records tracker start/status and final QA readback.

## Completion predicate

All mandatory rows must be PASS for VERIFIED_COMPLETE.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Genuine selected-output health text changes update an already-connected polite atomic status channel | Real DOM full operator_headless.py | Persistent live metadata precedes change and observed health updates reach it without focus movement | Hosted41051898145, output-health-status/green-attempt1.log | PASS |
| C-002 | yes | Identical or unrelated updates do not rewrite the same health announcement; selection/unknown/closed/clear remain truthful | Real DOM transition and dedup controls | Changed health/selection updates once; identical health produces no repeated text mutation; current empty/unknown state never retains stale warning | Hosted41051898145 actual mutation/clear controls | PASS |
| C-003 | yes | Existing NDI validation/revert, text safety and focused-picker behavior remain intact without duplicate health channels | Full existing/new Screens DOM controls | NDI statuses retain behavior, no markup interpretation/focus loss, one health announcer, picker deferred behavior preserved | Hosted41051898145 full siblings/positive controls | PASS |
| C-004 | yes | Full applicable CI and meaningful current-source mutation/restoration pass with exact measured suite count | Normal operator CI and isolated full-sibling mutation proof | Required gates green, removing actual health publication causes named failures, restored source passes | Hosted raw logs/receipts | PENDING |
| C-005 | yes | Four independent reviewers approve final frozen source | Cody, Quinn, Vera and Shadow | No unresolved blocking findings after remediation/re-review | Root consolidated review | PENDING |

## Verification plan

- Focused verification: scripted host view through real output render/selection/focus handlers and DOM MutationObserver; metadata tests establish portable live-region wiring, not actual speech.
- Broader regression verification: full operator headless siblings, normal path-filtered Linux operator/Rust/native-feature/launch/audit gates and WebKit smoke, retaining ignored/native boundaries.
- Independent verifier: root coordinates all four final-source reviewers.
- Required environment: hosted Chrome and normal pinned CI toolchains/WebKit. Local checks restricted to source, stdlib AST, structural validator and Git evidence.

## Iteration ledger

### Iteration 1

- Target criterion: C-001 through C-003.
- Hypothesis: current footer rebuild lacks a pre-existing live region; an existing persistent status channel with change-only plain-text publication can close the residual without duplicating NDI feedback.
- Change or investigation: read full saved task/comments/current main and existing status/render/focus patterns; isolate new managed worktree; prepare meaningful tests-only behavioral regressions and positive controls before product edits.
- Verifier executed: Goal structural validator/static checks; full hosted41048409738 on tests-onlyae6dfcdb, production byte-identical to base.
- Result: Actual2400 checks/13 failures:11 intended JH missing-channel/message assertions plus2 CON-089 fullscreen left-side hit tests. JH focus/dedup/defer/NDI controls passed, no exception. Old2384 exact guard separately exits4. Retain unexpected sibling failures; investigate new fixture focus/viewport isolation before claiming qualified baseline.
- New evidence: output-health-status/red.log, red-status.json and red-receipt.json.
- Decision: iterate

### Iteration 2

- Target criterion: C-001 through C-003 baseline fixture isolation.
- Hypothesis: new programmatic focus of right-side inspector controls scrolls the narrow viewport and contaminates later left-side fullscreen hit tests.
- Change or investigation: tests-only9e28a1b9 uses preventScroll for fixture focus and saves/restores initial window scroll. Every assertion retained; production app.js unchanged from base.
- Verifier executed: full hosted41050502853 / diagnostic02df0536a55927d8d62b9c161e812844cb5bbc19.
- Result: Actual2400 checks/11 failures, all named intended JH health-channel behaviors. All positive/focus/defer/NDI controls and both prior CON-089 hit tests now PASS; all other siblings PASS. Old2384 strict guard separately exits4. This qualifies behavioral RED before product changes; original failed run remains recorded.
- New evidence: output-health-status/red-isolated.log, red-isolated-status.json and red2-receipt.json.
- Decision: iterate

### Iteration 3

- Target criterion: C-001 through C-003.
- Hypothesis: one connected status/polite/atomic channel outside the rebuilt inspector, with changed-only plain-text publication of its current footer, announces genuine updates without repeated unrelated rebuild writes.
- Change or investigation: minimal existing-pattern persistent HTML span and app.js publication/empty clearing. Footer wording/visuals, NDI role/status behavior and focused-picker deferral unchanged. Add real empty-inspector clear control; preserve every prior test.
- Verifier executed: source/std-library AST, structural validator/full baseline diffcheck; actual full hosted41051898145 ondc27dc11410196db751dc043477207b7e7cad044 / diagnostica65e68bf4aa02d9cf42fdc7ab8c633d7916cab42.
- Result: Actual2401 checks/0 behavioral failures, every17 new JH and all existing siblings pass. Only old2384 strict guard exits4; updated to observed2401 without removing assertions or changing bounds. No local project runtime.
- New evidence: output-health-status/green1-receipt.json, green1-status.json and green-attempt1.log. Ordinary mainbd6f6a531dc3393959c49fa44a70d6c688e4b9c1 integrated at2f12fd1a1d3b9496189cce9aba3cf288d6bcf88d, no health source overlap; latest main will be fetched again before first PR publication.
- Decision: iterate

### Iteration 4

- Target criterion: C-004 and fresh C-005 review input.
- Hypothesis: the exact measured2401 guard exits0; removing the real publisher causes named health-update failures and removing its change-only predicate causes the unrelated-rebuild duplication assertion, while meaningful positives and restored full suite pass.
- Change or investigation: strict count update and bounded own hosted baseline/publication-mutant/duplicate-write-mutant/byte-identical-restored proof; ordinary fresh-main integration and full normal applicable CI. No local project runtime or native speech claim.
- Verifier executed: local structural/AST/full baseline checks; current-source hosted mutation and normal CI pending.
- Result: Pending actual current-source mutation/full CI and all four independent reviews.
- New evidence: own output-health-status mutation/normal receipts and immutable handoff to root; root owns completion copy.
- Decision: handoff

## Risks and rollback

- Risks: newly populated detached nodes may not announce; rebuilding/repeated identical writes can duplicate speech; focused-picker deferral or unsafe host text can regress behavior. Tests address these boundaries.
- Rollback or recovery: revert this one PR; no persisted data/API/schema change.

## Pause and escalation conditions

- Stop before production implementation until actual hosted behavioral RED is inspected.
- Escalate real product/policy/native requirement to root; no silent scope/budget extension, assertion weakening or guessed count.

## Final evaluation

- Validator command: python3 /Users/m.oluwole/.agents/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/17tnw2ay5jh-output-health-live-region.md
- Validator result: PASS structural validation on 2026-10-30; no local project runtime executed.
- Independent verification result: Pending root-owned reviews.
- Terminal state: ACTIVE, behavior observed passing; current exact-count full CI, mutation/restoration and four independent reviews pending.
- Remaining failed or blocked criteria: C-004 and C-005 pending.
- ClickUp final evidence comment: Root owns delivery updates and persisted QA readback after passing merge gates.
