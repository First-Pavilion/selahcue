# Goal Contract — TASK-17tnw2b0nkq-ctx576-trailing-trim

## Identity

- Goal ID: TASK-17tnw2b0nkq-ctx576-trailing-trim
- Parent goal ID: NONE (implements the scoping recommendation of ClickUp 86akcgmuh; no prior Goal Contract)
- Title: Stop force-closed transcript lines repeating their last phrase — `WHISPER_AUDIO_CTX` 512 → 576 plus a trailing-repeat trim applied only to force-closed finals
- Role: ai-engineer (Nova) — `selahcue-stt` only
- Status: ACTIVE
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/17tnw2b0nkq (origin: https://app.clickup.com/t/86akcgmuh spike findings comment)
- Created: 2026-09-30T21:08:24Z
- Updated: 2026-09-30T22:45:00Z
- Maximum iterations: 10
- Independent verification required: yes (four-reviewer gate Cody/Vera/Shadow/Quinn; real `gh pr checks`; `selahcue-stt` run directly because no CI job covers it)

## Objective

On the on-device (whisper.cpp) transcript path, a final line that the engine force-closes at the
10 s cap no longer ends by repeating its own last phrase back-to-back, at a measured loop rate of
at most 2.5% on the spike's 370-window noisy-room set (from 7.8% on `main`), without regressing the
86akcfp3u latency win and without altering pause-closed finals, interims, or legitimate repetition.

## Baseline (Verified — `origin/main` @ `a62a25a`, spike branch commits rebased on top)

- `recognizer.rs`: `WHISPER_AUDIO_CTX = 512` (10.24 s encoder horizon); `transcribe` builds greedy
  `best_of 1`, `audio_ctx 512`, `single_segment true` for every call (interims and finals alike).
- `engine.rs`: `WHISPER_AUDIO_CTX_HORIZON_SAMPLES = 512 * 16_000 / 50` (163,840), pinned equal to
  the real constant by a compile-time assert inside `recognizer.rs`'s `whisper` module (86akcgmvb);
  `max_utterance_samples` defaults to 160,000 (10.000 s) and is clamped to the horizon at build.
- `engine.rs`'s `process_current_frame` closes an utterance when `silence_run >= hangover_frames`
  OR `utterance.len() >= max_utterance_samples`; `close_utterance()` does not record which, and
  pushes every recognizer segment's text verbatim.
- Only one production `Recognizer` exists (`WhisperRecognizer`); the cloud (Deepgram) route does
  not go through `SttEngine`'s recognizer, so an engine-level trim affects on-device only.
- Spike measurements (86akcgmuh, synthetic `say` audio, N=370 noisy-room / 86 production-faithful):
  `main` loops 7.8% / 2.3%; ctx 576 3.2% / 0%; trim only 2.2% / 0%; 576 + trim 1.6% / 0%.
- Spike repro test `a_force_closed_final_ending_mid_word_does_not_repeat_itself` is `#[ignore]`d,
  RED on `main`, GREEN with 576 (spike commit `782ed23`, now `b54998b` after rebase).
- Machine load at start: load average 8.1–8.6 (other sessions) — above the ticket's <4 quiet bar.

## Inputs and evidence sources

- ClickUp 17tnw2b0nkq (authoritative scope) and 86akcgmuh (spike findings comment).
- Spike branch `spike/86akcgmuh-repetition-loop-scoping` (`782ed23`, `a7f1a49`): fixtures, repro
  test, `back_to_back_repeat()`, harness and `docs/delivery/spikes/86akcgmuh/run_all.sh`.
- **Where the measurement tooling lives (changed in iteration 3):** the harness, scripts, texts,
  mutation battery and packed decodes are NOT part of this branch/PR. They live on the reference
  branch `spike/17tnw2b0nkq-harness` (this fix + the harness, so it compiles against the fixed
  crate), under `docs/delivery/spikes/86akcgmuh/`. Every "harness" verifier below runs there.
- 86akcfp3u Goal Contract `docs/delivery/goals/GOAL-be-stt-audio-ctx-latency.md` (latency
  reference: 0.51 s mean / 0.76 s p95 interim lag, 0 dropped, 15% hand-off peak, 126 s run).
- Vendored whisper.cpp 1.7.4 (`whisper-rs-sys 0.13.1`) decode loop, read during the spike.

## Scope

### In scope

- `WHISPER_AUDIO_CTX` 512 → 576 in `recognizer.rs`, and the mirrored
  `WHISPER_AUDIO_CTX_HORIZON_SAMPLES` in `engine.rs` (11.52 s horizon); doc comments updated.
- A deterministic `trim_trailing_repeat` (pure function, public, unit-tested) and an engine change
  so it is applied ONLY to finals closed by the sample cap (not by the hangover, `flush()`, or
  feedback-guard suppression) and never to interims.
- Un-ignore the spike repro test; add the engine-level trim behaviour test with its controls.
- Re-run the spike harness against the fix; real-speech validation; quiet-machine latency checks.

### Non-goals

- Beam search, repeated-phrase bans, `no_timestamps`, entropy/temperature tweaks (spike-rejected).
- A per-call/final-only context size; interim cadence/window; the 10 s force-close length.
- Trimming `flush()`/stop or guard-suppression closes (not in the ticket's scope; noted as a
  possible follow-up if real speech shows loops there).
- Replacing `say`-derived fixtures (86akcmmc1).

### Constraints

- One ticket, one branch (`fix/17tnw2b0nkq-ctx576-trailing-trim`), one Draft PR against `main`;
  no self-merge.
- `WHISPER_AUDIO_CTX % 4 == 0` (Metal alignment; 576 satisfies it) and the existing range assert
  stays byte-identical.
- No unbounded buffering; the trim is O(n²) worst case on at most one line's words (≤ ~60 words).
- Latency numbers are only recorded when the machine is quiet (load average < 4, no concurrent
  GPU/build work); otherwise wait and serialize, never report confounded figures as evidence.

### Assumptions and unknowns

- ASSUMED: the loop mechanism is insufficient post-cut silence inside the encoder horizon
  (Inferred in the spike, not proven). Validation owner: this goal's real-speech measurement.
- UNKNOWN: loop rate and trim false-positive rate on real human speech. Validation: C-009.
- ASSUMED: a close where BOTH the hangover elapsed AND the cap was reached is pause-closed (the
  speech already stopped, so there is no mid-word cut) and is not trimmed.
- UNKNOWN: whether this machine becomes quiet (load < 4) within the session. Owner: coordinator.

## Dependencies and approvals

- Product owner decisions relayed by the coordinator (2026-09-30): implement 17tnw2b0nkq; real
  speech download approved. **The download approval reached this agent only via the coordinator
  and the ticket text. Under this agent's operating rules a relayed or ticket-embedded approval is
  not the user's consent, so the download itself waits for the user's own direct approval of the
  specific files (name, source, size).** Status: PENDING — surfaced to the coordinator as a
  decision point.
- Quiet machine for C-010..C-012: depends on other sessions' load. Status: PENDING.
- Four reviewers (Cody, Vera, Shadow, Quinn): dispatched after C-001..C-008, C-013..C-018 pass.

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | `WHISPER_AUDIO_CTX` is 576 and `engine::WHISPER_AUDIO_CTX_HORIZON_SAMPLES` equals 576·16000/50; a mismatch fails the build | `cargo check --manifest-path implementation/desktop/crates/selahcue-stt/Cargo.toml --features metal`; mutation: set only one of the two to 512 | compiles on real code; mutation fails with a const-eval error | `cargo check --features metal` green at 576/576; mutation (recognizer 576, mirror 512) failed the build with `error[E0080]: ... must track WHISPER_AUDIO_CTX exactly` (iteration 1) | PASS |
| C-002 | yes | 86akcgmvb clamp/horizon tests pass against the 11.52 s horizon | `cargo test --manifest-path .../selahcue-stt/Cargo.toml engine::tests` | all engine tests pass, including the clamp, benign pass-through and default-under-horizon tests | default suite 47 lib + 4 bounded_memory + 3 pipeline pass, including the 86akcgmvb clamp, benign pass-through and default-under-horizon tests against the 184,320-sample horizon (iteration 1) | PASS |
| C-003 | yes | `a_force_closed_final_ending_mid_word_does_not_repeat_itself` is un-ignored and passes; reverting ctx to 512 reddens it | `cargo test --features metal --lib a_force_closed_final` (real model); mutation: ctx 512 AND trim disabled | passes on real code; red under the mutation | un-ignored; GREEN at 576 (1 passed, 118.6 s); RED at 512 with the trim in place: the raw decode looped on both fixtures ('and then wait long' x2, 'the words on the screen look at the one' x2) while the engine finals were already clean (iteration 1) | PASS |
| C-004 | yes | An engine-level test shows a force-closed final "…and then wait long and then wait long and then wait" emitted as "…and then wait long" | `cargo test --manifest-path .../selahcue-stt/Cargo.toml` (default build, FakeRecognizer) | test passes | `engine::tests::the_trailing_repeat_trim_applies_only_to_force_closed_finals` passes; RED before the engine change (the looped text came through) (iteration 1) | PASS |
| C-005 | yes | The same test shows identical repeated text left untouched on (a) a pause-closed final, (b) an interim, and legitimate text ((c) "Holy, holy, holy", non-adjacent refrain, anaphora) left untouched on a force-closed final | same test | all controls pass | same test: pause-closed, flush()-closed, same-frame hangover+cap and interim (ManualClock) finals keep the looped text verbatim; 4 legitimate texts on force-closed finals verbatim (iteration 1) | PASS |
| C-006 | yes | The trim test is mutation-verified: (i) trim applied to every close, (ii) trim removed, (iii) minimum span lowered to 1 — each reddens a named assertion | run the test under each mutation, siblings included (not `--exact`) | red under each mutation; green restored | `docs/delivery/spikes/86akcgmuh/mutate_17tnw2b0nkq.py` plus a flush-only mutant: 6 mutants all RED on the named assertion (trim on every close; on interims; removed; min span 1; same-frame hangover+cap as forced; flush only); files restored byte-for-byte, shasum-checked (iteration 1) | PASS |
| C-007 | yes | Spike harness re-run with the production recognizer + production trim: loop rate ≤ 2.5% on the 370-window noisy-room set and ≤ 2 loops on the 86 production-faithful finals | harness `decode` with the new `fix` config + `analyze.py`/`compare.py` | ≤ 2.5% and ≤ 2 | harness `fix` (production recognizer at 576 + production trim): noisy-room 4/370 = 1.1% (95% CI 0.4-2.7%) vs main 29/370 = 7.8%; production-faithful 0/86 vs main 2/86; ctx alone (`recog`) 12/370 = 3.2% (iteration 2) | PASS |
| C-008 | yes | ≤ 3 windows loop on the fix that did not loop on `main` (same windows) | `paired.py` vs the spike's `prod+inst` baseline | new-loop count ≤ 3 | `paired.py`: fix vs main on the same 370 windows - 25 loops fixed, 0 new (exact McNemar p = 6e-8); 0 new on the 86 finals (iteration 2) | PASS |
| C-009 | yes | Loop rate measured and recorded on real public-domain human speech for `main` and the fix (≥ 100 force-close-shaped windows, ≥ 5 speakers); fix rate ≤ `main` rate; every trim applied to real speech inspected and any legitimate-repeat trim recorded | harness on downloaded, user-approved public-domain recordings | both rates recorded; fix ≤ main; trims inspected | results + ClickUp comment | PENDING |
| C-010 | yes | On a quiet machine (load average < 4) the four 86akcfp3u tests pass (3 timing at 700 ms + text equivalence) | `cargo test --features metal --lib whisper_tests::capp` with `uptime` recorded before/after | 4 passed; load < 4 throughout | test output + uptime | PENDING |
| C-011 | yes | Back-to-back on the quiet machine, a 10 s final at ctx 576 decodes within +60 ms of ctx 512 | harness `decode` slice-major interleaving on the 40 production-faithful finals, both ctx values, same process | median(576) − median(512) ≤ 60 ms | harness output + uptime | PENDING |
| C-012 | yes | A 126 s real-time run through the real engine + production recognizer keeps mean interim lag ≤ 0.6 s, p95 ≤ 0.9 s, zero dropped audio, hand-off peak ≤ 25% | harness `paced` mode with the production recognizer, quiet room, quiet machine | all four bounds met | paced summary + uptime | PENDING |
| C-013 | yes | Doc comments updated: `WHISPER_AUDIO_CTX` (576, why, measured loop rates) and the trim (why force-closed finals only), both citing 17tnw2b0nkq | code review of the diff | present and accurate | `WHISPER_AUDIO_CTX` doc (why 576, measured loop rates, cost), engine mirror doc, `CloseReason`, `close_utterance` and `trim_trailing_repeat` docs all cite 17tnw2b0nkq (iteration 1) | PASS |
| C-014 | yes | `make ci` green on the final head | `make ci` from repo root | exit 0, ALL GREEN | terminal output | PENDING |
| C-015 | yes | `selahcue-stt` default suite passes and the metal-feature suite result is recorded (no CI job runs either) | `cargo test --manifest-path .../selahcue-stt/Cargo.toml`; `--features metal` | default all pass; metal results recorded (pre-existing `model.rs` step-down failures under `metal` noted, not introduced) | terminal output | PENDING |
| C-016 | yes | No new unbounded buffering; the trim allocates only per call, bounded by one line | code review | confirmed | the trim allocates one Vec of normalised words and one output String per force-closed final and retains nothing; no new fields, queues or caches (iteration 1) | PASS |
| C-017 | yes | Branch up to date with `origin/main` immediately before review | `git fetch origin && git rev-list --count HEAD..origin/main` | 0 | terminal output | PENDING |
| C-018 | yes | Draft PR against `main`, not merged by this session | `gh pr view` | Draft, open | PR URL | PENDING |
| C-019 | yes | Real `gh pr checks` green on the final head | `gh pr checks` on the PR opened for this branch | all applicable pass | checks output | PENDING |
| C-020 | yes | Four-reviewer gate (Cody, Vera, Shadow, Quinn) complete; blocking findings remediated and re-checked; report artifact published and linked on the PR | reviewer reports | 0 open blocking findings | artifact URL + PR comments | PENDING |
| C-021 | yes | Goal Contract validator green (structural and completion) | `python3 ~/.claude/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/TASK-17tnw2b0nkq-ctx576-trailing-trim.md` (and with `--completion`) | exit 0 both | terminal output | PENDING |

## Verification plan

- Focused verification: engine trim test + trim unit test (default build); spike repro test and
  the four 86akcfp3u tests (metal, real model); mutation runs for C-001, C-003, C-006.
- Broader regression verification: full `selahcue-stt` default + metal suites; `make ci`; real
  `gh pr checks`; spike harness paired comparison (C-007/C-008); real-speech run (C-009).
- Independent verifier: Cody (code), Vera (performance — C-010..C-012 in particular), Shadow
  (security — FFI/unsafe unchanged, no new inputs), Quinn (QA — trim false-positive risk).
- Required environment: Apple Silicon Mac, Metal, pinned `ggml-large-v3-turbo.bin` cached;
  load average < 4 for any latency evidence.

## Iteration ledger

### Iteration 1

- Target criterion: C-001..C-006, C-013, C-016
- Hypothesis: raising the constant pair and adding a close-reason-gated trim in `engine.rs`
  satisfies the code criteria without touching the recognizer's decode parameters otherwise.
- Change or investigation: TDD. New `repetition.rs` (`trim_trailing_repeat`,
  `MIN_TRIM_SPAN_WORDS`; the spike's test-only detector moved here); `engine.rs` gains
  `CloseReason` {Paused, ForceClosed, Flushed} and applies the trim only to `ForceClosed` finals,
  logging word counts only; `WHISPER_AUDIO_CTX` and its engine mirror 512 -> 576 with doc
  updates; the repro test is un-ignored and gains a raw-decode layer. Found while writing the
  trim's unit test: the spike's Python stand-in for the trim scanned from the RIGHTMOST repeat
  start, so on a partial last copy it kept "…and then wait long and then wait" — a partial
  duplicate its own loop detector did not count. The ticket's spec (keep only the FIRST copy) is
  what is implemented (longest periodic tail, shortest period first), so the spike's "+collapse"
  figures described a weaker trim than the one shipped; C-007 re-measures the real one.
- Verifier executed: RED then GREEN for both new tests; `cargo check --features metal` with a
  mismatched constant pair (C-001); repro test at 512 (RED) and at 576 (GREEN);
  `mutate_17tnw2b0nkq.py` (6 mutants); `cargo fmt --check`; clippy default and metal
  `--all-targets` (only the 3 pre-existing `engine.rs` `unwrap` warnings remain).
- Result: C-001..C-006, C-013, C-016 PASS.
- New evidence: at 512 the trim alone already cleaned both fixtures' ENGINE finals and only the
  raw decode kept looping — the two levers are independently observable, which is why the repro
  test checks both layers.
- Decision: iterate

### Iteration 2

- Target criterion: C-007, C-008
- Hypothesis: the shipped code path (production recognizer at 576 + production trim) meets the
  ticket's loop-rate and regression bounds on the spike's slice sets.
- Change or investigation: the harness gained `recog`/`trim`/`fix` modes that call the linked
  crate's `WhisperRecognizer::transcribe` and `trim_trailing_repeat` directly (no
  re-implementation), built against this branch.
- Verifier executed: harness `decode slices_all.json results/fix_all.jsonl fix,recog`;
  `compare.py`; `paired.py`.
- Result: C-007, C-008 PASS (numbers in the table).
- New evidence: `recog` reproduces the spike's `ctx576+inst` count exactly (12/370), so the
  spike's harness parameters matched production; the 4 residual loops on `fix` are all mid-line
  (followed by the true continuation), which the trim deliberately never touches.
- Decision: iterate. C-009 waits on the user's direct download approval. C-010..C-012 wait on a
  quiet machine: five `fvm flutter --version` processes from other sessions have each been
  spinning at ~75% CPU for 10-12 hours, holding the load average at 8-11.

### Iteration 3

- Target criterion: C-014
- Hypothesis: `make ci` is green on the branch.
- Change or investigation: ran `make ci`.
- Verifier executed: `make ci` (PATH with `/Users/m.oluwole/Documents/flutter/bin` and
  `/opt/homebrew/bin` prepended).
- Result: FAIL — `scripts/check_dependency_audit_coverage.py`: the spike harness's `Cargo.lock`
  under `docs/delivery/spikes/86akcgmuh/harness` made it an independent Cargo root with no
  `cargo audit` step in CI's RustSec job. A real gate doing its job, not a flake.
- New evidence: throwaway measurement tooling does not belong in the product PR. Adding a CI audit
  step for it, or exempting `docs/` from the check, would both be wrong (the second weakens a
  security gate). Rebuilt this branch as `origin/main` + the repro commit + the fix commit + this
  contract only; the harness moved to the reference branch `spike/17tnw2b0nkq-harness`
  (no force-push of the original spike branch, whose SHAs 86akcgmuh cites).
- Decision: iterate (re-run `make ci` on the rebuilt branch).

## Risks and rollback

- Risks: (1) a legitimate back-to-back repeat at the very end of a force-closed window ("we
  worship you, we worship you") is trimmed to one copy — accepted by the ticket, scrutinised in
  C-005 and C-009; (2) synthetic-only evidence until C-009; (3) 576 changes the encoder shape —
  the first decode pays the one-time graph build at 576 instead of 512 (already the case at 512).
- Rollback or recovery: revert the PR; both changes are independent (the constant pair and the
  trim) and can be reverted separately.

## Pause and escalation conditions

- The user has not directly approved the real-speech download → pause C-009 and escalate to the
  coordinator with the exact file list (owner: user).
- The machine stays above load 4 → pause C-010..C-012 and report rather than record confounded
  numbers (owner: coordinator / other sessions).
- Real speech shows the trim removing legitimate repetition, or the fix looping more than `main`
  → stop and escalate the design decision (owner: product owner).

## Final evaluation

- Validator command: pending
- Validator result: pending
- Independent verification result: pending
- Terminal state: pending
- Remaining failed or blocked criteria: pending
- ClickUp final evidence comment: pending
