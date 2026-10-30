# Goal Contract — TASK-17tnw2aynax

## Identity

- Goal ID: TASK-17tnw2aynax
- Parent goal ID: WAVE2-SELAHCUE-20
- Title: Library snapshots keep plan-linked presentation names and missing status current
- Role: frontend-engineer
- Status: ACTIVE
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/17tnw2aynax
- Created: 2026-10-30
- Updated: 2026-10-30
- Maximum iterations: 8
- Independent verification required: yes

## Objective

Applying an authoritative presentation-library snapshot updates the shared plan-deck resolution data and its rendered consumers, so library changes do not leave stale names or false missing-presentation chips.

## Baseline

Verified at fresh main9d3febdc56f92560a469fe2a37590a0f4017ff28: planLoadDecks already has planDecksGen/planDecksLatest guards, including superseded return-value behavior, from merged PR100. Task comment1400430000020123 explicitly identifies that part as complete. The remaining pmApplyLibrary function updates only pmLibDecks/open/persistence/restorable and library grid; it never publishes the same snapshot to planDecks. Console render also caches its host-view signature independently of library data.

## Inputs and evidence sources

- Complete original task/comments: wave2-20261029/frontend-qualification/17tnw2aynax-live.json and qualifications.md.
- Current app.js planLoadDecks, pmApplyLibrary, link chips/cards/summary and render signatures.
- Existing operator_headless.py real library interactions and PR100 race/return-value/catch-path controls; root and desktop CLAUDE.md.

## Scope

### In scope

- Remaining library-snapshot publication/invalidation seam, shared plan-deck resolution and dependent render-cache invalidation.
- Behavioral tests of library mutation snapshots, latest-data ordering, stale return values and truthful unknown versus empty states.
- Hosted behavioral RED/GREEN, measured exact count and isolated mutation/restored proof.

### Non-goals

- Reimplementing completed PR100 request-ordering guards, unrelated library request policy, new UI or backend/API contracts.
- Other operator signal/CSS tickets, notes/auth source, new per-mutation network polling or global performance refactors.

### Constraints

- One isolated managed worktree/branch/PR; preserve concurrent agents' work. Ordinary current-main integration before publication.
- No local project runtime/build/benchmark/browser while host is paging. Hosted actual behavioral RED precedes production edits.
- Root delegates own diagnostic refs, feature push and draft PR/attachment/full applicable CI; root retains ClickUp, all four reviews, merge and QA. No force pushes or protected-branch edits.
- Preserve all existing PR100 guards and tests, invalid/failed-load honesty, rendering/focus protections and live-output safety.

### Assumptions and unknowns

- VERIFIED: library mutation handlers already apply LibraryView replies through pmApplyLibrary; the remaining defect is shared resolution state, not a new mutation workflow.
- UNKNOWN: exact remaining runtime failures/count and final review/CI outcomes until hosted execution.

## Dependencies and approvals

- Root explicitly selected the residual pmApplyLibrary gap; comment1400430000020123 preserves the already-complete generation-counter history. No new owner/design decision is required to apply existing library data to existing chips.
- Root owns source review routing and final publication beyond draft/CI, merge and QA.

## Completion predicate

All mandatory rows must be PASS for VERIFIED_COMPLETE.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Library snapshots update plan-deck names, counts and missing/resolved chips without an extra deck-list request or plan-surface visit | Full required operator_headless.py | Real mutation/application and DOM assertions pass after baseline RED, including held Library reads | Review RED41039166869; all NAX controls pass corrected41040420006 | PASS |
| C-002 | yes | A library snapshot supersedes an older in-flight plan load, including returned values and stale failures | Full operator headless existing/new concurrency controls | Latest snapshot remains authoritative; old caller receives latest data; obsolete Library replies cannot roll it back; PR100 controls retain passing behavior | Review RED41039166869; all concurrency/PR100 controls pass corrected41040420006 | PASS |
| C-003 | yes | Unknown/malformed library data does not become a false missing snapshot; a genuinely empty known library still marks missing | Full operator headless positive/negative controls | Unknown stays unresolved, empty remains missing; legitimate mutation data remains usable | Hosted41036840407 controls | PASS |
| C-004 | yes | Applicable full CI and isolated publication-hook mutation proof pass | Normal operator CI plus baseline/mutant/restored full headless runs | Required gates green; exact hook mutant causes named assertions; restored source passes measured strict count | Hosted CI/mutation receipts | PENDING |
| C-005 | yes | All independent reviewers approve frozen source | Cody, Quinn, Vera and Shadow | No unresolved blocking findings after remediation/re-review | CODY-NAX-01 Medium, deduplicated by Quinn; correction and all four current-source reviews pending | PENDING |

