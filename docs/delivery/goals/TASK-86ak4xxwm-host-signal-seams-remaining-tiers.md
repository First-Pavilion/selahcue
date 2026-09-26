# Goal Contract — TASK-86ak4xxwm-host-signal-seams-remaining-tiers

## Identity

- Goal ID: TASK-86ak4xxwm-host-signal-seams-remaining-tiers
- Parent goal ID: NONE
- Title: The operator console's control-link pill and per-screen output pill stop being able to fabricate a state the host has not reported.
- Role: backend-engineer
- Status: VERIFIED_COMPLETE
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
| C-005 | yes | `selahcue-operator`'s own test suite is unaffected (no regressions) | `cargo test --manifest-path .../selahcue-operator/Cargo.toml --no-fail-fast` | 169 passed, 0 failed (164 at first fix; +5 `endpoint_guard_tests` for S-3a/S-3/S-9) | terminal transcript | PASS |
| C-006 | yes | Formatting clean | `cargo fmt --manifest-path .../selahcue-operator/Cargo.toml --check` | no diff | terminal transcript | PASS |
| C-007 | yes | Independent four-reviewer gate (Cody/Sana/Vera/Quinn), all rounds, no unaddressed blocking findings at the final head | role dispatch each round, blocking findings remediated, re-review requested and returned | all four finished PASS/Resolved | ClickUp / PR comments; consolidated report https://claude.ai/artifact/Jx54jpWiXUQAUESPubeAdV | PASS |
| C-008 | yes | `selahcue-lan`'s `ControlClient::COMMAND_TIMEOUT` + `poisoned`-on-timeout fix (Sana S-8) does not regress the crate | `cargo test -p selahcue-lan --features server --no-fail-fast`, `cargo clippy -p selahcue-lan --all-targets --features server -- -D warnings`, `cargo fmt -p selahcue-lan --check` | 126 passed (was 125; +1 `test_client_timeout.rs`); 0 warnings; no diff | terminal transcript | PASS |
| C-009 | yes | Full desktop workspace regression-free after all remediation rounds | `cargo test --workspace --no-fail-fast`, `cargo clippy --workspace --all-targets -- -D warnings` | 1586 passed, 0 failed (post-merge with `main`); 0 warnings | terminal transcript (`/tmp/ws_test_postmerge.log`, `/tmp/ws_clippy_postmerge.log`) | PASS |
| C-010 | yes | Real GitHub Actions CI green on the branch tip, up to date with `main` | `gh pr checks 101` | all non-skipped jobs pass (rust ×3 OS, operator shell ×3 OS, operator shell release-features ×3 OS, launch-smoke ×2, audit, supply chain, workflows) | CI run 36220547676 (after 2 reruns of a confirmed pre-existing, unrelated flake — `RCD-008`, PR #98's own headless check, reproduced flaky locally too, independently flagged by Cody) | PASS |
| C-011 | yes | Branch not behind the integration branch immediately before requesting review | `git rev-list --count HEAD..origin/main` | 0 | terminal transcript (merge commit `b2cf88d`) | PASS |

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

### Iteration 4 (round 2 re-review → Sana's new finding S-8 → fix)

- Target criterion: C-007 (round 2).
- Result: Quinn (resolved, closed ClickUp 17tnw2ayw1r) and Vera (PASS, re-measured P-1..P-4 live, 4 real dials/8.06s terminal give-up) confirmed round-1 fixes by independent re-measurement, not by reading the diff. Sana found a NEW blocking defect (S-8): `COMMAND_TIMEOUT` had no `request_id` correlation on the read side, so a timed-out request's abandoned reply could be silently consumed by the next `command()` call and reported as success — proven live (`Ok(State { live_item: Some(0) })` forever after one stall). For this ticket, that meant a stale-but-successful reply could cancel an already-scheduled reconnect and fabricate "Connected."
- Change: `ControlClient` gains a `poisoned` flag set on any timeout; every later `command()` on that connection is refused immediately rather than risking a desynchronized read (matches Sana's own preferred remedy over request_id correlation). New regression test `selahcue-lan/tests/test_client_timeout.rs` reproduces the exact scenario against a real pinned-TLS server with its own dedicated runtime.
- Verifier executed: mutation check (disable `poisoned`, confirm the test reproduces Sana's exact stale-reply failure; restore, confirm green); full operator + selahcue-lan suites; clippy/fmt both crates.
- Result: mutation-verified; 165→ (later 169 after S-3a tests) operator tests; selahcue-lan 63→126 (later, +1 for the new poisoning test, +more after S-3a's own lan-side nothing — count updates below). Commit `9ec3d74`.
- Decision: handoff → re-review requested (S-8 specifically).

### Iteration 5 (round 3 — S-8/S-3a confirmed, S-9 found and fixed, then real CI)

- Target criterion: C-007 (round 3) + C-010 (real CI, newly added).
- Result: Sana reproduced her own S-8 proof against the fixed code (now errors locally in 24μs, confirmed via her own independent probe) and mutation-verified both directions; accepted the S-3 counter-proposal after checking `selahcue-desktop::run_server` herself; found S-9 (non-blocking): `an_oversized_descriptor_is_refused` didn't guard the size check it named (mutation-verified — neutering the size check left it green because `Read::take` truncated the padded JSON into invalid JSON first). Cody's round-2 landed at this same head: confirmed the original Blocker resolved by static trace, and — independently, without prompting — found the SAME `stt,cloud-stt` compile break described below before I'd finished pushing the fix for it.
- Change: fixed S-9 exactly per Sana's own verified remedy (a complete, valid JSON object at exactly `MAX_ENDPOINT_FILE_LEN` bytes, trailing whitespace only pushing it over the cap). Separately, checking the REAL GitHub Actions run (not local default-feature builds) surfaced two genuine CI-only compile breaks: (a) `listening.rs`'s `#[cfg(feature = "stt")]`-gated test helpers still used the pre-Tier-2a field name `link_error` (5 sites) — invisible locally because local runs never used `--features stt,cloud-stt`; (b) this session's own new `endpoint_guard_tests` used `PermissionsExt`/`from_mode` unconditionally, breaking Windows outright, then a follow-up fix that gated `PermissionsExt` but missed that `std::io::Write` was also now unix-test-only, still breaking Windows via `-D warnings` unused-import.
- Verifier executed: `cargo test`/`clippy`/`fmt --check` for operator (default, `stt,cloud-stt`, `dev-keys`, `dev-keys,openai-notes`) and selahcue-lan (`--features server`), all locally green; then the REAL `gh pr checks 101` / `gh pr checks --watch` against actual GitHub Actions, twice more after each fix commit, until genuinely green.
- Result: commits `2b0ee49` (S-9 + first CI fix) and `b7fc13f` (second CI fix) — real CI (run 36219703172) fully green: 14/14 non-skipped jobs across the 3-OS matrix. All four reviewers now cleared with zero remaining blocking findings.
- Decision: handoff → mark PR ready, publish consolidated report, close out ClickUp.

### Iteration 6 (branch currency + final CI)

- Target criterion: C-009/C-010/C-011 (branch-not-behind check, per the team operating contract's pre-review requirement — caught only when explicitly checking `git rev-list --count HEAD..origin/main`, which read 4: an unrelated PR #102 had merged into `main` while this ticket's review rounds were running).
- Change: merged `origin/main` (clean auto-merge, no conflicts — PR #102 touched `selahcue-lan`/`selahcue-app`/`selahcue-data` in functions this ticket's diff does not touch) → commit `b2cf88d`.
- Verifier executed: `cargo build --workspace`, `cargo test --workspace --no-fail-fast`, `cargo clippy --workspace --all-targets -- -D warnings` locally post-merge; then real CI on the merge commit.
- Result: local: 1586/1586 tests (was 1553; +32 from PR #102's own new tests + this ticket's own additions), clippy clean. Real CI (run 36220547676) came back with ONE failure — `operator shell (ubuntu-latest)`, specifically `RCD-008`, a headless-webview check that belongs to an already-merged, unrelated PR (#98) and was already flagged by Cody as a ~1-in-6 intermittent flake. Independently reproduced the same flakiness locally (3 consecutive full `operator_headless.py` runs: 2 clean at 2036/2036, 1 unrelated infra timeout) before concluding it was environment timing variance rather than assuming it. Reran the failed CI job twice (`gh run rerun --failed`): failed identically the first rerun, passed clean the second. Filed a follow-up task (not this ticket's scope) to fix the underlying flakiness. Every other job passed on every attempt without a single retry.
- Result: real CI (run 36220547676) fully green on the second rerun — 14/14 non-skipped jobs. Branch confirmed 0 commits behind `main`.
- Decision: VERIFIED_COMPLETE. PR marked ready (not merged — owner's call). Consolidated Artifact updated to reflect all three rounds + final CI. ClickUp evidence comment posted.

## Risks and rollback

- Risk: the reconnect loop's `Instant`-based scheduling is IO-adjacent code in an excluded, compile-checked-only crate — not covered by the desktop-workspace testable-by-construction bar the pure `LinkStatus` crate meets. Mitigated by the new E2E test exercising the real glue against real sockets, and by keeping all backoff DECISION logic in the already-exhaustively-tested pure crate (the shell only asks "is it due" and "what do the results mean").
- Rollback: revert the 4 touched files; no data/schema/wire changes, so a plain `git revert` is safe.

## Pause and escalation conditions

- None hit. No product/architecture/security decision was required beyond what's already recorded in the ticket and HOST-SIGNAL-INVENTORY.md.

## Final evaluation

- Validator command: `python3 ~/.claude/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/TASK-86ak4xxwm-host-signal-seams-remaining-tiers.md --completion`
- Validator result: PASS — all mandatory criteria (C-001 through C-011) are PASS.
- Independent verification result: three review rounds, four reviewers (Cody, Vera, Sana, Quinn), zero blocking findings remaining. Round 1: all three technical reviewers independently reproduced the same root-cause scheduling bug against the real `LinkStatus` state machine; Quinn independently found the headless-suite state leak. Round 2: Sana found a further blocking defect (S-8) in round 1's own fix; Vera and Quinn confirmed round 1 resolved by re-measurement. Round 3: Sana confirmed S-8/S-3a resolved by her own independent reproduction and mutation testing, found one non-blocking test nit (S-9, fixed); Cody confirmed the original Blocker resolved and independently found the same CI-only compile break this session was fixing. Consolidated report, all three rounds: https://claude.ai/artifact/Jx54jpWiXUQAUESPubeAdV
- Real CI: GitHub Actions run 36220547676 (final branch tip, merged with `main`, 0 commits behind) — 14/14 non-skipped jobs green after one confirmed-flaky, unrelated job (`RCD-008`, pre-existing from PR #98) was reproduced locally, retried, and passed clean. https://github.com/First-Pavilion/selahcue/actions/runs/36220547676
- Terminal state: **VERIFIED_COMPLETE.**
- Remaining failed or blocked criteria: none.
- ClickUp final evidence comment: posted on 86ak4xxwm per HANDOFF_TEMPLATE.md.
- Not merged: PR #101 marked ready for review; merging is the repo owner's explicit call per the team operating contract, not this role's.
- Follow-ups spun off, not folded into this ticket: relink_media + detection alternatives/cooldown/history (Tier 3 remainder, pre-existing audit finding, task_3b9c1407); RCD-008 headless-suite flake fix (task_1320ade5); Vera's P-5 (manual retry command) and P-6 (webview poll-queueing during a command timeout) — recommended, not filed as ClickUp tickets by this session.
