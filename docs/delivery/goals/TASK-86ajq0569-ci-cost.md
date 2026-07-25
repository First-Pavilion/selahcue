# Goal Contract — TASK-86ajq0569-ci-cost

## Identity

- Goal ID: TASK-86ajq0569-ci-cost
- Parent goal ID: STAGE7-foundation
- Title: CI runner-minutes are reduced by path-filtering the matrix (a single-side change skips the other side's jobs) without losing any coverage; the 3-OS parity gate is preserved
- Role: devops-engineer
- Status: IN_PROGRESS
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86ajq0569
- Created: 2026-07-25
- Updated: 2026-07-25
- Maximum iterations: 6
- Independent verification required: yes

## Objective

Cut GitHub Actions minutes/cost. The cost drivers: macOS runners bill at 10× minutes, Windows 2×, and most commits touch only desktop OR only mobile yet run the entire matrix. Path-filter so each side's jobs run only when that side (or the workflow) changes.

## Baseline

Verified from `.github/workflows/ci.yml`: caching is already in place (Swatinem/rust-cache in rust/launch-smoke/operator; flutter `cache: true`) and docs/`**.md`/TODO are skipped at the trigger. Jobs: `rust` ×3 OS, `launch-smoke` ×2 (ubuntu+macos), `operator` ×3 OS, `flutter` (+ heavy `flutter build apk --debug` + JDK), `audit`, `supply-chain`. No path-based gating between desktop and mobile — a mobile-only commit still runs the full 3-OS Rust matrix (incl. the 10× macOS + 2× Windows), and a desktop-only commit still runs Flutter + the Android apk build. CI is currently BLOCKED (repo Actions quota — the reason this task exists).

## Inputs and evidence sources

- Task 86ajq0569 + epic 86ajp09nk (CI); the current ci.yml; GitHub Actions per-OS minute multipliers (Linux 1×, Windows 2×, macOS 10× — DOCUMENTED, GitHub billing docs).

## Scope

### In scope

- A `changes` filter job (dorny/paths-filter@v3) with outputs `desktop`, `mobile`, `android`; each filter also matches `.github/workflows/ci.yml` so a CI change runs everything.
- Gate `rust`, `launch-smoke`, `operator`, `audit`, `supply-chain` on `desktop`; gate `flutter` on `mobile`; gate the flutter `apk --debug` step on `android`.
- Keep the docs-only trigger skip, all caching, and the full 3-OS matrices intact (they just don't run for the irrelevant side).

### Non-goals

- Removing any OS from a matrix, changing fail-fast/visibility, or weakening any gate (no coverage loss); PR branch-protection aggregator (documented as a follow-up if ever needed); the Actions-quota restoration itself (owner).

### Constraints

- Zero coverage loss on the changed side; the 3-OS parity gate runs in full on every desktop change; `ci.yml` must be valid; the CI itself can't self-verify (owner Actions outage) — validate YAML + the job graph locally.

### Assumptions and unknowns

- ASSUMED: push-to-main flow (no required-status-check branch protection), so `if:`-skipped jobs are acceptable. If protection is added later, an aggregator job is needed (documented). VALIDATION: repo settings (owner).

## Dependencies and approvals

- None blocking. The CI-green confirmation of this change waits on the owner restoring Actions (same blocker as 8b).

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | ci.yml is valid YAML and every job's `needs`/`if` references resolve (a coherent DAG; no dangling job/output refs) | pyyaml parse + job-graph audit | valid; all needs/outputs resolve | pyyaml OK; DAG audited (0 problems) | PASS |
| C-002 | yes | Path gating is correct: desktop jobs (rust/launch-smoke/operator/audit/supply-chain) gate on `desktop`; flutter on `mobile`; the apk step on `android`; every filter includes `.github/workflows/ci.yml` | filter-logic review | gating matches the matrix | desktop→rust/launch/operator/audit/supply; mobile→flutter; android→apk step; +web catch-all + pubspec | PASS |
| C-003 | yes | Coverage preserved: a desktop change runs the FULL 3-OS matrix (parity gate); a mobile change runs flutter; both/CI-change runs everything | scenario trace | no coverage lost per side | trace: desktop-only=full 3-OS matrix; mobile-only=flutter; both=all; review confirmed no OS/gate removed | PASS |
| C-004 | yes | Estimated minute savings documented; docs-skip + caching retained | doc review | savings + retention noted | savings estimate below; caching + docs-skip retained | PASS |
| C-005 | yes | Independent review of the workflow change; findings fixed | review | confirmed findings fixed | review agent: 0 high/med; 3 LOW fixed (web catch-all, pubspec, header comment) | PASS |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused: pyyaml parse of ci.yml; a manual job-DAG audit (needs/if/outputs resolve); a scenario trace (desktop-only / mobile-only / both / CI-change → which jobs run). Independent: a review agent checks the gating logic + coverage preservation.
- Required environment: local (CI can't run — owner Actions outage).

## Iteration ledger

### Iteration 1

- Target criterion: C-001..C-004
- Hypothesis: a dorny/paths-filter `changes` job + per-job `needs`/`if` gating cuts single-side-change minutes (the common case) with zero coverage loss.
- Change or investigation: edit ci.yml; parse + trace.
- Verifier executed: pyyaml parse + job-DAG audit + scenario trace; independent review agent.
- Result: all criteria PASS. A `changes` job (dorny/paths-filter) gates desktop vs mobile; a desktop change runs the FULL 3-OS matrix, a mobile change runs flutter, both/CI-change runs everything. Review: 0 high/med; 3 LOW fixed (web/** catch-all so no code area is silently unverified; pubspec in the android filter; corrected the header comment re: branch-protection deadlock + the aggregator follow-up).
- New evidence: **CI-green confirmation waits on the owner restoring Actions** (same outage as 8b) — but the change is YAML-valid + DAG-audited + reviewed locally.
- Decision: gate-review

## Savings estimate

GitHub multipliers: Linux 1x, Windows 2x, macOS 10x. Before: EVERY non-docs commit ran the full set — rust ×3 (1+10+2=13 weighted), launch-smoke ×2 (1+10=11), operator ×3 (13), flutter+apk, audit, supply-chain. The three macOS jobs alone = 30 weighted units. After: a **mobile-only** commit runs only flutter (+ apk if android) — skipping the entire ~50-weighted-unit desktop set; a **desktop-only** commit skips flutter + the heavy Android SDK/Gradle apk build. Since Stage-8 commits are overwhelmingly single-side (desktop OR mobile), this roughly **halves** average weighted-minute consumption and removes the macOS cost from every mobile commit and the Android-build cost from every desktop commit. Caching (rust-cache + flutter) and the docs-only trigger skip are retained.

## Risks and rollback

- Risks: a skipped job could block a required status check IF branch protection is added later (documented; not applicable to push-to-main today). Rollback: git — one file.

## Pause and escalation conditions

- CI-green confirmation waits on the owner restoring Actions.

## Final evaluation

- Validator command: `python3 scripts/validate_goal_contract.py docs/delivery/goals/TASK-86ajq0569-ci-cost.md --require-complete`
- Validator result: PASS (5/5)
- Independent verification result: review agent — 0 high/med; 3 LOW fixed
- Terminal state: GATE_REVIEW (CI-green confirmation pending owner Actions restore)
- Remaining failed or blocked criteria: none (CI-green is confirmatory, not a criterion — the change is locally validated)
- ClickUp final evidence comment: posted on 86ajq0569
