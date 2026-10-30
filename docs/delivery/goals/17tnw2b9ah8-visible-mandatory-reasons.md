# Goal Contract — TASK-17tnw2b9ah8

## Identity

- Goal ID: TASK-17tnw2b9ah8
- Parent goal ID: WAVE2-SELAHCUE-20
- Title: Require a visible minimum for governed audit reasons
- Role: backend-engineer
- Status: IN_PROGRESS
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/17tnw2b9ah8
- Created: 2026-10-30
- Updated: 2026-10-30
- Maximum iterations: 8
- Independent verification required: yes

## Objective

The shared reason validator excludes Unicode format/control/separator codepoints from its minimum while preserving legitimate Unicode content, existing total-length and control refusals, coded errors and existing whitespace normalization across every actual governed writer.

## Baseline

Fresh main initially7f2e3573 was fast-forwarded to merged DB273 main9d3febdc56f92560a469fe2a37590a0f4017ff28 before tests. require_reason normalizes whitespace and counts every resulting codepoint, so8zero-width spaces or7visible letters plus an invisible separator satisfy its minimum. Existing C0/C1 refusal and1000cleaned-codepoint maximum must remain. Six call sites cover generation, suspend/reinstate shared service,3catalogue writers and the generic licence state machine.

## Inputs and evidence sources

- Full saved task/comments/dependencies: wave2-20261029/api-qualification/17tnw2b9ah8.json;0comments,0dependencies.
- Task explicitly excludes format/control/separator characters from the minimum, naming zero-width space/joiner/non-joiner/word joiner/BOM/bidirectional marks and overrides, while preserving emoji,CJK,combining and RTL text.
- Current context.py, all require_reason call sites, existing control-character/lifecycle/catalogue fixtures and shared licensing_test_support helpers.

## Scope

### In scope

- Minimum excludes exactly Unicode Cf,Cc,Zs,Zl,Zp categories named by the task. Remaining codepoints, including combining marks, retain current counting; no new grapheme/rendering policy.
- Preserve accepted text with format/joining/bidi/combining characters and existing whitespace normalization; do not strip legitimate formatting from persisted audit reasons.
- Existing maximum continues to count every cleaned codepoint so invisible padding cannot bypass it; existing C0/C1 control refusal remains.
- Unit negative classes and every actual writer integration: generate,suspend,reinstate,set_plan_grant,set_license_grant_override,set_license_plan_assignment,generic state transition exercised through revoke.

### Non-goals

- Held PR233 or absent extend/revoke staff mutation wrappers, identity/provider/database/dependency changes, Unicode grapheme segmentation/render detection, schema/migrations or changing raw legitimate audit content beyond existing normalization.

### Constraints

- No local project runtime, DB, pytest, containers or benchmarks under paging. Only static standard-library checks locally; hosted RED/GREEN required.
- Author may publish ordinary branch/draft PR, attach it and run bounded workflow-only diagnostics; no force push, merge, UI/ClickUp, external review posts or subagents. Parent owns four independent reviews, remediation routing, merge and QA.
- Preserve other agents' work and prior merged database/configuration work. Fetch/integrate actual main before first PR and report overlaps.

### Assumptions and unknowns

- Unicode categories are the task's explicit visibility boundary; combining marks continue to count and remain unnormalized. A universal display-visibility detector is outside scope.
- Actual current main has no staff-facing extend/revoke wrapper from held PR233; generic state writer's revoke path is tested without importing held work.
- Hosted runtime and independent reviews remain pending; static evidence is not execution proof.

## Dependencies and approvals

- User authorizes implementation, hosted CI, author remediation and review-passed merge/QA. Parent explicitly expands author authority to ordinary push/draft PR/attach and own bounded hosted diagnostics.
- Database PR273 is merged and integrated; its nonblocking dependency advisory remains separate.

## Completion predicate

All mandatory rows must be PASS for VERIFIED_COMPLETE.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Named format/control/separator classes cannot supply the visible minimum and all-format reasons fail with VALIDATION_FAILED | new focused unit matrices | behavioral RED then all expected refusals pass | wave2-20261029/api-visible-reasons/red.log and green evidence | PENDING |
| C-002 | yes | Emoji,CJK,combining,RTL and normalized whitespace remain accepted; total-length/custom-boundary controls remain correct | focused positive/boundary tests | text preserved and maximum not bypassed | hosted focused/full logs | PENDING |
| C-003 | yes | Every actual governed writer refuses each negative class without changing domain/audit rows, and positive Unicode reasons persist intact |7writer integrations and positive controls | VALIDATION_FAILED/no writes; valid model/audit reasons match | hosted tests and author handoff | PENDING |
| C-004 | yes | Current target-integrated source passes complete API checks,migrations and regressions with prior skips preserved | normal hosted API job | CI green and raw logs inspected | PR/run links and raw CI log | PENDING |
| C-005 | yes | Frozen source accepted by Cody,Quinn,Vera,Shadow and valid findings remediated/reviewed | parent independent review round | no unresolved findings | parent review evidence | PENDING |
| C-006 | yes | PR merged and exact ticket QA persisted | parent delivery readback | merge/QA verified | parent delivery evidence | PENDING |

## Verification plan

- Focused: test_visible_mandatory_reasons.py unit classes/boundaries and transaction-enabled7writer integration; existing fixture DB marker initializes reference data.
- Broader: normal hosted API PostgreSQL16/Redis7/Python3.14 job, checks/migrations/full suite including existing control and lifecycle tests.
- Independent verifier: Cody,Quinn,Vera,Shadow through parent.
- Required environment: hosted services only; no local project runtime.

## Iteration ledger

### Iteration 1

- Target criterion: C-001 through C-003.
- Hypothesis: actual settings-independent validator and writer tests expose invisible-padding acceptance while preserving Unicode positives.
- Change or investigation: complete requirements/call graph inspected, attached worktrees checked, fresh worktree integrated merged main, tests written first using existing shared seeding patterns.
- Verifier executed: static syntax,diff and structural goal checks only.
- Result: test-only candidate prepared for actual hosted behavioral RED; source unchanged.
- New evidence: wave2-20261029/api-visible-reasons/test-only-manifest.json.
- Decision: iterate

## Risks and rollback

- Risks: reasons previously meeting the minimum through invisible padding are now intentionally refused; Unicode normalization or stripping would corrupt legitimate text, so no new mutation of the returned string is allowed.
- Rollback or recovery: supply a visible explanation; reverting this single validator change restores invisible-padding acceptance. No data migration or historical audit rewrite.

## Pause and escalation conditions

- Any requirement to invent further Unicode/rendering policy or import held work goes to parent.
- Hosted setup failure is not RED; diagnose it without source fixes until meaningful behavior is observed. At most8bounded iterations.

## Final evaluation

- Validator command: python3 /Users/m.oluwole/.agents/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/17tnw2b9ah8-visible-mandatory-reasons.md
- Validator result: structural validation and stdlib test syntax PASS.
- Independent verification result: pending parent review.
- Terminal state: IN_PROGRESS
- Remaining failed or blocked criteria: actualRED/GREEN/fullAPI/reviews/merge/QA pending.
- ClickUp final evidence comment: parent owns publication.
