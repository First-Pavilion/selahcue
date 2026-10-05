# Goal Contract — 17tnw2b2nxk

## Identity

- Goal ID: 17tnw2b2nxk
- Parent goal ID: NONE
- Title: Pull-request and main CI run on Linux only; Windows runs weekly or on demand; macOS is gone from CI
- Role: devops-engineer
- Status: ACTIVE
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/17tnw2b2nxk
- Created: 2026-10-05T11:00:00Z
- Updated: 2026-10-05T11:00:00Z
- Maximum iterations: 8
- Independent verification required: yes

## Objective

CI on this private repository spends hosted-runner minutes only where they buy evidence the owner cannot get locally: every pull request and every push to `main` runs the Linux legs only; the Windows legs run on a weekly schedule, on `workflow_dispatch`, on the `full-ci` pull-request label and on release tags; no job runs on macOS (the owner's local `make ci` covers it); and the `ci-red` alarm cannot be cleared by a run that did not exercise the leg that failed.

## Baseline

Verified on 2026-10-05 from the jobs API over the last 100 `ci.yml` runs (each job rounded up to whole minutes, Linux x1, Windows x2, macOS x10):

- 100 runs cost 12,046 billable minutes: macOS 7,720 (64%), Windows 2,258 (19%), Linux 2,068 (17%).
- A complete three-OS run costs a median 241 minutes (Linux 35, Windows 44, macOS 155).
- The repository is private again (GitHub Team plan, 3,000 included minutes a month, no payment method), so a month at the current pace is about 14 times the quota.
- `ci.yml` has no schedule trigger, no release-tag trigger, and its matrices hard-code `macos-latest` and `windows-latest`.
- `ci_alarm.py` tracks results by job id. A matrix job reports one result for all its legs, so a Linux-only success would clear a Windows failure once Windows is not run on every push.

## Inputs and evidence sources

- ClickUp 17tnw2b2nxk, description and the 2026-10-05 10:15 UTC comment; the owner's chat decision relayed by the coordinator on 2026-10-05 (remove macOS entirely).
- `.github/workflows/ci.yml`, `.github/scripts/ci_alarm.py`, `.github/scripts/check_workflows.py`, `CLAUDE.md`.
- GitHub Actions jobs API for runs of ci.yml, windows-installer.yml, rust-canary.yml, legal-drift.yml, Dependabot Updates and Dependency Graph.
- GitHub billing documentation (about-billing-for-github-actions; actions-minute-multipliers).

## Scope

### In scope

- `ci.yml`: triggers (schedule, release tags, dispatch input, `labeled`), concurrency, the tier decision inside `detect changed areas`, matrices, launch-smoke, alarm trigger and environment.
- `ci_alarm.py` and its self-test.
- A small script that guards the minute rules (`check_ci_minutes.py`) and its wiring into the workflow-lint job.
- `CLAUDE.md` notes, PR evidence and the monthly-budget numbers.

### Non-goals

- Removing test CI altogether (the owner's option 3; the owner decides).
- Repository settings, branch protection, environments, secrets, runners of any other class.
- The delivery workflows (windows-installer, publish translations, legal-drift, rust-canary).
- Fixing the flaky tests; changing Dependabot.

### Constraints

- Disk guard steps and `scripts/ci_disk.sh` untouched.
- No new third-party actions or secrets; `ubuntu-latest` and `windows-latest` only.
- One push (every push costs minutes); no cancelling of runs.
- Edits to `ci.yml` kept surgical because PR 196 rebases on this change.

### Assumptions and unknowns

- ASSUMED: Windows is billed at 2x (the coordinator's figure). The current GitHub rate card shows Windows at about 1.7x Linux in dollars, so 2x is the conservative reading. Owner: Otto, noted in the PR.
- UNKNOWN until the weekly run exists: the cost of a cold-cache Windows week. A cache not read for 7 days is evicted and a weekly schedule sits on that edge.
- UNKNOWN: whether Dependabot Updates and Dependency Graph runs count against the quota (they run on `ubuntu-latest`; measured at about 3 and 1 minutes a run).

## Dependencies and approvals

- Merge, reviewers and any change to settings are the coordinator's and the owner's. This goal ends at an open Draft PR with evidence.
- `workflow_dispatch`, the weekly schedule and release tags can only be exercised after the file is on `main`.

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Billable minutes per job, per run and per month at three activity levels are measured from real runs, for ci.yml and every other workflow | Jobs-API analysis of the last 100 ci.yml runs and all other workflows (scripts kept in the session scratchpad, figures copied into the PR) | Numbers present with the multipliers and the billing page named | PR description, measurement section | PASS |
| C-002 | yes | No workflow file contains a macOS runner | `python3 .github/scripts/check_ci_minutes.py`; mutation: a macOS leg added to launch-smoke is refused | Script exits 0; the mutant exits 1 | local transcript, PR body | PASS |
| C-003 | yes | `pull_request` and `push` to main resolve the matrix to `["ubuntu-latest"]`; only schedule, dispatch with `windows: true`, the `full-ci` label and release tags add `windows-latest` | `check_ci_minutes.py` executes the real `tier` step for 11 event shapes; 10 mutants of ci.yml refused | Every case matches; every mutant refused | local transcript, PR body | PASS |
| C-004 | yes | A Linux-only run cannot clear a Windows failure, a skipped or absent Windows leg is no evidence, and a missing macOS job never looks like a failure | `python3 .github/scripts/ci_alarm.py --self-test` including the new cases; mutants of `tier_results`; DRY_RUN rehearsal of `main()` against the live issue list | All cases pass; the mapping mutants make the self-test fail; the registry mutant is refused by `check_ci_minutes.py` | local transcript, PR body | PASS |
| C-005 | yes | Workflow invariants and linting stay green | `python3 .github/scripts/check_workflows.py --self-test`, `python3 .github/scripts/check_workflows.py`, `check_ci_minutes.py --self-test`, `actionlint` 1.7.12 | All exit 0 | local transcript | PASS |
| C-006 | yes | The first CI run of the PR (governed by the modified workflow) runs no macOS or Windows job and finishes green; its billable minutes are recorded | `gh run view` and the jobs API for that run | No `windows-latest` or `macos-latest` job; minutes listed | run id and numbers in the PR body (not in this file: a second push re-runs the whole workflow, about 45 billable minutes) | PENDING |
| C-007 | yes | The disk guard is untouched | `git diff origin/main -- scripts/ci_disk.sh` and the disk steps of ci.yml | Empty diff for the script; the `ci_disk.sh` steps byte-identical | diff output | PASS |
| C-008 | yes | CLAUDE.md states the new tiering and that macOS is covered only by the owner's local `make ci`; the PR states what a trimmed run no longer proves and where the weekly result is | Read the diff and the PR body | Statements present | PR and CLAUDE.md diff | PASS |
| C-009 | yes | The monthly budget is stated against about 1,800 minutes with a proposal for what to drop if it does not fit | PR description | Numbers and options present; option 3 left to the owner | PR description | PASS |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused verification: the check scripts and self-tests above; the `tier` step exercised for every event type; actionlint; a mutation of the alarm mapping.
- Broader regression verification: the PR's own CI run (one push).
- Independent verifier: the four reviewers the coordinator dispatches (code, performance, security, QA).
- Required environment: local worktree; one GitHub Actions run on the PR.

## Iteration ledger

### Iteration 1

- Target criterion: C-001
- Hypothesis: the pre-trim cost is dominated by macOS, and Linux-only is far cheaper per run but still above the budget at the current pace.
- Change or investigation: jobs API over the last 100 runs of ci.yml and all other workflows.
- Verifier executed: otto-trim-analyze.py, otto-trim-model.py
- Result: 12,046 minutes for 100 runs (macOS 64%); Linux-only would have been 2,068 (mean 20.7 a run).
- New evidence: see the PR measurement section.
- Decision: iterate

### Iteration 2

- Target criterion: C-002 to C-005, C-007
- Hypothesis: one `tier` step in `detect changed areas`, read by the three matrices, keeps Windows off pull requests and main pushes; keying matrix results by what they covered keeps the alarm honest.
- Change or investigation: ci.yml (triggers, concurrency, tier step, matrices, launch-smoke, alarm trigger and env); ci_alarm.py (`tier_results`, more than 20 new self-test case groups); new check_ci_minutes.py with 5 rules; CLAUDE.md.
- Verifier executed: the local gates in C-005; 10 mutants of ci.yml and 5 of ci_alarm.py; DRY_RUN rehearsal of the alarm's `main()`.
- Result: all local gates green; every mutant refused except one the alarm self-test cannot see by construction (a matrix job forgotten in `MATRIX_JOBS`), which `check_ci_minutes.py` refuses.
- New evidence: PR body; the one open `ci-red` issue (#197, `rust`) was read during the rehearsal and is covered by the migration note in the PR.
- Decision: handoff (the CI run of the PR itself, C-006, and the four reviewers)

## Risks and rollback

- Risks: a Windows break is first seen on the weekly run, a manual dispatch, a `full-ci` run or a release tag; macOS breaks are seen only by the owner's local `make ci`; a cold Windows cache costs more on the weekly run; the alarm holds a Windows failure open until a full run passes (stricter by design).
- Rollback or recovery: revert the single merge commit; `ci.yml` returns to the previous three-OS behaviour and the alarm script to job-level keys. An open `ci-red` issue written under the new keys is cleared by the next green full run.

## Pause and escalation conditions

- Any change that needs repository settings, a paid runner or a new secret: stop, owner decides.
- A conflict with PR 196 that is not mechanical: stop, coordinator decides.
- A change to alarm semantics beyond "stricter, never looser": stop, coordinator decides.

## Final evaluation

- Validator command: `python3 ~/.claude/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/17tnw2b2nxk-trim-ci-minutes.md --completion`
- Validator result: pending
- Independent verification result: pending
- Terminal state: pending
- Remaining failed or blocked criteria: all, until verified
- ClickUp final evidence comment: pending