## Verification plan

- Focused verification: full real operator DOM harness with sibling PR100 race controls retained; actual library reply paths and rendered link state.
- Broader regression verification: normal path-filtered operator CI, strict measured headless count and WebKit smoke; no claim of owner-native Tauri or unexecuted OS coverage.
- Independent verifier: root coordinates Cody, Quinn, Vera and Shadow.
- Required environment: isolated hosted Chrome for behavioral diagnostics; full normal pinned operator CI/toolchains and WebKit. Local checks limited to source, structural validation, stdlib AST and Git evidence.

## Iteration ledger

### Iteration 1

- Target criterion: C-001 through C-003.
- Hypothesis: pmApplyLibrary receives fresh deck data but leaves shared plan resolution and cached rendering unchanged; an earlier held planLoadDecks can also overwrite a newer library mutation unless publication joins the existing generation mechanism.
- Change or investigation: read complete original task/comment and current main; confirm PR100 portion already complete. Prepare tests-only real DOM/ordering regressions and controls against unchanged production.
- Verifier executed: hosted full DOM run41035953241 on tests-only2123e0727ee7391166d986b2f601725db849e7a6; inspect raw plandecks-library/red.log.
- Result: Actual2376 checks,10 named NAX failures. Existing PR100 ordering/catch/returned-value controls and all other sibling assertions passed; known-present, no-extra-request, actual rename/delete dialog controls passed. Exact old2358 count additionally exited4. No setup/runtime exception.
- New evidence: diagnostic4b2838a400210a5c07956d8743123883437497a6; red-receipt.json/red-status.json/red.log retained outside source.
- Decision: iterate

### Iteration 2

- Target criterion: C-001 through C-003.
- Hypothesis: publishing LibraryView data through the existing generation/latest pair supersedes old reads; clearing the console render signature repaints unchanged host views on their normal poll.
- Change or investigation: narrow pmApplyLibrary publication with unknown-versus-empty preserved, no network calls; preserve PR100 planLoadDecks unchanged. Restore the existing editor-name fixture changed by the real Rename action in test cleanup.
- Verifier executed: stdlib Python AST, structural validator and full baseline diff check; hosted full DOM run41036840407 on31e248df/d02e4ec7.
- Result: All2376 behavioral checks pass, including18 NAX assertions/controls and all existing PR100/siblings. Run failed only the old exact2358 count (exit4); count updated to measured2376 without test removal or bound changes.
- New evidence: plandecks-library/green1-receipt.json, green1-status.json and green-attempt1.log. Main dcdb4f64433a5631465de7ad62ff2e1235349c05 ordinary-integrated conflict-free at f022d28545c0afd9f80271f7d7cd6cc1e8d03956; zero behind, scoped operator source unchanged by integration.
- Decision: iterate

### Iteration 3

- Target criterion: C-004.
- Hypothesis: the strict measured count now exits0; an isolated copy with the publication hook removed reproduces named NAX failures while existing PR100 and no-extra-request controls remain active.
- Change or investigation: exact measured2376 count only; own hosted baseline/mutant/restored full-suite workflow prepared with unique real production anchor.
- Verifier executed: hosted mutation/restored proof and normal applicable CI pending.
- Result: Historical source13c921d2 full normal CI41037305776 passed selected Linux jobs (Chrome2376/0, WebKit44/0; existing ignored/native boundaries retained). Mutation attempt1 FAILED: baseline2376/0, publication mutant2376/10 NAX, restored2376/1 Remote no-op approve failure; timing cause unproven. One unchanged-source rerun41038070717 succeeded baseline2376/0, mutant2376/10 NAX, restored2376/0, with16 restored dist files byte-identical. These results do not waive the subsequent review finding or apply to corrected source automatically.
- New evidence: plandecks-library/mutation-attempt1.log, mutation-attempt1-object-proof.json, mutation-attempt2.log, mutation2-status.json; root pr287-green-ci.log. All actual failed attempts retained; no ignored/retried assertion wrapper.
- Decision: iterate

