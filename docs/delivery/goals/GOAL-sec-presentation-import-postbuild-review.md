# Goal Contract - GOAL-sec-presentation-import-postbuild-review

## Identity

- Goal ID: GOAL-sec-presentation-import-postbuild-review
- Parent goal ID: BUILD-selahcue
- Title: Post-build security review of the presentation importer verifies every threat-model constraint against the built code and issues a release verdict
- Role: security-reviewer
- Status: GATE_REVIEW
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86ajnx548
- Created: 2026-08-16
- Updated: 2026-08-16
- Maximum iterations: 5
- Independent verification required: yes

## Objective

Re-verify each constraint of `docs/security/THREAT-MODEL-presentation-import.md` v1.1 (B1-B5, B5-J, C1-C14) against the UNCOMMITTED implementation in the working tree (`selahcue-import` crate, `selahcue-engine` jpeg/exif/media changes, `selahcue-operator` media_store/deck_library/main changes, `scripts/import_guards.sh`), recording PASS / FAIL / PARTIAL per constraint with code evidence; scrutinise `exif.rs` (an owner-approved relaxation of B5-J clause 6), `jpeg.rs` (author-only-reviewed), the hostile-input test batteries (fixture-free, actually exercising the attacks, including the lying-declared-size case), and the B2 dependency-guard script; restate the RR1 risk position; update the threat model in place with a post-build verification section, a revision note, and a clear release verdict (merge / merge with conditions / not merge). Review only - no file under `implementation/` is modified, nothing is staged, committed or reverted.

## Baseline

Verified current state before substantive work:

- Threat model v1.1 exists with verdict "feature release verdict Not Assessed until the post-build security review re-verifies each constraint against code".
- The implementation exists uncommitted in the working tree: `implementation/desktop/crates/selahcue-import/` (16 src files + 4 test files + support builder), `selahcue-engine/src/{jpeg.rs,exif.rs}` + `tests/{test_jpeg.rs,test_jpeg_alloc.rs}` + modified `media.rs`/`lib.rs`/`Cargo.toml`, `selahcue-operator/src/media_store.rs` + modified `deck_library.rs`/`main.rs`, `scripts/import_guards.sh` wired into `Makefile` and `.github/workflows/ci.yml`.
- Parent-verified facts taken as starting points: `jpeg-decoder = "=0.3.2"` exact pin with `default-features = false` and no `zune` in the tree; `import_guards.sh` executes in the `make ci` gate.
- ADR-0024/0025 and `docs/product/IMPORT-product-decisions.md` record owner-approved divergences from v1.1: EXIF orientation IS applied via a bounded hand-rolled single-tag reader (relaxes B5-J clause 6); collision dialog with Replace policy.
- The owner has accepted RR1-RR6 on the threat model's terms and committed to scheduling the ADR-0016 out-of-process decode worker.
- ClickUp MCP tools are unavailable in this session; per repo precedent, pending ClickUp update text is recorded in this contract.

## Inputs and evidence sources

- `docs/security/THREAT-MODEL-presentation-import.md` v1.1 (the constraint set under verification)
- `docs/architecture/IMPORT-presentation-design.md` v2.0, ADR-0024, ADR-0025, `docs/product/IMPORT-product-decisions.md`
- The uncommitted working-tree implementation listed in the Baseline
- `cargo` metadata/tree output, test source, `scripts/import_guards.sh`, `Makefile`, `.github/workflows/ci.yml`
- `.claude/team/` operating contract documents

## Scope

### In scope

