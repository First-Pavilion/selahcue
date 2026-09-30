# Goal Contract — TASK-86akcfp6z-audio-handoff-cap

## Identity

- Goal ID: TASK-86akcfp6z-audio-handoff-cap
- Parent goal ID: NONE (parent/unit-of-MR ClickUp ticket 86akcfp6z; no prior Goal Contract)
- Title: Fix the on-device audio hand-off cap (mono/stereo bug), the interim wall-clock
  backpressure loop, and add a runtime guard coupling `max_utterance_samples` to
  `WHISPER_AUDIO_CTX` — one branch, one MR, three remaining defects
- Role: backend-engineer (Kenji) — cross-crate: `selahcue-operator`, `selahcue-stt`
- Status: VERIFIED_COMPLETE
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86akcfp6z (parent); subtasks
  https://app.clickup.com/t/86akcfp8w, https://app.clickup.com/t/86akcfpbj,
  https://app.clickup.com/t/86akcgmvb; https://app.clickup.com/t/86akcfpa2 already satisfied on
  `main`, folded into this MR as evidence only, no new work
- Created: 2026-09-30
- Updated: 2026-09-30
- Maximum iterations: 10
- Independent verification required: yes (`make ci`, `cargo test --manifest-path
  implementation/desktop/crates/selahcue-stt/Cargo.toml` directly since that crate has no CI job,
  real `gh pr checks`, four-reviewer gate)

## Objective