### Iteration 4

- Target criterion: C-001, C-002 and C-005 / CODY-NAX-01.
- Hypothesis: an actual older pmLibLoad reply can publish after completed Undo/Restore, replacing the current shared plan snapshot and superseded plan caller's data; stale failure/busy ownership also needs the same issue-time boundary.
- Change or investigation: read full independent Cody/Quinn findings; verify actual async Tauri/interactive Library source path. Tests-only1741f405 keeps production identical to13c921d2 and holds real Library read, clicks actual Undo, releases obsolete response plus held plan caller; adds stale-failure and overlapping reload controls while preserving prior assertions.
- Verifier executed: hosted full DOM41039166869, diagnosticdc5a76272786bcf3f44947cdbd704529814cea3e.
- Result: Actual2384 checks /4 named behavioral failures: restored plan/grid rollback, stale returned data, obsolete failure clears current grid, old completion clears new busy state. Real held-read/Undo/no-extra-request/latest ordinary reload positive controls and all other siblings passed. Old2376 exact guard separately exits4. Actual RED observed before production correction.
- New evidence: plandecks-library/review-red.log, review-red-status.json and review-red-receipt.json.
- Decision: iterate

### Iteration 5

- Target criterion: C-001, C-002 and C-004.
- Hypothesis: the latest Library read identity plus captured shared plan generation fences obsolete success/error publication; latest-read-only finally preserves the pending indicator while mutation publications retire older reads through the existing shared generation.
- Change or investigation: minimal pmLibLoad fence, no new network request/timer; planLoadDecks and authoritative unknown/empty semantics unchanged. Hosted500bc35f corrected DOM measurement pending before exact count update.
- Verifier executed: stdlib AST and full initial-baseline diff checks; hosted corrected full DOM41040420006 on500bc35f, diagnostic8656b5056ba0b42d72b0429f99ec7aaf43eee3a2.
- Result: Actual2384 checks; all original NAX, all8 new Library-read and all PR100 controls pass. One earlier unchanged Remote no-op remote_approve feedback assertion failed; timing causation remains unproven. Old2376 exact guard separately exits4. Guard updated to measured2384, with every assertion retained. Not claimed full GREEN. Current two-mutant/restored proof and fresh normal CI pending; no local project runtime.
- New evidence: plandecks-library/review-green1-receipt.json, review-green1-status.json and review-green-attempt1.log. Actual mainb01ce4e6860be99db2f82a71aef10c4ae229db8a ordinary-integrated at8adbc1ca5972d493c929021378c8079fe8d55fa1, no operator overlap, zero behind at integration. Historical13c source remains separately recorded.
- Decision: iterate

### Iteration 6

- Target criterion: C-004 and fresh C-005 review input.
- Hypothesis: exact measured2384 guard permits a truthful complete suite verdict; both removed snapshot-publication and Library-read fences must produce named assertions with all siblings active, and byte-identical restored source must pass before claiming current mutation proof.
- Change or investigation: strict count update only plus current-source hosted full normal CI and isolated-copy two-mutant/restored workflow. No retries, ignored assertions, Remote production/test changes or weakened controls.
- Verifier executed: local structural/stdlib/full baseline checks; actual25f8a347 normal41040926924 and two-mutant41040814878 raw logs inspected.
- Result: Normal CI FAILED only Chrome2384/1 Remote no-op approve; WebKit44/0 and other selected Linux gates pass with existing ignored boundaries. Two-mutant proof SUCCESS: baseline2384/0, publication mutant2384/15 (14 NAX plus same Remote failure), read-fence mutant2384/4 (3 named review failures plus same Remote), restored16-file identical2384/0. Required positive controls pass. Cody/Quinn close CODY-NAX-01 but block full certification on Remote boundary; no NAX source defect remains in reviewed code.
- New evidence: plandecks-library/current-full-ci.log/status, current-mutation.log/status/object proof, independent r2 reports. Failed complete CI is retained, never waived by the successful mutation baseline/restoration.
- Decision: iterate

