# Goal Contract — TASK-86akcfp6z-audio-handoff-cap

## Identity

- Goal ID: TASK-86akcfp6z-audio-handoff-cap
- Parent goal ID: NONE (parent/unit-of-MR ClickUp ticket 86akcfp6z; no prior Goal Contract)
- Title: Fix the on-device audio hand-off cap (mono/stereo bug), the interim wall-clock
  backpressure loop, and add a runtime guard coupling `max_utterance_samples` to
  `WHISPER_AUDIO_CTX` — one branch, one MR, three remaining defects
- Role: backend-engineer (Kenji) — cross-crate: `selahcue-operator`, `selahcue-stt`
- Status: DRAFT
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
  zero-rate/overflow/doctest pair).
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

## Scope

### In scope

- `selahcue-operator/src/listening.rs`: rename the `cloud-stt`-gated `CloudCaptureSource` trait
  to an always-compiled `DeviceCaptureSource` shared by both routes; derive the on-device hand-off
  capacity via `handoff_capacity()` before the ready signal, refusing to start on an unusable
  device config (mirroring `run_cloud`); update the `HANDOFF_MAX_SAMPLES` /
  `MAX_PCM_SAMPLES` compile-time headroom assertion's role and docs now that the literal no
  longer feeds the real runtime cap; add `DeviceCaptureSource` impls to the test fakes that drive
  `run_on_device`/`run_on_device_with_recognizer`.
- `selahcue-stt/src/engine.rs`: injected `Clock` seam (`SystemClock` default, `ManualClock` test
  double), replace `frames_since_interim` with wall-clock elapsed-since-last-interim gating,
  `EngineConfig.interim_interval_frames: usize` → `interim_interval: Duration`, a horizon
  constant mirroring (and compile-time pinned equal to, under `whisper`) `recognizer.rs`'s real
  `WHISPER_AUDIO_CTX`, and a construction-time clamp of `max_utterance_samples` against it.
- `selahcue-stt/tests/bounded_memory.rs`, `selahcue-operator/src/listening.rs`'s own
  `EngineConfig` call site: updated for the renamed/retyped config field.
- Tests: mono/stereo positive controls for the on-device cap; backlog-simulation + steady-state
  positive control for the interim gate; clamp + benign-passthrough positive control for the
  `max_utterance_samples` guard; a recognizer test double proving the pre-guard failure mode
  (identical/truncated output past the horizon) is real.

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
- Shared checkout: only one `make ci` at a time; check `ListAgents` before running it.

### Assumptions and unknowns

- ASSUMED: clamping (not refusing) `max_utterance_samples` at `SttEngine` construction is an
  acceptable "deliberate, tested choice" per 86akcgmvb's wording, since refusing would require
  changing `SttEngine::build`'s return type to `Result<...>` and rippling through every
  production and test call site across two crates — a much larger blast radius for the same
  guarantee. Flagged for reviewer sign-off (Cody/Sana) rather than decided unilaterally.
- ASSUMED: exposing `ManualClock`/`Clock`/`build_with_clock` as plain public items (not behind a
  `test-support` Cargo feature) is consistent with this crate's existing precedent
  (`FakeRecognizer`, `FakeAudioSource` are unconditionally public, used the same way).

## Dependencies and approvals

