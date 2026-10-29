# Goal Contract — TASK-17tnw2b9d9z

## Identity

- Goal ID: TASK-17tnw2b9d9z
- Parent goal ID: WAVE2-SELAHCUE-20
- Title: Refuse debug and caller-supplied actor identity outside dev
- Role: backend-engineer
- Status: GATE_REVIEW
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/17tnw2b9d9z
- Created: 2026-10-29
- Updated: 2026-10-29
- Maximum iterations: 8
- Independent verification required: yes

## Objective

Every environment other than exact `dev` refuses DEBUG or the trusted actor-header bridge; the dev bridge refuses anonymous actors while internal anonymous audit actors remain valid.

## Baseline

Main `55d5ff3a1b8d18e4702613cd1861a8d226197d37` accepts DEBUG and explicit header trust outside dev. Header trust defaults to DEBUG and accepts every ActorKind including ANONYMOUS. PR232 is merged; held PR233 is excluded.

## Inputs and evidence sources

- Complete saved ClickUp task and comments: wave2-20261029/api-qualification/17tnw2b9d9z.json in the parent evidence directory.
- Later owner comment **1400430000204673** supersedes the stale description allowing ingress opt-in: “Wanted, as this ticket already says: refuse SELAHCUE_TRUST_ACTOR_HEADERS (and DEBUG) when ENVIRONMENT is not dev, with a test.” It also says: “the bridge should reject ANONYMOUS (it is only for the failed-confirm audit row).”
- Existing settings import guards, deployment regression helpers and foundation actor tests.

## Scope

### In scope

- Import-time non-dev guards and actionable variable/environment error messages.
- Dev bridge anonymous refusal, preserving all internal audit uses and session precedence.
- Positive and negative tests, deployment documentation and this contract.

### Non-goals

- Staff identity provider, held PR233 mutations, environment selection policy, database fail-open changes, anonymous audit removal, schemas/migrations/jobs.

### Constraints

- Parent controls ClickUp, publication, hosted CI, all four independent reviews, merge and QA.
- No heavy local suites, database setup, containers or builds while this host is paging. Tiny deterministic checks require resource admission.
- Shared workspace; isolate this ticket and preserve all other agents' work.

### Assumptions and unknowns

- No product decision is needed: the later owner comment explicitly covers every non-dev environment, including staging.
- Full API regression execution is pending hosted CI due host resource limits.

## Dependencies and approvals

- User authorizes implementation, review remediation, merge after passed gates and QA handoff; parent owns external actions.
- Owner supersession is recorded above. PR232 prerequisite is already merged.

## Completion predicate

All mandatory rows must be PASS for VERIFIED_COMPLETE.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Non-dev DEBUG and explicit header trust refuse startup for truthy spellings with named flag and environment | deployment guard matrix | refusals and positive controls pass | wave2-20261029/api-debug-guard/verification.log | PENDING |
| C-002 | yes | Dev default and explicit header trust behavior remain available; anonymous bridge actor is refused | focused deployment and foundation tests | all focused cases pass | wave2-20261029/api-debug-guard/verification.log | PENDING |
| C-003 | yes | Internal failed-confirm anonymous audit and existing API behavior remain valid | hosted API job including test_every_failed_confirm_leaves_exactly_one_record_naming_its_outcome | CI passes | hosted CI linked by parent | PENDING |
| C-004 | yes | Deployment documentation matches guard policy and env inventory | deployment env docs tests and diff inspection | no stale ingress opt-in; docs tests pass | wave2-20261029/api-debug-guard/verification.log | PENDING |
| C-005 | yes | All independent reviews accept frozen implementation and CI passes | Cody Quinn Vera Shadow and hosted CI | no unresolved findings; CI green | parent review and CI evidence | PENDING |
| C-006 | yes | Merged PR links exact task and task moves to QA | parent merge and ClickUp persisted readback | merged and QA confirmed | parent delivery evidence | PENDING |

## Verification plan

- Focused: deployment guard matrices, foundation actor bridge cases, deployment env docs.
- Broader: hosted API job, including failed-confirm anonymous audit integration, TLS/proxy guards, existing auth.
- Independent verifier: Cody, Quinn, Vera and Shadow through parent.
- Required environment: existing Python3.14 dependencies; hosted database-backed suite. No local resource-intensive gates.

## Iteration ledger

### Iteration 1

- Target criterion: C-001, C-002.
- Hypothesis: import guards plus a bridge-only enum refusal enforce the later owner instruction.
- Change or investigation: baseline traced; test-first regression cases prepared before source changes.
- Verifier executed: source inspection and resource admission snapshots.
- Result: hosted RED run 40940404118, diagnostic ac20e0c (test source 9f0c21f), proves 41 behavioral failures and 40 positive controls in 2.24s. All 40 non-dev truthy cases failed to raise; anonymous bridge returned ActorContext. Setup, checks and migrations passed. Local project runtime was not run.
- New evidence: wave2-20261029/api-debug-guard/red.log; https://github.com/First-Pavilion/selahcue/actions/runs/40940404118
- Decision: iterate

### Iteration 2

- Target criterion: C-001 through C-004.
- Hypothesis: two import-time guards and bridge-only anonymous rejection satisfy the failing behavior without changing internal audit construction.
- Change or investigation: refuse DEBUG and explicit header trust outside exact dev, default header trust false outside dev; reject only anonymous at header parsing; update the registry, ops guide, API README and sample comment.
- Verifier executed: stdlib syntax inspection, diff checks and structural contract validator; full runtime is delegated to hosted CI.
- Result: source candidate prepared; hosted GREEN and all independent gates remain pending.
- New evidence: wave2-20261029/api-debug-guard/verification.log and candidate manifest.
- Decision: gate-review

## Risks and rollback

- Risks: deployments previously enabling either flag now intentionally fail startup; staff IdP remains separate and unavailable.
- Rollback or recovery: set flags false in shared environments; use exact dev only for a local trusted development environment. Revert this single PR if necessary, recognizing that it restores the unsafe baseline.

## Pause and escalation conditions

- New owner-policy conflict goes to parent. No broader identity or held PR implementation.
- Resource pressure prevents local runtime admission; parent uses hosted checks.

## Final evaluation

- Validator command: python3 /Users/m.oluwole/.agents/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/17tnw2b9d9z-deployment-debug-guard.md
- Validator result: initial structural validation PASS; production unchanged for hosted RED.
- Independent verification result: pending parent review round.
- Terminal state: GATE_REVIEW
- Remaining failed or blocked criteria: hosted GREEN, full API regression, all independent reviews, merge and QA remain pending.
- ClickUp final evidence comment: parent owns publication.