### Iteration 7

- Target criterion: C-004, evidence-backed immediate-action test observation.
- Hypothesis: the no-op test yields to a normal periodic poll after its mock-settled action completes, so it observes subsequent snapshot recovery instead of immediate action feedback.
- Change or investigation: observation-only exact25f8a347 hosted diagnostic; first41042050152 failed checkout parent preflight before runtime, retained separately. Repaired41043082668 reached full2384/1 runtime with434 trace rows; raw ZIP required because formatted log streaming omitted the181KB JSON line. Exact first-approve event order:21267.6ms completion/showUnconfirmed visible flex/finally busyfalse;21273.9ms real poll snapshot hides warning;21287.5ms original20ms wait resumes and assertion fails while live remains not-confirmed. This proves the poll-interleaved oracle for the observed failure, not harmlessness or every prior failure's cause.
- Verifier executed: actual repaired trace/event state, unchanged assertions/timers in isolated copies; stdlib AST and source comparison for proposed harness correction.
- Result: Replace only mock-settled no-op waits with existing bounded settleMicro; retain every visibility/live/list/role assertion and strengthen list checks with successful completion. Real polls, sleeps elsewhere and Remote production remain unchanged. No ignore or retry wrapper; current full CI and Remote-feedback sensitivity mutation still required.
- New evidence: plandecks-library/remote-trace-repaired-raw.zip, remote-trace-repaired-step-raw.log, remote-trace-events.json, remote-first-approve-events.json/.md and remote-trace2-receipt.json. Earlier setup failure and all behavioral failure history retained.
- Decision: iterate

### Iteration 8

- Target criterion: C-004 and C-005 final corrected candidate gates.
- Hypothesis: microtask completion observes immediate no-op feedback deterministically while the full suite's normal polls still run; removing the actual no-op unconfirmed branch must make all four contract assertions fail, alongside independently sensitive NAX publication/read-fence controls.
- Change or investigation: frozen harness-oracle correction plus existing full2384 strict gate; ordinary current-main integration; fresh normal CI and isolated full-sibling baseline/three-mutants/byte-identical-restored proof. No product Remote changes or count/assertion removal.
- Verifier executed: local structural/AST/full baseline checks, then hosted final source normal CI and three-mutant proof; all four final-source reviews root-owned.
- Result: Pending actual final-source runtime/CI/mutation/review results. Maximum8 reached for planned implementation iterations; further substantive source work requires root replan, never silent budget extension. No local project runtime.
- New evidence: final immutable source/receipts and external handoff to root; root owns completion copy once gates actually pass.
- Decision: handoff

## Risks and rollback

- Risks: updating data without render invalidation leaves chips stale; clearing to an empty array invents missing content; failing to supersede old requests restores stale data or return values. Tests exercise each boundary.
- Rollback or recovery: revert this one PR; no persisted data/schema/migration change.

## Pause and escalation conditions

- Stop implementation until actual hosted assertion RED is inspected.
- Escalate a genuine new policy/design or API requirement; do not silently widen the residual ticket or weaken counts/bounds.

## Final evaluation

- Validator command: python3 /Users/m.oluwole/.agents/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/17tnw2aynax-plandecks-library-invalidation.md
- Validator result: PASS structural validation on 2026-10-30; no local project runtime executed.
- Independent verification result: Pending root-owned reviews.
- Terminal state: ACTIVE, final bounded verification of evidence-backed oracle correction; current mutation/full CI and all four final-source reviews pending, all earlier failures retained.
- Remaining failed or blocked criteria: C-004 and C-005 pending.
- ClickUp final evidence comment: Root owns delivery updates and persisted QA readback after passing merge gates.
