# Goal Contract — TASK-86ajxeq0j-present-flow-qa

## Identity

- Goal ID: TASK-86ajxeq0j-present-flow-qa
- Parent goal ID: STAGE8-core-presentation
- Title: Independent QA of the Presentation browse→present→edit flow (Track A + Track B)
- Role: qa-engineer
- Status: ACTIVE
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86ajxeq0j
- Created: 2026-08-07
- Updated: 2026-08-07
- Maximum iterations: 6
- Independent verification required: yes

## Objective

Independently verify the Presentation browse→present→edit flow satisfies the approved spec across happy, edge, permission, and failure paths — engine (authored-slide mirroring, atomic advance-and-present), host signals, and the webview flow — and fail safely; file reproducible ClickUp bugs for any defect.

## Baseline

**Verified (2026-08-07):** Track A (86ajxeq0y) implemented + independently reviewed (0 blockers). Track B (86ajxeq17) implemented (Slices 1–5) + independently reviewed; all 6 review findings fixed in `77efd35`. Author-reported: headless 365/0, `selahcue-present`/`-gpu`/`-app` green, operator `cargo check` clean. QA re-runs these independently.

## Inputs and evidence sources

- Spec: `docs/superpowers/specs/2026-08-04-presentation-browse-present-flow-design.md` (§6 interaction, §7 live-output/mirroring, §8 states, §9 a11y, §10 tokens).
- Track goal contracts: `TASK-86ajxeq0y-present-flow-backend.md`, `TASK-86ajxeq17-present-flow-frontend.md`.
- Diffs: Track A `bd90f9a..821be31`; Track B `51e3f4e..77efd35`.

## Scope

### In scope

- Functional verification of the flow (engine + host + webview); §8 state matrix; §9 a11y; §7 one-live-output + secondary/NDI mirroring; regression of the suites the change touches.

### Non-goals

- Fixing defects (file bugs; route to backend/frontend). External owner WIP (`stage.rs`, `test_protocol.rs`).

### Constraints

- Repo under active concurrent editing — a transient `stage.rs`/`test_protocol.rs` compile break is owner/other-process, not this story; note but do not attribute to the flow.
- Do not mark the story Done (independent QA gate); move only to the next valid status.

### Assumptions and unknowns

- ASSUMED: Chrome present for the headless gate (else it SKIPs loudly). Manual `make launch` is owner-run (GUI) — QA notes it as owner-verify.

## Dependencies and approvals

- Track A review-approved; Track B review-fixed. Full `make ci` also depends on external items (`stage.rs`, `test_protocol.rs`).

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| Q-001 | yes | Engine: authored-slide mirroring + never-blank + theme survival | `cargo test -p selahcue-present` | PASS | test output | PENDING |
| Q-002 | yes | GPU parity incl. authored scene | `cargo test -p selahcue-gpu` | PASS (or GPU-absent SKIP) | test output | PENDING |
| Q-003 | yes | Host: live_authored_id + go_live_delta clamp | `cargo test -p selahcue-app --test test_controller` + `cargo test --manifest-path .../selahcue-operator go_live_delta` | PASS | test output | PENDING |
| Q-004 | yes | Webview flow + §8 states + a11y | `python3 scripts/operator_headless.py` | 365+ checks, 0 FAIL | headless output | PENDING |
| Q-005 | yes | Operator crate compiles (integration) | `cargo check --manifest-path .../selahcue-operator/Cargo.toml` | clean | check output | PENDING |
| Q-006 | yes | Acceptance-criteria → test map; no uncovered mandatory criterion | review vs spec §6/§8/§9 | every criterion has a check or a justified gap | QA notes | PENDING |
| Q-007 | yes | Exploratory / adversarial probe for defects | inspection + targeted checks | defects filed as ClickUp bugs (or none found) | bug links / note | PENDING |
| Q-008 | yes | Verdict: no unresolved release-blocking defect in the flow | QA synthesis | stated verdict | ClickUp handoff | PENDING |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused: run each suite above from a clean invocation; inspect actual output (not exit code alone).
- Broader: note full `make ci` status incl. external blockers.
- Independent verifier: QA is the independent gate for the story; manual GUI (`make launch`) is owner-verify.
- Required environment: local dev (headless Chrome for the gate; GPU optional).

## Iteration ledger

### Iteration 1

- Target criterion: Q-001…Q-005 (run the suites, establish evidence)
- Hypothesis: the author-reported green state reproduces independently.
- Verifier executed:
- Result:
- Decision: iterate | handoff | blocked | gate-review | complete

## Risks and rollback

- Risks: concurrency-induced transient breaks (external); headless flakiness (poll-based, bounded). Rollback: N/A (QA is read-only; no code changes).

## Pause and escalation conditions

- A release-blocking defect in the flow → file a bug, set the track task appropriately, escalate to the owning role.
- Behaviour ambiguity vs spec → route to Product/Design, do not redefine.

## Final evaluation

- Validator command: `python3 scripts/validate_goal_contract.py docs/delivery/goals/TASK-86ajxeq0j-present-flow-qa.md`
- Validator result:
- Independent verification result:
- Terminal state:
- Remaining failed or blocked criteria:
- ClickUp final evidence comment:
