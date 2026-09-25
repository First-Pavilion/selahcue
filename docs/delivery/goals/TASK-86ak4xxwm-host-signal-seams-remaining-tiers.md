# Goal Contract — TASK-86ak4xxwm-host-signal-seams-remaining-tiers

## Identity

- Goal ID: TASK-86ak4xxwm-host-signal-seams-remaining-tiers
- Parent goal ID: NONE
- Title: The operator console's control-link pill and per-screen output pill stop being able to fabricate a state the host has not reported.
- Role: backend-engineer
- Status: GATE_REVIEW
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
| C-001 | yes | A dropped control link really reconnects via the real backoff state machine, driven through the LITERAL production call path (`view` → `view_body`), and the webview's `view()`/`link_status()` path reflects it | `cargo test --manifest-path implementation/desktop/crates/selahcue-operator/Cargo.toml link_reconnect` | 1 passed | test output | PASS |
| C-002 | yes | `link_reconnect_tests` fails when the reconnect scheduling guard is removed (mutation check) — must fail against the REAL bug all four reviewers found (unconditional deadline rewrite), not a copy of the predicate | manual mutation of `record_poll_outcome`'s reconnecting-guard, re-run, then restore | test FAILs mutated, PASSes restored | terminal transcript (this session, both before and after remediation) | PASS |
| C-003 | yes | `statusPillFor` never renders `NO SIGNAL` for absent telemetry, and still renders it for a REPORTED `no_signal` (positive control); headless suite has 0 FAIL globally (not just in the new checks) | `python3 scripts/operator_headless.py` | 0 FAIL, check count matches `EXPECTED_MIN_CHECKS` (2036) | terminal transcript | PASS |
| C-004 | yes | `selahcue-operator` compiles and lints clean standalone | `cargo check` / `cargo clippy --all-targets -- -D warnings` (both `--manifest-path .../selahcue-operator/Cargo.toml`) | 0 errors/warnings | terminal transcript | PASS |
| C-005 | yes | `selahcue-operator`'s own test suite is unaffected (no regressions) | `cargo test --manifest-path .../selahcue-operator/Cargo.toml --no-fail-fast` | 165 passed, 0 failed | terminal transcript | PASS |
| C-006 | yes | Formatting clean | `cargo fmt --manifest-path .../selahcue-operator/Cargo.toml --check` | no diff | terminal transcript | PASS |
| C-007 | yes | Independent four-reviewer gate (Cody/Sana/Vera/Quinn) — round 1: 3 blockers + 1 high, all four independently found the same root-cause scheduling bug; remediated commit 993c1b7; round 2 requested | role dispatch, blocking findings remediated, re-review requested | all four finished, no unaddressed blocking findings | ClickUp / PR comments | PENDING |
| C-008 | yes | `selahcue-lan`'s new `ControlClient::COMMAND_TIMEOUT` does not regress the crate | `cargo test -p selahcue-lan --features server`, `cargo clippy -p selahcue-lan --all-targets --features server -- -D warnings`, `cargo fmt -p selahcue-lan --check` | 63 passed; 0 warnings; no diff | terminal transcript | PASS |
| C-009 | yes | Full desktop workspace regression-free after remediation (record_poll_outcome/record_dial_failure split, COMMAND_TIMEOUT) | `cargo test --workspace --no-fail-fast`, `cargo clippy --workspace --all-targets -- -D warnings` | 1553 passed, 0 failed; 0 warnings | terminal transcript (`/tmp/ws_test_full.log`, `/tmp/ws_clippy.log`, this session) | PASS |

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
- Result: first run FAILED the new positive control (`NO SIGNAL` unreachable due to the ordering bug) → fixed the ordering → second run: 0 FAIL, 2036/2036 checks (bumped `EXPECTED_MIN_CHECKS` from 2033 with a dated changelog comment, matching the file's own discipline). At the time, 4 unrelated-looking failures (`CON-089` fullscreen hit-testing, `Pre-service` readiness) were also observed and — **incorrectly** — assessed in this session as pre-existing/unrelated. They were not: Quinn's QA review (round 1) root-caused them to this iteration's OWN new test code (the positive control left `V.outputs = []` instead of restoring the harness's default fixture, leaking into every later check in the same page session) and reproduced the fix by restoring the default. Corrected in Iteration 3. Recorded here as a deliberate correction, not a silent edit — the original (wrong) claim is worth keeping visible as a reminder to verify "pre-existing" claims against a clean baseline rather than asserting them from a single run.
- Decision: iterate → four-reviewer gate.

### Iteration 3 (remediation round 1)

- Target criterion: C-001/C-002/C-007 (reviewer findings) + the C-003 correction above.
- Hypothesis: all three technical reviewers (Cody, Vera, Sana) independently reproduced the SAME root-cause bug by replaying the real production sequence against the real `LinkStatus` — the fix has to change WHEN `record_link_outcome` is allowed to touch `link_next_attempt`, not just how the test calls things.
- Change:
  - Split `record_link_outcome` into `record_poll_outcome` (starts the backoff sequence exactly once, on `Connected/Local -> Reconnecting`; never touches an already-pending deadline) and `record_dial_failure` (only a real `connect_remote` failure inside `maybe_reconnect_from` may advance `attempts`/reschedule from there) — closes Cody's Blocker, Vera P-1/P-4, Sana S-1/S-4.
  - `view` split into a thin command wrapper + `view_body(state, endpoint_source)`; the test now drives `view_body` itself in a bounded loop (the literal production sequence) instead of calling `record_link_outcome`/`maybe_reconnect_from` by hand — closes Vera P-2 / Sana S-2. Both fixed-duration sleeps in the test replaced with bounded poll-until-condition loops — closes Vera's flake note.
  - `read_endpoint` gained a bounded read + Unix mode-`0600` check — partial response to Sana S-3; the literal "pin must match the original boot connection" fix was rejected with recorded reasoning (`selahcue-desktop` mints a fresh identity + token on every process start, so pin continuity would silently defeat the crash-recovery scenario Tier 2a exists to serve).
  - `link_status_reply`'s poisoned-lock fallback changed from a fabricated static `"connected"` to an out-of-vocabulary `"unknown"` state string, which the webview's existing fallback already renders honestly — closes Sana S-5.
  - `ControlClient::COMMAND_TIMEOUT` (2s) added in `selahcue-lan/src/client.rs` — closes Vera P-3.
  - `scripts/operator_headless.py`'s `V.outputs` state leak fixed (restores the default fixture instead of `[]`) — closes Quinn's finding and the C-003 correction above.
- Verifier executed: `cargo test --manifest-path .../selahcue-operator/Cargo.toml --no-fail-fast`; mutation check (reintroduce the unconditional-reschedule bug, confirm RED, restore, confirm GREEN); `cargo clippy`/`cargo fmt --check` (operator); `cargo test -p selahcue-lan --features server`; `cargo clippy -p selahcue-lan --features server --all-targets -- -D warnings`; `cargo fmt -p selahcue-lan --check`; `cargo test --workspace --no-fail-fast`; `cargo clippy --workspace --all-targets -- -D warnings`; `python3 scripts/operator_headless.py`.
- Result: 165/165 operator tests (was 164; the rewritten reconnect test replaces the old one); mutation check fails the mutated version and passes the restored version; operator clippy/fmt clean; selahcue-lan 63/63, clippy/fmt clean; full workspace 1553/1553 passed, clippy clean; headless suite 2036/2036, 0 FAIL (confirms the C-003 correction — the 4 failures are gone with no other code change).
- Decision: handoff → re-review requested from all four reviewers (PR comment posted, commit 993c1b7).

## Risks and rollback

- Risk: the reconnect loop's `Instant`-based scheduling is IO-adjacent code in an excluded, compile-checked-only crate — not covered by the desktop-workspace testable-by-construction bar the pure `LinkStatus` crate meets. Mitigated by the new E2E test exercising the real glue against real sockets, and by keeping all backoff DECISION logic in the already-exhaustively-tested pure crate (the shell only asks "is it due" and "what do the results mean").
- Rollback: revert the 4 touched files; no data/schema/wire changes, so a plain `git revert` is safe.

## Pause and escalation conditions

- None hit. No product/architecture/security decision was required beyond what's already recorded in the ticket and HOST-SIGNAL-INVENTORY.md.

## Final evaluation

- Validator command: `python3 ~/.claude/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/TASK-86ak4xxwm-host-signal-seams-remaining-tiers.md` (structural) — PASS. `--completion` — FAILs on C-007 (expected: review gate not yet closed).
- Validator result: structural PASS; completion correctly blocked on C-007 pending re-review.
- Independent verification result: Round 1 complete — Cody (Blocker), Vera (FAIL, P-1/P-2 blocking + P-3 high), Sana (Blocked, S-1/S-2/S-3 blocking), Quinn (contradicted the PR's own claimed test-plan result, filed ClickUp 17tnw2ayw1r). All three technical reviewers independently reproduced the SAME root-cause scheduling bug against the real `LinkStatus`. Remediated in commit 993c1b7 (Iteration 3); re-review requested via PR comment. Round 2 outcome not yet known at the time of this evaluation entry.
- Terminal state: GATE_REVIEW (remediation complete and self-verified; awaiting round-2 confirmation from Cody/Sana/Vera/Quinn before VERIFIED_COMPLETE). NOT VERIFIED_COMPLETE — do not treat self-verification as a substitute for the closed review gate.
- Remaining failed or blocked criteria: C-007 (review gate) — round 1 findings remediated, round 2 pending.
- ClickUp final evidence comment: to be posted once C-007 clears, per HANDOFF_TEMPLATE.md.
