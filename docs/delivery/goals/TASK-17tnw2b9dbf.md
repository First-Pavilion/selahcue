# Goal Contract — TASK-17tnw2b9dbf

## Identity
- Goal ID: TASK-17tnw2b9dbf
- Parent goal ID: NONE
- Title: Rust CI audits cannot be replaced by Cargo aliases and STT policy is checked
- Role: devops-engineer
- Status: GATE_REVIEW
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/17tnw2b9dbf
- Created: 2026-11-04
- Updated: 2026-11-04
- Maximum iterations: 4
- Independent verification required: yes

## Objective
Every Rust CI root runs the actual advisory auditor despite Cargo aliases, the independent STT root receives license/source/bans enforcement, and existing weekly failure reporting remains effective.

## Baseline
Verified main65c2bba6f379ab71da9a23fe23c4fe4e3c7be097. The audit job runs three plain cargo audit commands, which Cargo configuration can replace. Local make audit already refuses identity/shadow-warning bypasses, with37 offline cases. Supply-chain CI checks desktop and operator but not independent selahcue-stt, which already has an all-features deny.toml. Existing Sunday03:17UTC schedule turns every area on; ci-alarm depends on audit/supply-chain, runs on schedule under always() and reconciles the ci-red issue. Parent read the full live ticket, saved/read back In Progress and posted its visible start comment via UI. Historical private-repository billing assumptions are stale; current repository is public and CI operates.

## Inputs and evidence sources
- Parent authenticated UI read of task17tnw2b9dbf and its acceptance criteria.
- Current CI audit/supply-chain/changes/alarm jobs; scripts/cargo_audit_all.sh and its real script tests; scripts/check_dependency_audit_coverage.py.
- Existing STT deny.toml; existing CI-minute and ci-alarm regression controls.

## Scope
### In scope
- Direct cargo-audit binary invocation in existing all-root CI steps, preserving discovered-root coverage and nonzero/error behavior.
- STT cargo deny licenses/sources/bans step on Ubuntu, bounded read-only audit/supply-chain jobs with no persisted checkout credentials.
- Real Cargo alias-resolution regression, focused CI coverage controls and evidence of existing equivalent weekly audit/issue reporting.
### Non-goals
- No new scheduler, live failure issue rehearsal, installer dispatch, deployment, credentials, unrelated dependency upgrades or allowlist relaxation.
- Application APIs/authentication/data/schema/migrations, service backup/restore and rollout operations are unaffected by this CI-only change.
### Constraints
- One ticket, agent-owned managed worktree and branch. Preserve concurrent work and user mobile lockfile; root owns four reviews, actual CI, merge/main and QA.
- No hidden skip, advisory suppression, permission expansion or unsupported completion claim.
### Assumptions and unknowns
- VERIFIED: real cargo-audit 0.22.2 binary is installed locally; cargo-audit audit --version invokes its actual CLI entry point.
- UNKNOWN: live advisory and STT deny results until executed; failures are not automatically waived.

## Dependencies and approvals
- User selected next wave; parent assigned this ticket to Otto and approved the minimal direct-binary/STT-deny approach.
- Parent explicitly accepts existing weekly all-root job plus schedule/always alarm as the operational equivalent of weekly make audit; document this instead of creating duplicate scheduling.
- Integrate fresh main, including0ec577c2 or later, before final freeze. Prior PR355 remains frozen and separate until root merges it.