- Read-only code review of the implementation files named in the Baseline, and execution of read-only verification commands (cargo tree/metadata, greps, optionally running the crate's own tests).
- Constraint-by-constraint PASS/FAIL/PARTIAL adjudication with named evidence and named bypass paths where a check is bypassable.
- In-place update of `docs/security/THREAT-MODEL-presentation-import.md` (post-build verification section + revision note preserving the audit trail).
- This goal contract under `docs/delivery/goals/`.

### Non-goals

- No modification of any file under `implementation/`; no fixes; no staging/commit/revert.
- No second findings document - the threat model is updated in place per the tasking.
- No risk acceptance on behalf of the owner; RR acceptance is already the owner's recorded decision.
- No destructive testing, no execution of hostile files outside the crate's own test batteries.

### Constraints

- Write only under `docs/`.
- Severity calibrated to a single-operator offline desktop deployment.
- Findings labelled Verified / Inferred / Assumed / Unknown; no claim of compliance taken from comments or docs without code evidence.
- Structural enforcement is distinguished from check-based enforcement, and bypassable paths are named.

### Assumptions and unknowns

- ASSUMED: the working tree state reviewed is the state that would merge; any post-review code change invalidates the verdict for the changed files.
- UNKNOWN until inspected: whether the missing per-module test files (test_zip.rs, test_ooxml.rs, test_pkgpath.rs etc. from design SS4.2) exist as inline module tests or are absent.

## Dependencies and approvals

- Owner acceptance of RR1-RR6: recorded (per tasking); the ADR-0016 worker scheduling commitment is a condition this review re-states, not re-decides.
- ClickUp write path: unavailable; pending update recorded below.

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Goal Contract validates before substantive work | `python3 scripts/validate_goal_contract.py docs/delivery/goals/GOAL-sec-presentation-import-postbuild-review.md` | Exit 0 | Validator output in session | PASS |
| C-002 | yes | Every blocker B1, B2, B3, B4, B5 and every B5-J clause is adjudicated PASS/FAIL/PARTIAL against code (not comments), with file/line evidence, noting structural vs check-based enforcement and any bypass path | Code inspection recorded in the threat model's post-build section | A per-constraint table with verdicts and evidence exists | `docs/security/THREAT-MODEL-presentation-import.md` post-build section | PASS |
| C-003 | yes | Every required control C1-C14 is adjudicated PASS/FAIL/PARTIAL the same way | Code inspection recorded in the threat model's post-build section | Per-control verdicts with evidence | `docs/security/THREAT-MODEL-presentation-import.md` post-build section | PASS |
| C-004 | yes | The four scepticism targets are individually assessed: exif.rs bounds vs ADR-0025 claims; jpeg.rs caps-before-allocation incl. height==0, second-SOF, dimension-change, 40/24 MP; the hostile-input batteries actually exercise the attacks (incl. the lying-declared-size case failing against a vulnerable implementation); import_guards.sh genuinely delivers B2 or its gap is named | Code + test inspection; test execution where practical | Each target has an explicit finding with evidence | `docs/security/THREAT-MODEL-presentation-import.md` post-build section | PASS |
| C-005 | yes | The threat model is updated in place with a post-build verification section, a revision-history entry preserving the audit trail, a restated RR1 position, and a clear release verdict (merge / merge with conditions / not merge) with findings ranked by product-realistic severity | Document review | Section and revision note present; verdict unambiguous | `docs/security/THREAT-MODEL-presentation-import.md` | PASS |
| C-006 | yes | No file under `implementation/` is modified by this goal and the contract validates at completion | `git status --porcelain -- implementation/` diffed against session start; validator with `--completion` | Identical file list and contents; exit 0 | git + validator output in session | PASS |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused verification: per-constraint code inspection with file/line citations; run the crate's own test suites read-only where practical (`cargo test -p selahcue-import`, `cargo test -p selahcue-engine --test test_jpeg --test test_jpeg_alloc`); execute `scripts/import_guards.sh`; `cargo tree -p selahcue-import -e normal` and feature inspection of `jpeg-decoder`.
- Broader regression verification: `git status --porcelain -- implementation/` unchanged; `git diff --stat -- implementation/` unchanged relative to session start.
- Independent verifier: the parent agent and the authorised human gate consume the verdict; this review is itself the required independent check for the feature.
- Required environment: local repository; cargo toolchain for read-only builds/tests.

## Iteration ledger

### Iteration 1

- Target criterion: C-001
- Hypothesis: A structurally valid contract can be authored from the tasking, the v1.1 threat model, ADR-0024/0025, the product decisions, and the observed working-tree file inventory.
- Change or investigation: Read skill + operating contract, threat model v1.1, ADR-0024/0025, IMPORT-presentation-design.md v2.0, IMPORT-product-decisions.md; inventoried the implementation files; authored this contract.
- Verifier executed: `python3 scripts/validate_goal_contract.py docs/delivery/goals/GOAL-sec-presentation-import-postbuild-review.md`
- Result: C-001 PASS (validator green, 6 criteria).
- New evidence: validator output in session.
- Decision: iterate

### Iteration 2

- Target criterion: C-002, C-003, C-004, C-005
- Hypothesis: Reading every load-bearing module in full and running the batteries (not trusting their names) yields a defensible per-constraint verdict for each blocker/control and each scepticism target.
- Change or investigation: Full read of selahcue-import (16 src + 4 test files + support builder), selahcue-engine jpeg.rs/exif.rs/media.rs + test_jpeg.rs/test_jpeg_alloc.rs, operator media_store.rs + deck_library.rs policy diff + main.rs, import_guards.sh + Makefile/ci wiring. Ran `cargo test -p selahcue-import` (48 green) and `-p selahcue-engine` (JPEG battery + alloc green), `sh scripts/import_guards.sh` (pass), `cargo tree -p selahcue-import -e normal` (network-free, ~70 crates), inspected pinned jpeg-decoder 0.3.2 source (platform_independent forbids unsafe, zero deps, no rayon/zune). Built a scratch harness against the real crate feeding a REFERENCED under-declared 200 MiB deflate bomb: it stages nothing and keeps the slide text, empirically confirming the B3 streaming counter is correct while the committed lying-header test is hollow (its bomb is an unreferenced duplicate). Authored §11 in the threat model in place with per-constraint verdicts, the four scepticism-target findings, ranked findings F1-F5, restated RR1, and the MERGE WITH CONDITIONS verdict.
- Verifier executed: document review against the coordinator's four scepticism targets and every B/C constraint; `git status --porcelain -- implementation/` (identical to session start).
- Result: C-002 PASS (every B1-B5 + B5-J clause adjudicated with evidence), C-003 PASS (C1-C14 adjudicated), C-004 PASS (all four targets with explicit findings; F1 empirically confirmed), C-005 PASS (§11 added in place with revision-history 1.2 and a clear verdict), C-006 PASS (no implementation file touched).
- New evidence: §11 in `docs/security/THREAT-MODEL-presentation-import.md` (now 679 lines); scratch harness output `REFERENCED-BOMB: Ok, slides=1, staged=0`.
- Decision: gate-review

## Risks and rollback

- Risks: adjudicating 20+ constraints across ~8.5k lines invites shallow sampling; mitigated by reading every load-bearing module fully and running the batteries rather than trusting their names.
- Risks: the review races concurrent commits in a WIP-heavy repo; mitigated by recording the reviewed git state and scoping the verdict to it.
- Rollback or recovery: docs-only output; the threat model revision can itself be revised.

## Pause and escalation conditions

- Pause if verification would require modifying `implementation/` or executing untrusted binaries outside the test batteries.
- Escalate to the owner: any FAIL on a blocker (merge gate), and the standing RR1 milestone condition.
- Escalate to Aria/Kenji: constraint failures needing design or code change.

## Final evaluation

- Validator command: `python3 scripts/validate_goal_contract.py docs/delivery/goals/GOAL-sec-presentation-import-postbuild-review.md --require-complete`
- Validator result: PASS
- Independent verification result: This post-build review IS the required independent security check for the feature; its verdict (merge with conditions) and RR acceptance are handed to the authorised human gate / product owner.
- Terminal state: GATE_REVIEW
- Remaining failed or blocked criteria: none for this review goal. Feature-level: MERGE WITH CONDITIONS — F1 test fix + a shell-slice post-build review before the importer is wired to a Tauri command.
- ClickUp final evidence comment: PENDING (ClickUp MCP unavailable this session; post to Build Control `86ajnx548` when available).
