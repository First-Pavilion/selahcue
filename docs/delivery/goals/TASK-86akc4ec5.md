# Goal Contract — TASK-86akc4ec5

## Identity

- Goal ID: TASK-86akc4ec5
- Parent goal ID: NONE
- Title: Installer scanner controls run in ordinary CI, including docs-only changes
- Role: devops-engineer
- Status: ACTIVE
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86akc4ec5
- Created: 2026-11-04
- Updated: 2026-11-04
- Maximum iterations: 4
- Independent verification required: yes

## Objective

The existing scanner self-test runs automatically for normal main pushes and pull requests, including docs-only and API-only changes, and a broken control fails its job.

## Baseline

Verified main c0325d52e809847fac141a605b74a7e6d7de7021. Actual scanner self-test passes45 cases. ci.yml does not invoke it; ordinary docs are excluded before that workflow starts. The scanner and Windows installer workflow must remain unchanged. Ticket In Progress saved/read back, start comment1400430000278591.

## Inputs and evidence sources

- Live ticket86akc4ec5, full description, no comments/dependencies at start.
- scripts/installer_secret_scan.py and existing CI/trigger/permission/minute controls.
- Existing visual-audit trigger contract intentionally excludes ordinary docs.

## Scope

### In scope

- Automatic self-test wiring and focused event/wiring/failure evidence.
- Cheap docs-safe route preserving existing CI event exclusions, approved by root.

### Non-goals

- Scanner logic/signature changes, optional NSIS extraction/real-artifact controls, release packaging, SDK/runtime/provider/secrets access and deployment.
- Database, migration, backup, production capacity and infrastructure rollout criteria are inapplicable to this CI-only source change.

### Constraints

- One ticket/branch/PR, isolated worktree; preserve other agents' work and the user's primary mobile lock modification.
- Only --self-test; no real installer artefacts or full scan. Preserve manual/main-only installer admission and existing visual/NDI/SBOM gates.

### Assumptions and unknowns

- Root approved a dedicated unfiltered lightweight workflow plus the ordinary ci.yml call; duplicate normal-code execution is an explicit subsecond tradeoff.

## Dependencies and approvals

- Current user authorized the next delivery wave, agents moving actual work In Progress, four reviews and root merge/QA.
- Root owns CI-route decision, four independent review dispatch and final merge/main/QA.

## Completion predicate

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Existing self-test is automatic for normal source/API/docs events | Actual workflow structure and trigger/wiring controls | No docs/API path can omit the self-test | docs/delivery/evidence/86akc4ec5.md | PASS |
| C-002 | yes | Broken scanner control fails the same CI command | Actual scratch scanner mutation, positive command first | Nonzero self-test exit and job failure propagation | docs/delivery/evidence/86akc4ec5.md | PASS |
| C-003 | yes | Self-test-only scope is fast and installer behavior unchanged | Actual timed command, diff and workflow/permissions/minute checks | Under5s, no scanner or windows-installer.yml changes, no artifacts/build | docs/delivery/evidence/86akc4ec5.md | PASS |
| C-004 | yes | Final source passes four independent reviews and applicable hosted CI | Root Cody/Shadow/Quinn/Vera and exact-head checks | Four passes and actual CI success before merge/QA | PR/root reports | PENDING |

## Verification plan

- Focused verification: actual scanner self-test, broken-control negative, event/wiring cases and failure propagation.
- Broader regression verification: actionlint, workflow scopes/ordering/cache controls, minute policy and preserved existing visual gate controls.
- Independent verifier: root coordinates Cody, Shadow, Quinn and Vera.
- Required environment: local Python standard library and hosted Ubuntu normal CI; no installer dispatch.

## Iteration ledger

### Iteration 1

- Target criterion: C-001 through C-003.
- Hypothesis: a lightweight docs-safe CI route can exercise existing scanner fixtures without widening the expensive workflow's docs trigger.
- Change or investigation: root-approved dedicated docs-safe workflow, ordinary CI invocation and focused wiring controls implemented.
- Verifier executed: actual self-test and scratch vacuity mutation; focused event/bypass controls; existing workflow/minute/visual controls and actionlint.
- Result:45 cases passed in0.427s; actual disabled scanner exits1 with30 failed cases;8 representative event/path cases and7 rejected bypass mutations pass. Existing controls pass across7 workflows.
- New evidence: docs/delivery/evidence/86akc4ec5.md.
- Decision: local source gate passes; freeze for independent review and hosted CI.

### Iteration 2 — explicit manual review cycle3 integration

- Target criterion: C-001 through C-004 current-source compatibility.
- Hypothesis: normal integration of published CSP93/currentmain scanner9/47 preserves tiny CI wiring, while an independent additive baseline policy rejects coordinated scanner rollback.
- Change or investigation: root explicitly authorizes ONE further implementation/integration iteration for manual reviewcycle3 after automaticrefresh cap2. Existing Goalmax4/iteration1 preserved; this is actualimplementationiteration2, not an invented reset. Normalmerge31f2939f integrates93e5875c andmaina6 without conflict. Exact five-authored-file scope remains.
- Verifier executed: actual coordinatedold8/45 scanner mutant selftest exits0 before newpolicy (demonstrates missing independentbaseline); current47normal/-O plus wiring/policymutants/currentworkflow/minute/actionlint pending.
- Result: PASS current47normal/-O,8eventcases/7wiringmutants/9newpolicymutants, actualdisabledscannerexit1 and actualcoordinatedold8/45source rejection. Currentworkflow/cache/minute/visual/supply/canary/Linuxinstaller/actionlint/whitespace allPASS; scanner/Windowsworkflow bytes equal93. Allprocessesfinished.
- New evidence: no scanner/runtime/Windowsworkflow production change by this ticket; CSP373 actualmergeb5b17f1e nowverified. Normallyintegratedcurrentmain364(menu374only) beforefinalfreeze, allCI/scanner/controlinputbytes unchanged andactualauthoreddiffexactfivefiles.
- Decision: freeze/handoff after onefocusedset; root allfour manualrefresh3/currentCI/merge owns finalgates.

## Risks and rollback

- Risks: docs exclusions hide the gate, conditional/continued failures mask it, or full scan runs without artifacts. Focused wiring/negative checks must reject those cases.
- Rollback or recovery: revert this isolated ticket; no persisted product data changes.

## Pause and escalation conditions

- Report any required change to scanner semantics, Windows installer behavior, runner policy or source outside this ticket before expanding scope.
- No retry after actual publication rejection; freeze exact payload for root review/approval.

## Final evaluation

- Validator command: python3 /Users/m.oluwole/.agents/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/TASK-86akc4ec5.md
- Validator result: structural validator PASS (exit0).
- Independent verification result: pending root reviews.
- Terminal state: GATE_REVIEW.
- Remaining failed or blocked criteria: C-004 independent reviews and hosted CI pending; local implementation criteria pass.
- ClickUp final evidence comment: pending.
