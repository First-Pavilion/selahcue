# Goal Contract — TASK-17tnw2b1wvd

## Identity
- Goal ID: TASK-17tnw2b1wvd
- Parent goal ID: NONE
- Title: Cache-save checks follow repository-local call chains and fail safely
- Role: devops-engineer
- Status: GATE_REVIEW
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/17tnw2b1wvd
- Created: 2026-11-04
- Updated: 2026-11-04
- Maximum iterations: 4
- Independent verification required: yes

## Objective
A PR-reachable Rust/Flutter cache save cannot evade the workflow gate through local reusable workflows, composite actions or default-branch PR-like events; invalid YAML produces an actionable error.

## Baseline
Verified main c0325d52e809847fac141a605b74a7e6d7de7021. Existing checker118 self-tests pass and six workflows/nineteen jobs pass. It sees only direct steps, recognizes pull_request and pull_request_target but accepts a ref-only guard on the latter, rejects harmless parentheses, and lets YAML parser tracebacks escape. Primary mobile lockfile is user-modified and untouched. Parent read the full live ticket and historical link, saved/read back In Progress and posted the visible start comment via authenticated UI because connector quota is exhausted.

## Inputs and evidence sources
- Root authenticated UI read of ticket17tnw2b1wvd, four acceptance criteria and no human comments.
- .github/scripts/check_workflows.py, its existing118 cases and workflow consumers.
- Official GitHub event/context/reusable-workflow documentation.

## Scope
### In scope
- Propagate PR event reachability through repository-local reusable workflows and composite actions with caller-chain diagnostics.
- Refuse unsafe default-branch PR-like cache saves, test each handler against bypass mutations, narrowly support balanced outer parentheses and report malformed YAML without traceback.
- Focused tests, workflow checker documentation and this execution evidence.
### Non-goals
- No remote action/workflow fetching, arbitrary expression interpretation, new runtime dependencies, production configuration, deployment or installer dispatch.
- Application APIs/authentication/data/schema/migrations, backup/restore and service observability are unaffected; those DevOps criteria are inapplicable to this static CI checker.
### Constraints
- Preserve existing118 workflow controls and normal CI/minutes/visual/scanner protections, including concurrent work when integrated later.
- One ticket, managed worktree and branch; root owns four independent reviews, actual CI, merge/main verification and QA.
### Assumptions and unknowns
- VERIFIED: no repository-local reusable workflows or composite actions exist at baseline; synthetic on-disk fixtures exercise those paths.
- UNKNOWN: final hosted CI; separately tracked Home harness blocker17tnw2bcadw is not waived.

## Dependencies and approvals
- User authorizes next-wave work; root authorized the bounded default-ref fail-closed treatment and UI tracking.
- Scanner PR350 remains separate; preserve its source once merged without stacking it into this PR.

## Completion predicate
| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Local reusable/composite call chains propagate PR reachability and report caller/callee on unsafe Rust/Flutter saves | on-disk fixtures against actual checker CLI | valid guarded chains pass, unsafe/missing/cyclic targets fail with caller diagnostics | docs/delivery/evidence/17tnw2b1wvd.md | PASS |
| C-002 | yes | Default-branch PR-like events cannot use a ref-only guard to save caches | direct/nested event fixtures and handler mutations | pull_request_target/workflow_run/issue_comment reject ref-only saves; explicit disabled caches pass | focused regression suite | PASS |
| C-003 | yes | Only safe parenthesized canonical comparison is accepted and malformed YAML emits one-line error | expression variants, malformed top-level/reachable fixture CLI | exact harmless grouping passes; unsafe variants fail; malformed input exit 1 without traceback | focused regression suite | PASS |
| C-004 | yes | Tests catch removal of each newly required handler and existing controls pass | self-tests, focused handler mutation proof, actual workflow/minutes/visual checks and diff check | all positive controls pass and real bypass mutations are caught | committed evidence | PASS |
| C-005 | yes | Four independent reviews and current CI pass before merge/QA | root Cody/Shadow/Quinn/Vera, hosted CI, main and ClickUp readback | four passes plus actual CI; merged main verified before QA | root review/CI/ticket receipts | PENDING |

## Verification plan
- Focused verification: real checker CLI over temporary repository trees, recursive call, event, grouping, malformed-input and fail-closed fixtures; handler-removal mutations.
- Broader regression verification: existing118 self-tests, actual workflow/minute/visual controls, syntax and whitespace checks. No application build is needed for unchanged application behavior.
- Independent verifier: root coordinates Cody, Shadow, Quinn and Vera.
- Required environment: local Python3.9-compatible checker with existing PyYAML; hosted Linux workflow checks.

## Iteration ledger
### Iteration1
- Target criterion: C-001 through C-004.
- Hypothesis: repository-root-bounded call traversal with event context and fail-closed parsing can expose the documented blind spots without executing workflows.
- Change or investigation: establish baseline and failing on-disk regression fixtures before implementation.
- Verifier executed: existing checker self-test and repository check.
- Result:118 cases and6 workflows/19 jobs pass at baseline; new fixtures pending.
- New evidence: direct source identifies all four blind spots.
- Decision: iterate

### Iteration2
- Target criterion: C-001 through C-004 and local integration.
- Hypothesis: a bounded local call graph retaining caller events can enforce the same cache policy through reuse without executing workflow code.
- Change or investigation: implemented local reusable/composite traversal, default-ref event refusal, narrow grouping normalization and one-line parsing diagnostics; expanded real on-disk fixtures to 39 and added handler-removal proof. Integrated uv main b3ae75f8 without changing its files.
- Verifier executed: all 118 existing plus 39 CLI cases, nine handler mutants, normal workflow/minutes/visual controls, syntax/actionlint and whitespace checks.
- Result: all final local checks exit 0; nine real handler removals make the actual self-test red. Initial non-unique proof anchor and macOS bytecode-cache location were corrected and rerun, not counted as passes.
- New evidence: docs/delivery/evidence/17tnw2b1wvd.md; normal checker six workflows/twenty jobs accepts the merged uv graph job. No source behavior outside cache policy/input diagnostics changes.
- Decision: gate-review

## Risks and rollback
- Risks: missed nested cache saves, path escape/cycles or overly broad expression acceptance; bound paths, reject cycles and keep a deliberately narrow expression grammar.
- Rollback or recovery: revert this isolated static-checker change; no production state or artifacts change.

## Pause and escalation conditions
- Stop for owner-level scope changes, unsafe access, publication rejection or four iterations without required evidence. Do not waive the separate Home CI gate.

## Final evaluation
- Validator command: python3 /Users/m.oluwole/.agents/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/TASK-17tnw2b1wvd.md
- Validator result: structural validation passed before implementation; final structural validation exits 0. Completion validation intentionally exits 1 while C-005 independent reviews/CI/merge/QA are pending.
- Independent verification result: pending root reviews.
- Terminal state: GATE_REVIEW.
- Remaining failed or blocked criteria: C-001 through C-004 locally pass; C-005 parent-owned reviews/actual CI/merge/QA remain pending.
- ClickUp final evidence comment: root owns authenticated UI updates while quota is exhausted.
