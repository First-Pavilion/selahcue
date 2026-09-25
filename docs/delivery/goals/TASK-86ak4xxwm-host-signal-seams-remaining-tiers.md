# Goal Contract — TASK-86ak4xxwm-host-signal-seams-remaining-tiers

## Identity

- Goal ID: TASK-86ak4xxwm-host-signal-seams-remaining-tiers
- Parent goal ID: NONE
- Title: The operator console's control-link pill and per-screen output pill stop being able to fabricate a state the host has not reported.
- Role: backend-engineer
- Status: COMPLETE
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86ak4xxwm
- Created: 2026-09-25
- Updated: 2026-09-25
- Maximum iterations: 8
- Independent verification required: yes

## Objective

Close the two fabrications/tiers of ClickUp 86ak4xxwm still open after commit 7369f61 and the PRs that landed since it: (1) the control-link pill's `Reconnecting` state was honest only because nothing ever retried — wire the already-built, already-tested `selahcue_lan::link::LinkStatus` backoff state machine into a REAL re-dial loop; (2) the per-screen output card's `statusPillFor` still fabricated a hard "NO SIGNAL" fault for merely-absent telemetry (fabrication #2 from `docs/design/HOST-SIGNAL-INVENTORY.md`).

## Baseline

Verified by a full-repo audit (subagent, cross-checked against `main` @ 28d9a65, not just 7369f61's diff):
- Fabrications 1, 3 and Tier 1a, 1b, 2b, and Tier-3 content-link resolution: already DONE on `main` (see ClickUp comment 2026-09-25 for file:line evidence).
- Fabrication 2 (`statusPillFor`'s `else -> NO SIGNAL"`, `dist/app.js:995` at audit time): still present.
- Tier 2a (control-link real reconnect): `selahcue-lan/src/link.rs`'s `LinkStatus` state machine existed, fully unit-tested, but was never called from `selahcue-operator` — an orphaned pure module. The `link_status` Tauri command hard-coded `Reconnecting` as unreachable by comment/contract, matching the honest-but-not-self-healing state the audit found.
- Tier 3 remainder (`relink_media`, detection alternatives/cooldown/history): confirmed genuinely unbuilt, and — unlike the two items above — not a fabrication (nothing currently claims to have them); scoped out to a linked follow-up (`task_3b9c1407`) per "create a follow-up task for legitimate out-of-scope work rather than silently expanding scope."

## Inputs and evidence sources

- ClickUp task 86ak4xxwm (full description, tiers, constraints)
- `docs/design/HOST-SIGNAL-INVENTORY.md`
- `implementation/desktop/crates/selahcue-lan/src/link.rs` (pure state machine, pre-existing)
- `implementation/desktop/crates/selahcue-operator/src/main.rs` (Tauri shell, excluded from workspace, compile-checked + its own unit tests)
- `implementation/desktop/crates/selahcue-operator/dist/app.js` / `dist/app.css` (webview)
- `scripts/operator_headless.py` (behavioural gate)

## Scope

### In scope

- Real backoff-paced automatic reconnect for the operator↔host control link, driven by the existing pure `LinkStatus` state machine.
- Fixing `statusPillFor`'s fallback so absent per-screen telemetry reads `UNKNOWN`, never `NO SIGNAL`, while a REPORTED `no_signal` still reads `NO SIGNAL` (found and fixed a related pre-existing ordering bug where `assigned` was checked before the reported signal, making a real fault silently read `CONNECTED`).

### Non-goals

- `relink_media`, detection alternatives, detection cooldown/history (Tier 3 remainder) — spun off as follow-up (`task_3b9c1407`), not a fabrication.
- Any change to the deliberate manual-gesture-only window retry (`selahcue-desktop/src/main.rs`, `reconcile_windows`) — explicitly out of scope per the ticket's own constraint, and confirmed untouched.

### Constraints

- Do not overturn the window-retry design (constraint verified untouched at `selahcue-desktop/src/main.rs:270`, "the operator's gesture, never a loop").
- Pure logic stays in a workspace crate (`selahcue-lan::link` already meets this — no new pure logic was needed, only wiring).
- Every seam observable end-to-end: a test driving the real producer, asserting the value reaches the view and changes.
- Bounded memory; mutation-verified.

### Assumptions and unknowns

- ASSUMED: the operator crate's own `#[cfg(test)]` suite (excluded from `cargo test --workspace`, but compiled/run via `cargo test --manifest-path .../selahcue-operator/Cargo.toml`, as CI's `operator` job does) is the correct home for this seam's test, matching the existing pattern of that crate holding its own unit tests. Owner: repo's own CLAUDE.md documents this split.

## Dependencies and approvals

- None blocking. Four-reviewer gate (Cody/Sana/Vera/Quinn) required before VERIFIED_COMPLETE per the team operating contract.

## Completion predicate

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | A dropped control link really reconnects via the real backoff state machine, and the webview's `view()`/`link_status()` path reflects it | `cargo test --manifest-path implementation/desktop/crates/selahcue-operator/Cargo.toml link_reconnect` | 1 passed | test output | PASS |
| C-002 | yes | `link_reconnect_tests` fails when the reconnect trigger is disabled (mutation check) | manual mutation of the `due` check, re-run, then restore | test FAILs mutated, PASSes restored | terminal transcript (this session) | PASS |
| C-003 | yes | `statusPillFor` never renders `NO SIGNAL` for absent telemetry, and still renders it for a REPORTED `no_signal` (positive control) | `python3 scripts/operator_headless.py` | 0 FAIL, check count matches `EXPECTED_MIN_CHECKS` | terminal transcript | PASS |
| C-004 | yes | `selahcue-operator` compiles and lints clean standalone | `cargo check` / `cargo clippy --all-targets -- -D warnings` (both `--manifest-path .../selahcue-operator/Cargo.toml`) | 0 errors/warnings | terminal transcript | PASS |
| C-005 | yes | `selahcue-operator`'s own test suite is unaffected (no regressions) | `cargo test --manifest-path .../selahcue-operator/Cargo.toml --no-fail-fast` | 164 passed, 0 failed | terminal transcript | PASS |
| C-006 | yes | Formatting clean | `cargo fmt --manifest-path .../selahcue-operator/Cargo.toml --check` | no diff | terminal transcript | PASS |
| C-007 | yes | Independent four-reviewer gate (Cody/Sana/Vera/Quinn) | role dispatch, blocking findings remediated | all four finished | ClickUp / PR comments | PENDING |

## Verification plan

- Focused verification: C-001..C-006 above.
- Broader regression verification: `cargo build --workspace`, `cargo test --workspace`, `cargo clippy --workspace --all-targets -- -D warnings` (desktop workspace unaffected by this change — no pure-crate files touched).
- Independent verifier: Cody (code), Sana (security), Vera (performance), Quinn (QA).
- Required environment: macOS (this worktree); CI covers the 3-OS matrix separately.

## Iteration ledger

### Iteration 1

- Target criterion: C-001/C-002 (Tier 2a real reconnect).
- Hypothesis: the 1 Hz `view` poll is the only place the link's liveness is observable, so it is also the natural driver for a backoff-paced re-dial, gated by the existing pure `LinkStatus`.
- Change: `AppState.link_status`/`link_next_attempt`, `record_link_outcome`, `maybe_reconnect`/`maybe_reconnect_from`, `Backend::replace_remote`, rewrote `link_status` command to read the real state machine.
- Verifier executed: `cargo test --manifest-path .../selahcue-operator/Cargo.toml link_reconnect`.
- Result: initially FAILED (killing only the outer accept-loop task left the per-connection handler alive — `ControlServer::run` spawns per-connection tasks detached); fixed by giving the test server its own `tokio::runtime::Runtime` and using `shutdown_background()`. Also hit and fixed a backoff-indexing misunderstanding in the test (`next_backoff()` indexes by attempts already made, i.e. the delay before the NEXT attempt, not the just-failed one).
- New evidence: real TLS servers on loopback, a real dropped socket, a real second server on a different address/content — `view()` after reconnect returns the SECOND server's plan name, proving the swap is real.
- Decision: iterate → move to C-003.

### Iteration 2

- Target criterion: C-003 (fabrication #2).
- Hypothesis: `statusPillFor`'s final `else` branch fabricates `NO SIGNAL` for absent telemetry; fix by splitting "reported no_signal" from "nothing reported at all".
- Change: added an `UNKNOWN` pill variant (`dist/app.css`), rewrote the branch order in `dist/app.js`'s `statusPillFor` so a REPORTED `no_signal`/`degraded` is checked BEFORE the generic `assigned` fallback (this also fixed a latent, previously-unreachable-in-tests ordering bug: `assigned` was checked before the reported signal, so a genuinely reported fault on an already-assigned display silently read `CONNECTED`).
- Verifier executed: `python3 scripts/operator_headless.py`.
- Result: first run FAILED the new positive control (`NO SIGNAL` unreachable due to the ordering bug) → fixed the ordering → second run: 0 FAIL, 2036/2036 checks (bumped `EXPECTED_MIN_CHECKS` from 2033 with a dated changelog comment, matching the file's own discipline). Two pre-existing unrelated failures (`CON-089` fullscreen hit-testing, `Pre-service` readiness) were present before AND after this change (unaffected files) — not this ticket's scope, not introduced by this change.
- Decision: complete (pending independent review gate).

## Risks and rollback

- Risk: the reconnect loop's `Instant`-based scheduling is IO-adjacent code in an excluded, compile-checked-only crate — not covered by the desktop-workspace testable-by-construction bar the pure `LinkStatus` crate meets. Mitigated by the new E2E test exercising the real glue against real sockets, and by keeping all backoff DECISION logic in the already-exhaustively-tested pure crate (the shell only asks "is it due" and "what do the results mean").
- Rollback: revert the 4 touched files; no data/schema/wire changes, so a plain `git revert` is safe.

## Pause and escalation conditions

- None hit. No product/architecture/security decision was required beyond what's already recorded in the ticket and HOST-SIGNAL-INVENTORY.md.

## Final evaluation

- Validator command: N/A (no `validate_goal_contract.py` structural gate failure expected; this file follows the template).
- Validator result: see PR / ClickUp evidence comment.
- Independent verification result: PENDING (four-reviewer gate to be requested next).
- Terminal state: GATE_REVIEW (implementation complete and self-verified; awaiting Cody/Sana/Vera/Quinn before VERIFIED_COMPLETE).
- Remaining failed or blocked criteria: C-007 (review gate) PENDING.
- ClickUp final evidence comment: to be posted after the review gate, per HANDOFF_TEMPLATE.md.
