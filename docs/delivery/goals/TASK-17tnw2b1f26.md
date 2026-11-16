# Goal Contract — TASK-17tnw2b1f26

## Identity

- Goal ID: TASK-17tnw2b1f26
- Parent goal ID: NONE
- Title: Installer operator features remain covered by desktop CI lint
- Role: devops-engineer
- Status: ACTIVE
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/17tnw2b1f26
- Created: 2026-11-03
- Updated: 2026-11-04
- Maximum iterations: 4
- Independent verification required: yes

## Objective

Reject installer operator feature changes without an exactly matching operator-native lint configuration, and run desktop checks on installer workflow edits.

## Baseline

Verified at main 9801fc587adba59a30ddee066efb5d0da26fc425: packaging uses `cargo tauri build --features stt`; operator-native lints stt and stt,cloud-stt separately; desktop filter omits windows-installer.yml. No parity gate exists. Task has no parent or dependencies; linked historical implementation 86ak4y8yr is complete.

## Inputs and evidence sources

- Active ClickUp task, empty comments, completed linked ticket.
- .github/workflows/ci.yml, windows-installer.yml and Makefile.

## Scope

### In scope

- Feature equality and path-filter check, negative self-tests, shared Make/CI invocation.

### Non-goals

- Packaging execution, installer downloads, signing, credentials, deployment, STT runtime changes.
- NDI lint and SBOM coverage belong to separate queued tickets.

### Constraints

- One isolated managed worktree, branch and PR for this ticket; root owns review, merge and QA status.
- Packaging admission remains workflow_dispatch plus exact refs/heads/main.
- No new runner jobs; reuse existing workflow lint job and its pinned PyYAML dependency.

### Assumptions and unknowns

- Unknown: hosted CI result until branch PR runs. Independent reviewer verdicts owned by root.

## Dependencies and approvals

- User authorizes ticket implementation, branch push and public PR. No packaging dispatch authorized.
- Independent Cody, Shadow, Quinn and Vera reviews coordinated by root.
- Environments, rollout, migrations, backups, alerts and cost changes are not applicable: static checks only; no infrastructure or deployed application changes.

## Completion predicate

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Installer feature drift fails gate used by Make and CI | make installer-feature-parity; feature mutant | baseline exits 0, mismatch exits nonzero | Iterations 2–3: baseline exits 0; comma and unquoted variadic mutants exit 2 | PASS |
| C-002 | yes | Installer-only edit matches desktop filter | checker and removed-filter mutant | baseline matches, removed path rejected | Iteration 2: removed path exits 2 | PASS |
| C-003 | yes | Self-test rejects deliberately mismatched features and dead checker | self-test and dead-check mutant | cases pass; disabled comparison rejected | Iteration 3: 12 tests; dead checker fails variadic regression | PASS |
| C-004 | yes | Workflow invariants and main-only packaging preserved | check_workflows.py; actionlint; diff | checks pass and installer workflow unchanged | Iteration 2: invariant checks and actionlint exit 0 | PASS |
| C-005 | yes | Independent reviews pass at final revision | Root review round | all four verdicts pass | root handoff | PENDING |

## Verification plan

- Focused verification: shared Make target, script self-tests, deliberate feature/path/checker mutations.
- Broader regression verification: workflow invariants, CI minute check, actionlint, make -n ci wiring; hosted PR CI.
- Independent verifier: root dispatches Cody, Shadow, Quinn and Vera.
- Required environment: local macOS for static gates; hosted Linux PR CI for actual workflow execution. Actual installation is outside scope.

## Iteration ledger

### Iteration 1

- Target criterion: C-001 through C-004.
- Hypothesis: Parsing executable workflow commands, comparing exact feature sets with matching default-feature behavior, and asserting installer desktop filter membership will prevent drift.
- Change or investigation: baseline inspected; implementation pending.
- Verifier executed: pending.
- Result: pending.
- New evidence: baseline confirms reported gap.
- Decision: iterate.

### Iteration 2

- Target criterion: C-001 through C-004.
- Hypothesis: One shared Make target, using the existing CI PyYAML parser dependency, prevents divergent invocations.
- Change or investigation: added the checker and nine self-tests; `make ci` calls `installer-feature-parity` immediately after the toolchain check; the existing workflow-lint job calls the same target after its pinned PyYAML install. Added the exact installer workflow to the desktop filter. Installer workflow itself is unchanged.
- Verifier executed: `make installer-feature-parity` (nine tests and live configuration pass); `make -n ci` includes the target. Deliberately changed the real installer command to `--features stt,parity-probe`: both `make installer-feature-parity` and actual `make ci` exit 2 with the exact-feature diagnostic before build/staging. Removed the real installer filter entry: shared gate exits 2 with installer-only path diagnostic. Replaced the checker's comparison with `if False` in a temporary script: self-tests exit 1 naming the feature-drift failure. All mutants restored.
- Result: static gate and negative proofs pass. `check_workflows.py --self-test` passes 118 cases; live checker reports six workflows/19 jobs OK; `check_ci_minutes.py` and its self-tests pass; actionlint over ci.yml and windows-installer.yml exits 0; `git diff --check` passes.
- New evidence: an initial live mutant using `stt,cloud-stt` correctly remained green, because that exact set is already linted. The useful negative proof therefore adds an unlinted feature (`parity-probe`). A first parser attempt tokenized unrelated PowerShell lines and failed on a continuation; narrowed command tokenization to literal Cargo command lines before final verification.
- Decision: handoff to root for independent reviews and hosted PR CI. Full green `make ci` was not run: no Rust, Flutter or application source changed; its real failing mutant proves the new gate is reached and enforced. No actual Windows build or install is claimed.

### Iteration 3 — Cody C-342-1 remediation

- Target criterion: C-001 and C-003; preserve C-002 and C-004.
- Hypothesis: Tauri's variadic `-f`/`--features` operands must be consumed until the next option, separately from Cargo Clippy's single operand. Unknown arguments must be refused rather than ignored.
- Change or investigation: independently reproduced reviewed head's defect in a fresh scratch copy: changing only the installer command to `cargo tauri build --features stt openai-notes` made the shared Make target falsely exit 0. Confirmed Tauri's documented grammar at https://v2.tauri.app/reference/cli/ (build `-f, --features [FEATURES...]`). Replaced silent unknown-token skipping with bounded supported grammar; added three regression tests covering unquoted/quoted/comma/equal forms, short Tauri `-f`, Cargo `-F`, exact matching and default-feature mismatch.
- Verifier executed: `make installer-feature-parity` passes 12 tests and live comparison. Five distinct scratch Make mutants (`--features stt openai-notes`, quoted space list, comma list, equals plus extra operand, and `-f` space list) each exit 2 with exact-feature mismatch. Mutating the real worktree installer to the reviewer's unquoted form makes actual `make ci` exit 2 at the same gate. A dead-comparison script mutant exits 1 and specifically fails `test_tauri_variadic_feature_drift`. All temporary edits restored.
- Result: regression corrected locally. Workflow checker self-test (118 cases), live workflow checker (six workflows/19 jobs), CI minute self-test and live rules, actionlint for both workflows and `git diff --check` pass. Origin main refreshed and branch remains zero commits behind 9801fc587adba59a30ddee066efb5d0da26fc425.
- New evidence: the original parser dropped extra unquoted feature operands; this was a real false-green, not a difference in feature-set intent. Supported equivalent lists now resolve to the same full set; Cargo unquoted extras and unsupported command spellings fail closed.
- Decision: handoff for Cody re-review and final independent review round. Hosted CI must be checked on the corrected head; no full green make-ci or packaging/install claim.

## Risks and rollback

- Risks: static parser must fail clearly on unsupported dynamic feature expressions; PyYAML is already pinned in the workflow lint job, local users need the same dependency.
- Rollback or recovery: revert this ticket's PR; no runtime state changes.

## Pause and escalation conditions

- Stop for a new release, SDK, license, infrastructure or cost decision; root coordinates independent reviews.

## Final evaluation

- Validator command: python3 /Users/m.oluwole/.agents/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/TASK-17tnw2b1f26.md
- Validator result: structural validation passes. Completion validation intentionally pending C-005.
- Independent verification result: pending root coordination.
- Terminal state: GATE_REVIEW (implementation evidence ready; root owns independent review and final disposition).
- Remaining failed or blocked criteria: C-005 independent review pending; hosted PR CI pending.
- ClickUp final evidence comment: pending.