## Completion predicate
| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Every CI Cargo root invokes actual cargo-audit despite repository/environment aliases and propagates tool failures | real Cargo alias fixture driving actual workflow commands plus coverage parser/self-tests | alias cannot produce unchecked success; binary invoked with correct arguments; failure statuses remain nonzero | docs/delivery/evidence/17tnw2b9dbf.md | PASS |
| C-002 | yes | Ubuntu supply-chain checks STT licenses/sources/bans with its existing all-feature policy | normal CI wiring check and actual cargo deny in STT | STT step present and real deny check passes without policy relaxation | focused and live command receipts | PASS |
| C-003 | yes | Existing weekly audit plus issue-on-failure behavior is preserved without duplication | CI schedule/change/alarm source trace, minute/alarm self-tests and workflow checks | one existing weekly schedule reaches every audit area and tracks failing audit/supply-chain jobs | source/verification evidence | PASS |
| C-004 | yes | Existing controls and required current-head independent/hosted gates pass | local audit/coverage/workflow controls plus root Cody/Shadow/Quinn/Vera and actual CI | local checks and four reviews/current CI pass; main verified before QA | parent PR/CI/ticket evidence | PENDING |

## Verification plan
- Focused verification: baseline real Cargo alias bypass, fixed actual workflow-command invocation and failing auditor negative; coverage/mutation controls; real STT deny.
- Broader regression verification: local all-root audit37 cases, coverage self-test and normal check, workflow/minute/visual/alarm controls, actionlint and whitespace/syntax.
- Independent verifier: parent coordinates Cody, Shadow, Quinn and Vera.
- Required environment: local macOS Rust tools and network for genuine advisory/policy checks; Ubuntu hosted jobs for final CI. No actual workflow dispatch or live issue creation.

## Iteration ledger
### Iteration1
- Target criterion: C-001 through C-003 baseline and failing regression.
- Hypothesis: bypassing Cargo dispatch while retaining root coverage closes the alias hole with minimal CI change; STT already has a suitable policy.
- Change or investigation: inspected current jobs, local audit safeguards and existing weekly alarm; establish failing alias/coverage tests before implementation.
- Verifier executed: installed cargo-audit version checks and source trace.
- Result: actual binary entry point works; three audit roots, two deny roots and existing weekly all-area/alarm path verified.
- New evidence: direct source and parent-approved equivalence disposition.
- Decision: iterate

### Iteration2
- Target criterion: C-001 through C-003 and local C-004 checks.
- Hypothesis: direct tool invocation plus actual Cargo alias/status fixtures closes the bypass without changing advisory defaults; existing STT policy can pass unchanged.
- Change or investigation: changed six audit/deny invocations, added STT deny, bounded read-only jobs/credential cleanup, discovered-root CI helper and local/CI regression wiring. Integrated current main 0ec577c2; audited locks/policies unchanged.
- Verifier executed: RED original CI alias reproduction; GREEN 8 policy mutations and 36 actual-Cargo probes; genuine three-root cargo-audit and STT cargo-deny;37 existing audit cases; coverage, workflow/minute/visual/alarm controls.
- Result: all current local gates pass; actual tools exit 0, existing warnings visible. Initial sandbox xcrun residue invalidated signal cleanup tests; unchanged suite passed when rerun with required execution permission. No warning/advisory/policy suppression.
- New evidence: docs/delivery/evidence/17tnw2b9dbf.md and exact live tool receipts. Existing weekly all-area schedule/alarm explicitly retained as approved equivalent, not duplicated.
- Decision: gate-review

## Risks and rollback
- Risks: CLI argument mismatch, masked failure or missing STT policy dependencies; execute real tools and actual command/error controls before handoff.
- Rollback or recovery: revert this isolated CI change; no production state changes.

## Pause and escalation conditions
- Stop for unknown advisory/policy failures requiring unrelated dependency or owner changes, unsupported tool identity, publication rejection or four iterations without required evidence. Never suppress a failing audit to ship.

## Final evaluation
- Validator command: python3 /Users/m.oluwole/.agents/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/TASK-17tnw2b9dbf.md
- Validator result: initial structural validation passed; final validation recorded at handoff. Completion remains intentionally pending C-004 independent/hosted gates.
- Independent verification result: pending parent review.
- Terminal state: GATE_REVIEW.
- Remaining failed or blocked criteria: C-001 through C-003 and local controls pass; C-004 parent-owned four reviews/current CI/merge/QA remain pending.
- ClickUp final evidence comment: parent owns authenticated UI updates while connector quota is exhausted.