- 86akby7th (PR #22) — MERGED (commit 72ded2d), confirmed before branching. No longer a blocker.
- Four-reviewer gate (Cody, Vera, Sana, Quinn) — required before VERIFIED_COMPLETE, not yet run.

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | On-device hand-off capacity is derived from the real device sample rate/channel count via `handoff_capacity()`, not a hardcoded literal | `grep -n "HANDOFF_MAX_SAMPLES" listening.rs` shows it no longer feeds `AudioHandoff::new` in `run_on_device_with_recognizer`; code review | `AudioHandoff::new(handoff_capacity)` where `handoff_capacity` comes from `source.sample_rate()`/`source.channels()` | listening.rs diff | PENDING |
| C-002 | yes | On-device path refuses to start (clear error) on an unusable device config, mirroring `run_cloud` | `cargo test -p selahcue-operator --features stt` (new dedicated test) | test asserts `ready_rx` receives `Err` for a zero-channel/zero-rate source | test output | PENDING |
| C-003 | yes | Both routes (on-device and Cloud) consume the identical `DeviceCaptureSource`/`handoff_capacity` definition — no independent computation | code review of `listening.rs` | one trait, one function, two call sites | listening.rs diff | PENDING |
| C-004 | yes | The `MAX_PCM_SAMPLES` compile-time headroom assertion still compiles and its role is documented accurately post-fix | `cargo check --features stt` | compiles; doc comment no longer claims `HANDOFF_MAX_SAMPLES` is the live runtime cap | build output + diff | PENDING |
| C-005 | yes | `SttEngine`'s interim trigger is gated on wall-clock elapsed time via an injected `Clock`, not a frame counter | code review of `engine.rs` | `frames_since_interim` field removed; a wall-clock timestamp field plus `self.clock.now()` gate the trigger | engine.rs diff | PENDING |
| C-006 | yes | A backlog-simulation test proves interim frequency does NOT rise while a recognizer is behind (mutation-verified against the old counter) | `cargo test --manifest-path implementation/desktop/crates/selahcue-stt/Cargo.toml engine::tests` | new test passes on current code; fails when reverted to a frame-count gate | test output (both runs) | PENDING |
| C-007 | yes | A steady-state positive control proves the ~0.8s cadence is unchanged in the ordinary (no-backlog) case | same test binary | passes | test output | PENDING |
| C-008 | yes | `max_utterance_samples` is validated/clamped at `SttEngine` construction against a horizon mirroring `WHISPER_AUDIO_CTX`, not by a compile-time-only assert | code review of `engine.rs`; `cargo test --manifest-path .../selahcue-stt/Cargo.toml` | over-horizon config clamped at `build`/`build_with_clock`; test asserts the clamped value | test output | PENDING |
| C-009 | yes | A benign in-bounds `max_utterance_samples` passes through unclamped (positive control) | same test binary | unaffected value asserted | test output | PENDING |
| C-010 | yes | A test proves the pre-guard failure mode is real (identical/truncated recognizer output past the horizon), so the guard's target is proven not assumed | same test binary | dedicated recognizer test double demonstrates the plateau | test output | PENDING |
| C-011 | yes | The horizon constant is pinned equal to `recognizer.rs`'s real `WHISPER_AUDIO_CTX` at compile time when `whisper` is compiled in | `cargo check --manifest-path implementation/desktop/crates/selahcue-stt/Cargo.toml --features whisper` (or workspace `--features stt`) | compiles; a deliberate mismatch fails the build | build output | PENDING |
| C-012 | yes | PR #23's existing `WHISPER_AUDIO_CTX` range/alignment const-assert is untouched | `git diff` on `recognizer.rs`'s existing assert | no changes to that block | diff | PENDING |
| C-013 | yes | 86akcfpa2 is confirmed already satisfied on `main` — cited as evidence, no regression introduced | code review + existing test pass | `capture_handoff.rs` tests still pass unchanged | test output | PENDING |
| C-014 | yes | No new unbounded buffering introduced anywhere in this change | code review of all diffs | every new buffer/collection is bounded or per-call, no growth without bound | diff review notes | PENDING |
| C-015 | yes | `make ci` green on this branch | `make ci` from repo root | exit 0, all steps pass | terminal output | PENDING |
| C-016 | yes | `selahcue-stt`'s tests pass run directly (no CI job covers this crate) | `cargo test --manifest-path implementation/desktop/crates/selahcue-stt/Cargo.toml` (default features) and `--features whisper,capture` if toolchain available | exit 0 | terminal output | PENDING |
| C-017 | yes | Branch is up to date with `origin/main` immediately before requesting review | `git fetch origin main && git rev-list --count HEAD..origin/main` | 0 | terminal output | PENDING |
| C-018 | yes | Draft PR opened against `main`, not merged by this session | `gh pr view` | PR exists, `isDraft: true`, no merge | PR URL | PENDING |
| C-019 | yes | Real `gh pr checks` green (3-OS matrix), not just local `make ci` | `gh pr checks` run against the opened PR | all required checks pass or are not yet applicable per repo convention | checks output | PENDING |
| C-020 | yes | Four-reviewer gate (Cody, Vera, Sana, Quinn) run, blocking findings remediated | reviewer reports | no unresolved blocking findings | published review report artifact link | PENDING |
| C-021 | yes | Goal Contract validator green (structural + completion) | `validate_goal_contract.py` (both modes) | exit 0 both | terminal output | PENDING |

## Verification plan

- Focused verification: `cargo test --manifest-path implementation/desktop/crates/selahcue-stt/Cargo.toml`
  for engine.rs's own tests; `cargo test -p selahcue-operator --features stt` for listening.rs's
  own tests (mutation-verify the two positive-control pairs per `implementation/desktop/CLAUDE.md`'s
  bounded-memory-test discipline: break the guard, confirm RED, restore).
- Broader regression verification: `make ci` (fmt, clippy, full workspace test matrix, operator
  compile-check, headless webview check).
- Independent verifier: four-reviewer gate (Cody/Vera/Sana/Quinn) + real `gh pr checks` on the
  3-OS matrix.
- Required environment: local macOS dev machine with cmake on PATH for the native `whisper`/
  `capture` feature build (per this workspace's known PATH gap — prepend `/opt/homebrew/bin`).

## Iteration ledger

### Iteration 1

- Target criterion: C-001..C-004 (on-device hand-off cap)
- Hypothesis: deriving the on-device capacity via the existing `handoff_capacity()` function,
  mirroring `run_cloud`'s already-correct pattern, closes 86akcfp8w's remaining gap with minimal
  new surface area.
- Change or investigation: in progress
- Verifier executed: pending
- Result: pending
- New evidence: pending
- Decision: iterate

## Risks and rollback

- Risks: changing `EngineConfig.interim_interval_frames` to `interim_interval: Duration` is a
  breaking field rename across two crates (listening.rs, bounded_memory.rs) — mitigated by
  compiler-enforced exhaustiveness (any missed call site fails to compile, not a silent runtime
  gap). Clamping (vs refusing) `max_utterance_samples` is a judgement call flagged for reviewer
  sign-off. Renaming `CloudCaptureSource` → `DeviceCaptureSource` touches every test fake that
  implements it — mitigated by compiler enforcement (a missing impl fails to compile) and by
  keeping `flush_pending_backlog`'s fakes untouched (only fakes actually driving
  `run_on_device`/`run_on_device_with_recognizer` need the new methods).
- Rollback or recovery: single feature branch, not merged by this session; `git revert` or drop
  the branch if a reviewer finds a fundamental issue. No production data or migrations involved.

## Pause and escalation conditions

- A rebase conflict against `origin/main` that requires a judgement call this role is not
  equipped to make.
- A four-reviewer finding that contradicts this contract's ASSUMED clamp-vs-refuse decision.
- CI failure that cannot be attributed to this branch's own changes (check `ci-red` issue state
  first, per repo CLAUDE.md).

## Final evaluation

- Validator command: pending
- Validator result: pending
- Independent verification result: pending
- Terminal state: pending
- Remaining failed or blocked criteria: pending
- ClickUp final evidence comment: pending