On `origin/main` @ 30d35d9 (which already includes 86akby7th/PR #22), land the three still-open
defects from the same investigation as Phase 1 (86akcfp3u): (1) the on-device capture hand-off
cap must be derived from the real device sample rate/channel count, not a hardcoded stereo
literal; (2) the streaming-interim trigger must be gated on wall-clock elapsed time, not audio
position, so a recognizer falling behind does not demand interims faster than wall time allows;
(3) `max_utterance_samples` must be validated/clamped at `SttEngine` construction against the
horizon `WHISPER_AUDIO_CTX` implies, so a configured ceiling above it cannot silently drop
trailing words. One branch, one PR, all three fixes plus evidence that 86akcfpa2 is already
satisfied.

## Baseline (Verified — read directly from `origin/main` before starting)

- `selahcue-core/src/audio_capacity.rs`: `handoff_capacity(sample_rate_hz, channels, Duration) ->
  Option<NonZeroUsize>` already exists, fully implemented and tested (mono/stereo/zero-channel/
  zero-rate/overflow). **Correction (Quinn, QA review round 1):** this baseline originally also
  claimed the ticket's required compile-fail/compiling doctest pair on the `Duration` parameter
  "already exists" — it did not, on any commit reachable from this branch. Added and
  mutation-verified in this same PR (C-022).
- `selahcue-operator/src/capture_handoff.rs`: `AudioHandoff::new` already takes `NonZeroUsize`,
  already lives in this neutral module, already has a `dropped: u64` counter + non-vacuous test
  pair (86akcfpa2 — already satisfied, verified independently, evidence comment on that ticket).
- `selahcue-operator/src/listening.rs`: `run_cloud` (~line 1264) already derives its hand-off
  capacity via `handoff_capacity()` from the real device config and refuses to start on `None`.
  The ON-DEVICE path does not: `HANDOFF_MAX_SAMPLES` (~line 117) is still
  `NonZeroUsize::new(48_000 * 2 * 5)` — a hardcoded stereo assumption — and
  `run_on_device_with_recognizer` (~line 1137) still builds `AudioHandoff::new(HANDOFF_MAX_SAMPLES)`
  from that literal instead of the device's real config. The `sample_rate`/`channels` accessors
  needed to fix this exist only on the `cloud-stt`-gated `CloudCaptureSource` trait, not reachable
  from the on-device path in an `stt`-only build.
- `selahcue-stt/src/engine.rs`: `frames_since_interim: usize` (field ~97) increments once per
  processed VAD frame (~195) and gates the interim trigger (~207) on a frame count, not wall
  time. The module doc's "the engine reads no wall clock" claim is the ROOT of the bug: a
  recognizer draining a backlog processes many frames per real millisecond, so interim frequency
  rises exactly when the system is already behind (positive feedback).
- `selahcue-stt/src/recognizer.rs` (~145-194, inside the `whisper`-feature-gated module):
  extensive doc comment already states the `WHISPER_AUDIO_CTX` (512, giving a 10.24s content
  horizon) / `max_utterance_samples` (10.000s default) coupling problem and explicitly says this
  crate cannot enforce it from there. No runtime check exists anywhere in the crate.

## Inputs and evidence sources

- ClickUp 86akcfp6z, 86akcfp8w, 86akcfpbj, 86akcgmvb, 86akcfpa2 (full ticket text read via
  `clickup_get_task` before any code was written — the 86akcgmvb "CORRECTED 2026-09-05" fix
  direction supersedes that ticket's original text).
- `implementation/desktop/CLAUDE.md` — bounded-memory test discipline, injected-clock convention.
- `selahcue_core::timer::Timer` — the repo's established injected-clock pattern ("the caller
  supplies `now`") this fix mirrors for `SttEngine`.
- Four-reviewer gate: Cody (code), Vera (performance, two rounds — see below), Shadow (security),
  Quinn (QA, two rounds — see below), all dispatched against the real PR #124 diff, each with
  independent local verification (their own test runs, their own mutation testing), not taken on
  the implementer's word.

## Scope

### In scope

- `selahcue-operator/src/listening.rs`: rename the `cloud-stt`-gated `CloudCaptureSource` trait
  to an always-compiled `DeviceCaptureSource` shared by both routes; derive the on-device hand-off
  capacity via `handoff_capacity()` before the ready signal, refusing to start on an unusable
  device config (mirroring `run_cloud`); update the `HANDOFF_MAX_SAMPLES` /
  `MAX_PCM_SAMPLES` compile-time headroom assertion's role and docs now that the literal no
  longer feeds the real runtime cap; add `DeviceCaptureSource` impls to the test fakes that drive
  `run_on_device`/`run_on_device_with_recognizer`; an end-to-end mono-vs-stereo capacity test
  (`on_device_hand_off_capacity_is_mono_correct_not_stereo_doubled`, added in review round 2 —
  Vera F2).
- `selahcue-stt/src/engine.rs`: injected `Clock` seam (`SystemClock` default, `ManualClock` test
  double), replace `frames_since_interim` with wall-clock elapsed-since-last-interim gating,
  `EngineConfig.interim_interval_frames: usize` → `interim_interval: Duration`, a horizon
  constant mirroring (and compile-time pinned equal to, under `whisper`) `recognizer.rs`'s real
  `WHISPER_AUDIO_CTX`, and a construction-time clamp of `max_utterance_samples` against it. The
  wall-clock stamp for "last interim fired" is taken AFTER the interim's own decode completes,
  not before (review round 2 — Vera F1, blocking; see C-025) — this is the single most important
  correctness detail of the whole fix and the one place an initial implementation got it wrong.
- `selahcue-stt/tests/bounded_memory.rs`, `selahcue-operator/src/listening.rs`'s own
  `EngineConfig` call site: updated for the renamed/retyped config field; `bounded_memory.rs`'s
  force-close test corrected to count `is_final` segments only, not finals+interims together
  (review round 2 — Vera F3).
- `selahcue-core/src/audio_capacity.rs`: compile-fail/compiling doctest pair on `handoff_capacity`
  (review round 1 — Quinn, found missing).
- Tests: mono/stereo positive controls for the on-device cap (rewritten once for a fragmentation
  flake, then once more for a weak positive control — see C-001/C-026); backlog-simulation +
  steady-state positive control for the interim gate (steady-state test rewritten in round 2 to
  pin the corrected `interim_interval + decode_time` cadence — C-027); a slow-decode regression
  test reproducing Vera's exact F1 finding (C-025); clamp + benign-passthrough positive control
  for the `max_utterance_samples` guard; a recognizer test double proving the pre-guard failure
  mode (identical/truncated output past the horizon) is real; a same-crate default-value guard
  test (round 1 — Quinn, found missing — C-023).

### Non-goals

- 86akcfpa2 (dropped-audio counter/log) — already satisfied on `main`, no new work, cited as
  evidence only.
- 86akcgmuh (10s force-close boundary repetition-loop failure) — different root cause, no agreed
  fix direction, explicitly out of scope.
- 86akcfwdr (`selahcue-operator` `[lib]` target so its doctests execute) — explicitly deferred
  follow-up, not folded in here.
- Raising `WHISPER_AUDIO_CTX` to 576 for headroom — optional menu item on 86akcgmvb, not required
  to close it; not done here (512 kept).
- True streaming/incremental whisper decode, coalescing interims — pre-existing documented
  follow-ups, unrelated to these three defects.
- A "hybrid stamp" design that would preserve a flat `interim_interval` cadence for a fast decode
  (Vera's option (b) on N2) — deliberately rejected in favour of the simpler, honest
  `interim_interval + decode_time` characteristic (coordinator decision, review round 2).
- An app-owned upper ceiling on the derived hand-off capacity for a device reporting a
  pathological sample-rate/channel-count (Shadow's Low advisory) — tracked as a follow-up ticket
  (86ak_TBD — to be filed), not blocking, same exposure already exists on the pre-existing Cloud
  route since 86akby7th.

### Constraints

- One ticket (86akcfp6z), one branch (`fix/86akcfp6z-audio-handoff-cap`), one PR against `main`
  — all three remaining defects land together, per the parent ticket's explicit mandate.
- No-leak: no new unbounded buffering anywhere in this change (86akcfpbj's own criterion).
- `selahcue-stt` has no CI job — its tests must be run directly
  (`cargo test --manifest-path implementation/desktop/crates/selahcue-stt/Cargo.toml`) in
  addition to `make ci`, since CI will not catch a regression there.
- Do not implement 86akcgmvb's ORIGINAL (compile-time-only) fix direction — corrected 2026-09-05,
  a runtime check/clamp is the primary criterion.
- Do not modify PR #23's existing `WHISPER_AUDIO_CTX` range/`%4==0` alignment const-assert —
  different purpose, must stay as-is.
- Shared checkout: only one `make ci` at a time; checked for other active sessions before each
  run.

### Assumptions and unknowns

- ASSUMED: clamping (not refusing) `max_utterance_samples` at `SttEngine` construction is an
  acceptable "deliberate, tested choice" per 86akcgmvb's wording, since refusing would require
  changing `SttEngine::build`'s return type to `Result<...>` and rippling through every
  production and test call site across two crates — a much larger blast radius for the same
  guarantee. Flagged for reviewer sign-off — no reviewer objected to this choice across two
  review rounds (Cody, Vera, Shadow, Quinn all examined the clamp mechanism directly).
- ASSUMED: exposing `ManualClock`/`Clock`/`build_with_clock` as plain public items (not behind a
  `test-support` Cargo feature) is consistent with this crate's existing precedent
  (`FakeRecognizer`, `FakeAudioSource` are unconditionally public, used the same way). Unchallenged
  by any reviewer.
- RESOLVED (was ASSUMED, now a recorded design decision — review round 2): the corrected
  steady-state interim cadence is `interim_interval + decode_time`, not a flat `interim_interval`
  as 86akcfpbj's original acceptance-criteria wording literally states ("cadence unchanged from
  today's ~0.8s behaviour"). This is a genuine, deliberate deviation from the ticket's literal AC
  text, made explicit rather than silently implemented — see C-007 and C-027, and the ClickUp
  comment posted on 86akcfpbj recording the correction.

## Dependencies and approvals

- 86akby7th (PR #22) — MERGED (commit 72ded2d), confirmed before branching. No longer a blocker.
- Four-reviewer gate (Cody, Vera, Shadow — replaced Sana in the active roster, Quinn) — run to
  completion across two rounds (see Iteration ledger). All blocking findings remediated and
  independently re-confirmed by the finding reviewer (Vera, Quinn) against the final head.

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | On-device hand-off capacity is derived from the real device sample rate/channel count via `handoff_capacity()`, not a hardcoded literal, end to end through the real capture/recognition path | `on_device_hand_off_capacity_is_mono_correct_not_stereo_doubled` in `listening.rs`; mutation-verified against `HANDOFF_MAX_SAMPLES.max(handoff_capacity)` (Vera's exact reproduction) | test passes on real code (stable across 10+ repeated runs); reddens under the mutation | test output (both runs, both commits — first attempt was flaky on a razor-thin bracket, rewritten with decoupled margins) | PASS |
| C-002 | yes | On-device path refuses to start (clear error) on an unusable device config, mirroring `run_cloud` | `on_device_refuses_to_start_on_an_unusable_device_config` in `listening.rs` | test asserts `ready_rx` receives `Err` for a zero-channel source | test output | PASS |
| C-003 | yes | Both routes (on-device and Cloud) consume the identical `DeviceCaptureSource`/`handoff_capacity` definition — no independent computation | code review of `listening.rs`; Cody + Vera round-1 review independently confirmed exactly one trait, one function, two call sites | one trait (`DeviceCaptureSource`), one function (`handoff_capacity`), two call sites (`run_on_device_with_recognizer`, `run_cloud`) | listening.rs diff; Cody's PR comment | PASS |
| C-004 | yes | The `MAX_PCM_SAMPLES` compile-time headroom assertion still compiles and its role is documented accurately post-fix | `cargo check --features stt` | compiles; doc comment states `HANDOFF_MAX_SAMPLES` is a modeling constant, not the live runtime cap | build output + diff | PASS |
| C-005 | yes | `SttEngine`'s interim trigger is gated on wall-clock elapsed time via an injected `Clock`, not a frame counter, stamped AFTER the interim's own decode completes (not before — see C-025) | code review of `engine.rs`; Vera round-2 re-review, independently re-derived | `frames_since_interim` field removed; a wall-clock timestamp field stamped with a fresh `self.clock.now()` taken after `emit_interim()` returns | engine.rs diff; Vera's PR comment | PASS |
| C-006 | yes | A backlog-simulation test proves interim frequency does NOT rise while a recognizer is behind (mutation-verified against the old counter) | `cargo test --manifest-path implementation/desktop/crates/selahcue-stt/Cargo.toml engine::tests` | `a_backlog_burst_fires_zero_interims_when_zero_real_time_elapses` passes on current code; fails when reverted to a frame-count gate (49 interims observed under mutation) | test output (both runs); Quinn round-2 independently re-ran and re-confirmed | PASS |
| C-007 | yes | A steady-state positive control pins the REAL interim cadence formula, `interim_interval + decode_time` (CORRECTED from the ticket's original literal wording "cadence unchanged from today's ~0.8s behaviour" — see the Assumptions section and the ClickUp comment on 86akcfpbj recording this correction) | `steady_state_cadence_is_interim_interval_plus_decode_time` in `engine.rs`; mutation-verified against the pre-decode stamp | passes on real code (gap ≈850ms for an 800ms interval + 50ms simulated decode); reddens under the pre-decode-stamp mutation (measured gap ≈810ms, outside the expected band) | test output (both runs) — see C-027 | PASS |
| C-008 | yes | `max_utterance_samples` is validated/clamped at `SttEngine` construction against a horizon mirroring `WHISPER_AUDIO_CTX`, not by a compile-time-only assert | code review of `engine.rs`; `cargo test --manifest-path .../selahcue-stt/Cargo.toml` | over-horizon config clamped at `build`/`build_with_clock` (logged via `eprintln!`); `max_utterance_samples_above_the_horizon_is_clamped_at_construction` asserts the clamped value; mutation-verified | test output (both runs) | PASS |
| C-009 | yes | A benign in-bounds `max_utterance_samples` passes through unclamped (positive control) | `a_benign_max_utterance_samples_passes_through_unclamped` | unaffected value asserted | test output | PASS |
| C-010 | yes | A test proves the pre-guard failure mode is real (identical/truncated recognizer output past the horizon), so the guard's target is proven not assumed | `the_ctx_limited_fake_reproduces_the_real_truncation_plateau` + `the_clamp_keeps_every_utterance_handed_to_the_recognizer_at_or_under_the_horizon` | dedicated `CtxLimitedFakeRecognizer` double demonstrates the plateau; end-to-end test proves the clamp reaches the force-close boundary | test output | PASS |
| C-011 | yes | The horizon constant is pinned equal to `recognizer.rs`'s real `WHISPER_AUDIO_CTX` at compile time when `whisper` is compiled in | `cargo check --manifest-path implementation/desktop/crates/selahcue-stt/Cargo.toml --features whisper,capture`; mutation-verified (mismatched constant) | compiles on real code; a deliberate mismatch fails the BUILD with `error[E0080]`, not merely a test | build output (both runs) | PASS |
| C-012 | yes | PR #23's existing `WHISPER_AUDIO_CTX` range/alignment const-assert is untouched | `git diff` on `recognizer.rs`'s existing assert; Cody + Quinn both independently confirmed byte-identical to `origin/main` | no changes to that block | diff; reviewer comments | PASS |
| C-013 | yes | 86akcfpa2 is confirmed already satisfied on `main` — cited as evidence, no regression introduced | code review + existing test pass; Quinn round 1 and round 2 both independently confirmed `capture_handoff.rs` untouched (`git diff --stat` empty) | `capture_handoff.rs` tests still pass unchanged | test output; Quinn's PR comments | PASS |
| C-014 | yes | No new unbounded buffering introduced anywhere in this change | code review of all diffs; Vera round 1 explicitly confirmed (the hand-off holds a fixed wall-clock window of whatever the device delivers — bounded by time, not by an unbounded count) | every new buffer/collection is bounded or per-call, no growth without bound | diff review notes; Vera's PR comment | PASS |
| C-015 | yes | `make ci` green on this branch, on the final head commit | `make ci` from repo root | exit 0, all steps pass, "ALL GREEN" marker printed | terminal output (run against final head `7dac215`) | PASS |
| C-016 | yes | `selahcue-stt`'s tests pass run directly (no CI job covers this crate) | `cargo test --manifest-path implementation/desktop/crates/selahcue-stt/Cargo.toml` (default features) and `--features whisper,capture` | exit 0; 44 unit + 4 bounded_memory + 3 pipeline tests pass | terminal output | PASS |
| C-017 | yes | Branch is up to date with `origin/main` immediately before requesting review | `git fetch origin main && git rev-list --count HEAD..origin/main` | 0 (checked and re-checked before every push) | terminal output | PASS |
| C-018 | yes | Draft PR opened against `main`, not merged by this session | `gh pr view 124` | PR exists, opened as Draft, not merged | https://github.com/First-Pavilion/selahcue/pull/124 | PASS |
| C-019 | yes | Real `gh pr checks` green (3-OS matrix), not just local `make ci` | `gh pr checks 124` on the final head commit | all applicable checks pass; path-filtered jobs (marketing/flutter/api) correctly skip | checks output (final commit `7dac215`) | PASS |
| C-020 | yes | Four-reviewer gate (Cody, Vera, Shadow, Quinn) run, blocking findings remediated and independently re-checked | reviewer reports across two rounds; Vera and Quinn (the two with blocking findings) specifically re-dispatched as fresh agents to re-derive against the final head, per coordinator instruction, rather than accepting the implementer's own mutation evidence alone | Cody 0 blocking (1 Medium fmt, fixed); Shadow 0 blocking (1 Low advisory, follow-up ticket); Vera round 1: 1 High BLOCKING (F1) + 2 non-blocking (F2/F3), all fixed; Vera round 2 (re-review): F1/F2/F3 confirmed closed by independent re-derivation, 2 further Low non-blocking (N1/N2), both fixed; Quinn round 1: 2 BLOCKING (missing doctest pair, missing default-value test), both fixed; Quinn round 2 (re-review): both confirmed closed by independent re-derivation, 0 new findings | published review report artifact link (see below) | PASS |
| C-021 | yes | Goal Contract validator green (structural + completion) | `validate_goal_contract.py` (both modes) | exit 0 both | terminal output | PASS |
| C-022 | yes | 86akcfp8w's compile-fail/compiling doctest PAIR on `handoff_capacity`'s `Duration` parameter exists in `selahcue-core` and actually executes under the 3-OS `rust` CI job (Quinn, QA review round 1 — found missing) | `cargo test -p selahcue-core --doc`; mutation check (widen the param to `u64`, confirm both doctests go red, restore) | 2 doctests pass on real code; both fail under the mutation (`Couldn't compile the test` / `compiled successfully, but it's marked compile_fail`) | terminal output (both runs); Quinn round 2 independently re-ran and re-confirmed | PASS |
| C-023 | yes | 86akcgmvb's "sooner, weaker" same-crate test pins `EngineConfig::default().max_utterance_samples` specifically under the horizon (Quinn, QA review round 1 — found missing; prior tests used only synthetic over/under values, not the real default) | `cargo test --manifest-path implementation/desktop/crates/selahcue-stt/Cargo.toml engine::tests::the_default_max_utterance_samples_stays_under_the_whisper_ctx_horizon`; mutation check | passes on real code; fails when the default is mutated above the horizon | terminal output (both runs); Quinn round 2 independently mutation-tested this herself | PASS |
| C-024 | yes | Goal Contract's own baseline no longer misstates that the doctest pair already existed | this file's Baseline section | correction recorded, not silently edited away | this file | PASS |
| C-025 | yes | Interim wall-clock stamp is taken AFTER the interim's decode completes, not before (Vera, review round 1, F1 — HIGH, BLOCKING: the pre-decode stamp reintroduced a STRONGER version of 86akcfpbj's own feedback loop, since every retrigger now cost a full decode) | `a_slow_decode_does_not_retrigger_before_it_actually_completes`; mutation-verified against the pre-decode stamp; independently re-derived by Vera round 2 (her own mutation reproduced the identical 50-vs-0 numbers) and by Quinn round 2 | passes on real code (0 extra decodes over a 50-frame backlog after a 1s decode); reddens under the pre-decode-stamp mutation (exactly 50 extra decodes, matching Vera's original empirical finding) | test output (both runs, both by implementer and independently by Vera/Quinn) | PASS |
| C-026 | yes | The mono/stereo on-device capacity test's stereo assertion is a genuine positive control — same flood as the mono assertion, not a separately-chosen smaller value (Vera, review round 2, N1) | `on_device_hand_off_capacity_is_mono_correct_not_stereo_doubled` | both mono and stereo checks flood with the identical 350,000 samples | test output; listening.rs diff | PASS |
| C-027 | yes | `EngineConfig::interim_interval`'s doc comment, the `listening.rs` construction-site comment, and the steady-state test all state and pin the REAL cadence formula (`interim_interval + decode_time`), not the ticket's original "unchanged" wording (Vera, review round 2, N2) | doc review of `engine.rs`/`listening.rs`; `steady_state_cadence_is_interim_interval_plus_decode_time` | docs updated; test uses a nonzero simulated decode cost and asserts the additive formula, mutation-verified | engine.rs/listening.rs diff; test output (both runs) | PASS |

## Verification plan

- Focused verification: `cargo test --manifest-path implementation/desktop/crates/selahcue-stt/Cargo.toml`
  for engine.rs's own tests; `cargo test -p selahcue-operator --features stt,cloud-stt` for
  listening.rs's own tests (mutation-verified every new/changed positive-control pair per
  `implementation/desktop/CLAUDE.md`'s bounded-memory-test discipline: break the guard, confirm
  RED, restore — done by hand for every criterion above, and independently repeated by Vera and
  Quinn in their round-2 re-reviews).
- Broader regression verification: `make ci` (fmt, clippy, full workspace test matrix, operator
  compile-check, headless webview check) — run 5 times across the branch's lifetime (once per
  commit, plus one re-run after a rebase onto `origin/main`), green every time on the final state
  of each commit.
- Independent verifier: four-reviewer gate (Cody/Vera/Shadow/Quinn), with the two reviewers who
  found blocking issues (Vera, Quinn) specifically re-dispatched as fresh agents against the
  final head to re-derive their own findings rather than accept the implementer's fix claim —
  both came back CLEAN. Real `gh pr checks` on the 3-OS matrix, green on the final commit.
- Required environment: local macOS dev machine with cmake on PATH for the native `whisper`/
  `capture` feature build (per this workspace's known PATH gap — `/opt/homebrew/bin` already on
  PATH in this environment).

## Iteration ledger

### Iteration 1 — on-device hand-off cap (C-001..C-004)

- Target criterion: C-001..C-004
- Hypothesis: deriving the on-device capacity via the existing `handoff_capacity()` function,
  mirroring `run_cloud`'s already-correct pattern, closes 86akcfp8w's remaining gap with minimal
  new surface area.
- Change: renamed `CloudCaptureSource` → `DeviceCaptureSource`, un-gated it, wired
  `run_on_device_with_recognizer` to derive capacity before the ready signal, refuse on `None`.
- Verifier executed: `cargo test -p selahcue-operator --features stt,cloud-stt`.
- Result: PASS (186/194 then 195/195 across iterations as tests were added).
- Decision: iterate to interim gate.

### Iteration 2 — interim wall-clock gate (C-005..C-007)

- Target criterion: C-005..C-007
- Hypothesis: an injected `Clock` seam, wall-clock-gated interim trigger, closes 86akcfpbj.
- Change: `Clock`/`SystemClock`/`ManualClock`, `frames_since_interim` → `last_interim_at`.
- Verifier executed: `cargo test --manifest-path .../selahcue-stt/Cargo.toml`.
- Result: initial PASS — later found INCOMPLETE in review round 2 (see Iteration 5, C-025).
- Decision: iterate to max_utterance_samples guard.

### Iteration 3 — max_utterance_samples / WHISPER_AUDIO_CTX guard (C-008..C-012)

- Target criterion: C-008..C-012
- Hypothesis: a construction-time clamp against a mirrored, compile-time-pinned horizon constant
  satisfies 86akcgmvb's corrected (runtime, not compile-time-only) direction.
- Change: `WHISPER_AUDIO_CTX_HORIZON_SAMPLES`, clamp in `build_with_clock`, cross-check assert.
- Verifier executed: `cargo check --features whisper,capture`; mutation test on the cross-check.
- Result: PASS.
- Decision: proceed to `make ci`, push, open Draft PR, dispatch four-reviewer gate round 1.

### Iteration 4 — four-reviewer gate round 1 (C-013..C-024)

- Target criterion: full acceptance-criteria coverage across all 5 tickets, `make ci`, `gh pr checks`.
- Change/investigation: dispatched Cody, Vera, Shadow, Quinn against PR #124.
- Result: Cody 0 blocking (1 Medium fmt); Shadow 0 blocking (1 Low advisory); Vera 0 blocking at
  this point (round 1 report); Quinn 2 BLOCKING (missing doctest pair — C-022; missing
  default-value test — C-023).
- New evidence: fixed both Quinn blocking items, fixed Cody's fmt finding.
- Decision: iterate — a real GitHub Actions CI failure (`rust (windows-latest)`,
  `selahcue-data`'s WAL-checkpoint timing test) was also diagnosed as an unrelated pre-existing
  flake (main's last run green including this test; the diff touches none of `selahcue-data`) and
  confirmed by re-running just that job, which passed on retry.

### Iteration 5 — Vera's F1 (blocking) surfaces; review round 2 (C-025..C-027)

- Target criterion: C-025..C-027 (discovered mid-round, not planned at contract authoring time)
- Hypothesis: none yet — Vera's round-1 report (delivered after Quinn's, on a re-notification)
  revealed F1: `last_interim_at` was stamped with the pre-decode `now`, not a post-decode read —
  reintroducing a STRONGER version of 86akcfpbj's own bug for any decode taking longer than
  `interim_interval`.
- Change: moved the stamp to `Some(self.clock.now())` taken after `emit_interim()` returns; added
  `a_slow_decode_does_not_retrigger_before_it_actually_completes`.
- Verifier executed: mutation test (reverted stamp, confirmed exactly 50 extra decodes matching
  Vera's own empirical number; restored, confirmed 0).
- Result: PASS for F1. Also fixed Vera's 2 non-blocking round-1 items (F2: no test pinned the
  actual on-device capacity end to end — first attempt flaky on a fragmentation-sensitive
  threshold, rewritten with decoupled margins; F3: `bounded_memory.rs`'s force-close test counted
  interims+finals together, vacuous against a disabled cap — fixed to count `is_final` only).
- New evidence: per coordinator instruction, re-dispatched Vera AND Quinn (the two reviewers with
  blocking findings) as FRESH agents against the new head, explicitly told not to trust the
  implementer's own claim. Both came back and independently re-derived everything themselves —
  Quinn: CLEAN, re-ran both her original criteria plus 86akcfpbj's two criteria given the
  production-code change, 51/51 and 195/195 fresh test runs. Vera: F1/F2/F3 confirmed closed
  (her own simulation harness, her own mutation reverts, matching her original numbers exactly),
  but found 2 further Low, non-blocking items from re-checking her own fix: N1 (the stereo
  positive control used a separately-chosen, weaker flood value than the mono check, instead of
  the same input — the discriminating property of a positive control) and N2 (the corrected
  cadence is `interim_interval + decode_time` for ANY decode_time > 0, not only during a backlog
  — a real, honest, and safer characteristic the ticket's literal AC wording did not anticipate,
  needing the AC/docs corrected and a test that could actually see it, since the prior test used
  a zero-cost `FakeRecognizer` and could not distinguish the two designs at all).
- Decision: fixed both (N1: identical 350,000-sample flood for mono and stereo; N2: corrected
  `EngineConfig`/`listening.rs` docs, rewrote the steady-state test with a real simulated decode
  cost, mutation-verified). `make ci` and `gh pr checks` re-run green on the final commit.
  Complete.

## Risks and rollback

- Risks: changing `EngineConfig.interim_interval_frames` to `interim_interval: Duration` is a
  breaking field rename across two crates (listening.rs, bounded_memory.rs) — mitigated by
  compiler-enforced exhaustiveness (any missed call site fails to compile, not a silent runtime
  gap). Clamping (vs refusing) `max_utterance_samples` is a judgement call — unchallenged by any
  of the four reviewers across two rounds. Renaming `CloudCaptureSource` → `DeviceCaptureSource`
  touches every test fake that implements it — mitigated by compiler enforcement. **Realized
  risk, caught by review:** the interim wall-clock stamp's exact placement (before vs after the
  decode) was subtle enough that the implementer got it wrong on the first pass and every
  implementer-written test passed anyway (all used a zero-cost `FakeRecognizer`), because the bug
  is invisible whenever decode time is negligible relative to `interim_interval` — this is
  precisely why the independent-reviewer requirement in the operating contract exists, and why
  the coordinator's instruction to re-dispatch the finding reviewers specifically (rather than
  accept the implementer's own mutation evidence) mattered here: a self-authored "confirming"
  test is not the same evidence as an adversarial one written by someone who doesn't yet believe
  the fix is correct.
- Rollback or recovery: single feature branch, not merged by this session; `git revert` or drop
  the branch if a reviewer finds a fundamental issue. No production data or migrations involved.

## Pause and escalation conditions

- A rebase conflict against `origin/main` that requires a judgement call this role is not
  equipped to make. (Did not occur — the one rebase needed was a clean, non-overlapping
  dependency-lockfile-only fast-forward.)
- A four-reviewer finding that contradicts this contract's ASSUMED clamp-vs-refuse decision. (Did
  not occur.)
- CI failure that cannot be attributed to this branch's own changes (check `ci-red` issue state
  first, per repo CLAUDE.md). (One occurred — `rust (windows-latest)`'s `selahcue-data` WAL test —
  diagnosed as a pre-existing flake, confirmed green on a same-commit re-run, no code change
  needed for it.)

## Final evaluation

- Validator command: `python3 ~/.claude/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/TASK-86akcfp6z-audio-handoff-cap.md` (structural) and the same with `--completion`
- Validator result: both green — `OK (structural): ... satisfies the Goal Contract schema` and `OK (completion): ... satisfies the Goal Contract schema and all mandatory criteria PASS`
- Independent verification result: four-reviewer gate complete across two rounds; the two
  reviewers with blocking findings (Vera, Quinn) both independently re-confirmed their fixes
  against the final head commit, from scratch, without relying on the implementer's own claims.
  Real `gh pr checks` green on the 3-OS matrix. Local `make ci` green.
- Terminal state: VERIFIED_COMPLETE
- Remaining failed or blocked criteria: none
- ClickUp final evidence comment: posted on 86akcfp6z and its three still-open subtasks
  (86akcfp8w, 86akcfpbj, 86akcgmvb) per `HANDOFF_TEMPLATE.md`
