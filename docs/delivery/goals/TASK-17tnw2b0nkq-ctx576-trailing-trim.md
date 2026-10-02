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
- Updated: 2026-10-02T14:00:00Z
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
| C-002 | yes | 86akcgmvb clamp/horizon tests pass against the 11.52 s horizon | `cargo test --manifest-path .../selahcue-stt/Cargo.toml engine::tests` | all engine tests pass, including the clamp, benign pass-through and default-under-horizon tests | default suite passes, including the 86akcgmvb clamp, benign pass-through and default-under-horizon tests against the 184,320-sample horizon: 47 lib + 4 bounded_memory + 3 pipeline in iteration 1, 57 + 4 + 3 in iteration 5, and 60 lib + 4 bounded_memory + 3 pipeline on the iteration 6 code after merging `origin/main` (b0a418d) - 3 new lib tests since iteration 5 | PASS |
| C-003 | yes | `a_force_closed_final_ending_mid_word_does_not_repeat_itself` is un-ignored and passes; reverting ctx to 512 reddens it | `cargo test --features metal --lib a_force_closed_final` (real model); mutation: ctx 512 AND trim disabled | passes on real code; red under the mutation | un-ignored; GREEN at 576 (1 passed, 118.6 s); RED at 512 with the trim in place: the raw decode looped on both fixtures ('and then wait long' x2, 'the words on the screen look at the one' x2) while the engine finals were already clean (iteration 1) | PASS |
| C-004 | yes | An engine-level test shows a force-closed final "…and then wait long and then wait long and then wait" emitted as "…and then wait long" | `cargo test --manifest-path .../selahcue-stt/Cargo.toml` (default build, FakeRecognizer) | test passes | `engine::tests::the_trailing_repeat_trim_applies_only_to_force_closed_finals` passes; RED before the engine change (the looped text came through) (iteration 1) | PASS |
| C-005 | yes | The same test shows identical repeated text left untouched on (a) a pause-closed final, (b) an interim, and legitimate text ((c) "Holy, holy, holy", non-adjacent refrain, anaphora) left untouched on a force-closed final | same test | all controls pass | same test: pause-closed, flush()-closed, same-frame hangover+cap and interim (ManualClock) finals keep the looped text verbatim; 4 legitimate texts on force-closed finals verbatim (iteration 1) | PASS |
| C-006 | yes | The trim test is mutation-verified: (i) trim applied to every close, (ii) trim removed, (iii) minimum span lowered to 1 — each reddens a named assertion | run the test under each mutation, siblings included (not `--exact`) | red under each mutation; green restored | `docs/delivery/spikes/86akcgmuh/mutate_17tnw2b0nkq.py` plus a flush-only mutant: 6 mutants all RED on the named assertion (trim on every close; on interims; removed; min span 1; same-frame hangover+cap as forced; flush only); files restored byte-for-byte, shasum-checked (iteration 1). Iteration 6 added a 7th, for the feedback-guard suppression close: passing `CloseReason::ForceClosed` at that call site in `process` turned only `engine::tests::a_feedback_guard_suppression_close_is_never_trimmed` RED (the whole lib suite was run, siblings included, and restored with `git checkout`) | PASS |
| C-007 | yes | Spike harness re-run with the production recognizer + production trim: loop rate ≤ 2.5% on the 370-window noisy-room set and ≤ 2 loops on the 86 production-faithful finals | harness `decode` with the new `fix` config + `analyze.py`/`compare.py` | ≤ 2.5% and ≤ 2 | harness `fix` (production recognizer at 576 + production trim): noisy-room 4/370 = 1.1% (95% CI 0.4-2.7%) vs main 29/370 = 7.8%; production-faithful 0/86 vs main 2/86; ctx alone (`recog`) 12/370 = 3.2% (iteration 2) | PASS |
| C-008 | yes | ≤ 3 windows loop on the fix that did not loop on `main` (same windows) | `paired.py` vs the spike's `prod+inst` baseline | new-loop count ≤ 3 | `paired.py`: fix vs main on the same 370 windows - 25 loops fixed, 0 new (exact McNemar p = 6e-8); 0 new on the 86 finals (iteration 2) | PASS |
| C-009 | yes | Loop rate measured and recorded on real public-domain human speech for `main` and the fix (≥ 100 force-close-shaped windows, ≥ 5 speakers); fix rate ≤ `main` rate; every trim applied to real speech inspected and any legitimate-repeat trim recorded | harness on downloaded, user-approved public-domain recordings | both rates recorded; fix ≤ main; trims inspected | pipeline ready (`real_speech.py` on `spike/17tnw2b0nkq-harness`); download of the 6 LibriVox MP3s (Spurgeon's Sermons May 1858, 124,468,586 bytes, 6 readers) awaits the user's own direct approval - relayed approval is not accepted as consent | BLOCKED |
| C-010 | yes | On a quiet machine (load average < 4) the four 86akcfp3u tests pass (3 timing at 700 ms + text equivalence) | `cargo test --features metal --lib whisper_tests::capp` with `uptime` recorded before/after | 4 passed; load < 4 throughout | load average 8-24 all session; five `fvm flutter --version`/`flutter test` processes from other sessions at ~96% CPU each for 11-13 h (PIDs 11887, 98402, 73989, 73885, 73640) put a ~5-core floor under the load, so < 4 is unreachable while they run. It is also unreachable from the iteration 6 environment (Linux container: no Metal, no cached model), whatever the load | BLOCKED |
| C-011 | yes | Back-to-back on the quiet machine, a 10 s final at ctx 576 decodes within +60 ms of ctx 512 | harness `decode` slice-major interleaving on the 40 production-faithful finals, both ctx values, same process | median(576) − median(512) ≤ 60 ms | same quiet-machine blocker as C-010 | BLOCKED |
| C-012 | yes | A 126 s real-time run through the real engine + production recognizer keeps mean interim lag ≤ 0.6 s, p95 ≤ 0.9 s, zero dropped audio, hand-off peak ≤ 25% | harness `paced` mode with the production recognizer, quiet room, quiet machine | all four bounds met | same quiet-machine blocker as C-010 | BLOCKED |
| C-013 | yes | Doc comments updated: `WHISPER_AUDIO_CTX` (576, why, measured loop rates) and the trim (why force-closed finals only), both citing 17tnw2b0nkq | code review of the diff | present and accurate | `WHISPER_AUDIO_CTX` doc (why 576, measured loop rates, cost), engine mirror doc, `CloseReason`, `close_utterance` and `trim_trailing_repeat` docs all cite 17tnw2b0nkq (iteration 1). Iteration 6 corrected two overstatements, with no behaviour change: "while the speaker was still talking" now reads as the engine's real condition `capped && silence_run < hangover_frames` (the trailing run can hold up to `hangover_frames - 1` silent frames) in `CloseReason`, `close_utterance` and the `process_current_frame` comment, and the trim's cost note now lists its real allocations; the trim's doc also states the one- and two-word-loop limits and the accepted doubled-refrain false positive | PASS |
| C-014 | yes | `make ci` green on the final head | `make ci` from repo root | exit 0, ALL GREEN | Was PASS on `21571cb` (`== local Rust/Flutter gate: ALL GREEN ==`, exit 0, iteration 4), but that commit is no longer on the branch (history was rewritten) and the PR review of 2026-10-02 flagged the evidence as unverifiable for the current head; iterations 5 and 6 changed `selahcue-stt` and this contract only and did NOT re-run `make ci`, so this is back to PENDING until it is re-run on the final head. It cannot be re-run in the iteration 6 environment (Linux container: no Flutter/fvm, no Playwright WebKit), so it needs a machine that has them. GitHub CI on the final head (see C-019) is the substitute evidence for the jobs it covers; it is NOT this criterion and does not close it | PENDING |
| C-015 | yes | `selahcue-stt` default suite passes and the metal-feature suite result is recorded (no CI job runs either) | `cargo test --manifest-path .../selahcue-stt/Cargo.toml`; `--features metal` | default all pass; metal results recorded (pre-existing `model.rs` step-down failures under `metal` noted, not introduced) | iteration 6, run by hand on the iteration 6 code after merging `origin/main` (b0a418d, which brought the whisper-rs 0.16 / cpal 0.18 / ureq 3 migration of this crate): default features 60 lib + 4 bounded_memory + 3 pipeline pass; `cargo fmt --check` clean; `cargo clippy -- -D warnings` clean on the lib, with default features and with `--features whisper`; `cargo check --features whisper --tests` (CPU) clean; `--all-targets` without `-D warnings` shows only the 3 pre-existing `engine.rs` test `unwrap` warnings (they are errors under `-D warnings`). NOT done: the `metal` suite and every `whisper_tests` test (they compile but were never run - Linux host, no Metal, no cached model), so the row's `metal` result is unrecorded and the row stays PENDING | PENDING |
| C-016 | yes | No new unbounded buffering; the trim allocates only per call, bounded by one line | code review | confirmed | per call the trim allocates a `Vec<&str>` of the line's tokens, a `Vec<(usize, String)>` with one `String` per word, two transient `String`s per token inside `normalize_word` (the filtered characters and their lower-cased copy), and the output `String` when a repeat is found; all are bounded by the one segment passed in, freed on return, and nothing is retained; no new fields, queues or caches (iteration 1; wording corrected in iteration 6, the code is unchanged) | PASS |
| C-017 | yes | Branch up to date with `origin/main` immediately before review | `git fetch origin && git rev-list --count HEAD..origin/main` | 0 | `git fetch origin` then `git rev-list --count HEAD..origin/main` = 0 and `origin/main` is an ancestor of HEAD, immediately before push (iteration 4); `origin/main` (`feaee70`) merged again in iteration 5 (merge commit, no conflicts); iteration 6: `origin/main` @ `b0a418d` merged (94 commits, merge commit `e0d215e`, no conflicts) and `git rev-list --count HEAD..origin/main` = 0 immediately before the iteration 6 push. `main` keeps moving, so this is true for that push only | PASS |
| C-018 | yes | Draft PR against `main`, not merged by this session | `gh pr view` | Draft, open | Draft PR https://github.com/First-Pavilion/selahcue/pull/128 against `main`, open, not merged (iteration 4) | PASS |
| C-019 | yes | Real `gh pr checks` green on the final head | `gh pr checks` on the PR opened for this branch | all applicable pass | checks output | PENDING |
| C-020 | yes | Four-reviewer gate (Cody, Vera, Shadow, Quinn) complete; blocking findings remediated and re-checked; report artifact published and linked on the PR | reviewer reports | 0 open blocking findings | artifact URL + PR comments | PENDING |
| C-021 | yes | Goal Contract validator green (structural and completion) | `python3 ~/.claude/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/TASK-17tnw2b0nkq-ctx576-trailing-trim.md` (and with `--completion`) | exit 0 both | terminal output | PENDING |
| C-022 | yes | The trim's word normalisation keeps non-ASCII letters and treats NFC and NFD spellings of a word as equal, and punctuation-only tokens are never counted as matches (PR #128 review, 2026-10-02) | `cargo test --manifest-path .../selahcue-stt/Cargo.toml` (default build); mutation battery on `repetition.rs` | the review's `"ọlọ ẹlẹ ọlọ ẹlẹ ọlọ ẹlẹ"` is left alone; Yoruba, accented-Latin, NFC/NFD, tone-only and punctuation-only cases pass; each test reddens under its named mutant; English cases unchanged | 9 new `repetition::tests` + `engine::tests::the_trailing_repeat_trim_does_not_mistake_distinct_non_ascii_words_for_a_loop`; 10 mutants of the new code (ASCII-only filter, marks dropped, no composition, empties kept, lone apostrophe, mark range, table row, no lower-casing, cut position) all RED on named tests, plus a full revert of `normalize_word`/empty handling RED on 9 tests (iteration 5) | PASS |

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

### Iteration 4

- Target criterion: C-014, C-017, C-018, C-019
- Hypothesis: with the harness off the branch, `make ci` is green and the branch can be opened as a Draft PR.
- Change or investigation: none to code; re-ran the gate on the rebuilt branch (now on `origin/main` @ `d46d6d5`).
- Verifier executed: `make ci`; `git fetch` + `git rev-list --count HEAD..origin/main`; `gh pr create --draft`; `gh pr checks 128`.
- Result: C-014, C-017, C-018 PASS; C-019 pending the CI run on the final head. C-009 BLOCKED (user's direct download approval), C-010..C-012 BLOCKED (quiet machine). ClickUp writes are also blocked for ~11.5 h: the ClickUp MCP daily limit (1,000 calls) was reached, so ClickUp updates are carried in the handback instead.
- New evidence: none beyond the gate results.
- Decision: blocked - hand back to the coordinator with the two user decisions and the reviewer-gate brokering request.

### Iteration 5

- Target criterion: C-022 (new, from the PR #128 review of 2026-10-02); C-014, C-015, C-017 evidence corrected
- Hypothesis: the trim's `normalize_word` kept only ASCII alphanumerics, so non-ASCII letters were deleted and distinct words (Yoruba "ọlọ"/"ẹlẹ", accent-only variants) collapsed to the same token, and every punctuation-only token normalised to the same empty string; fixing the normalisation fixes both.
- Change or investigation: `normalize_word` now keeps `char::is_alphanumeric` letters and digits of every script, apostrophes and combining diacritical marks, lower-cases, and returns an empty string for a token with no letter or digit. Canonical equivalence without a new dependency: a 33-row table (`COMPOSED`: Latin-1 accented lower-case letters plus the Yoruba letters ẹ ọ ṣ ń ǹ ḿ) composes base + mark pairs so NFC and NFD spellings of those letters compare equal; anything outside it is compared as written (a missed trim, never a false one). Full coverage needs a normalisation crate, left as an owner decision. Punctuation-only tokens are dropped by one shared tokenizer (`indexed_words`) that both `trim_trailing_repeat` and the test-only `normalized_words`/`back_to_back_repeat` detector consume, so they are never matches and never breaks, and the trimmed text ends at the last word of the first copy. Doc comments added on `close_utterance` and at `set_single_segment(true)` recording that the force-close trim assumes one segment per utterance (the review's latent trap); no behaviour change there.
- Verifier executed: new default-build tests (RED against the original normalisation, GREEN after); mutation battery (see C-022); `cargo test` default features, `cargo fmt --check`, `cargo clippy` on `selahcue-stt`, with `origin/main` merged. `make ci`, the `metal`/`whisper` suites and the real-model repro test were NOT run.
- Result: C-022 PASS. C-014 returned to PENDING (its evidence commit is gone from the branch). C-009, C-010..C-012 and C-020 are unchanged and still open.
- New evidence: none on real speech. Behaviour change worth knowing: a lone apostrophe token and a bare dash are no longer words, so a loop whose copies are separated by a dash token is still trimmed to its first copy but no longer keeps the separator dangling at the end of the line (before, the kept text ended with the dash).
- Decision: iterate (C-009 and the quiet-machine criteria still need the owner)

### Iteration 6

- Target criterion: review follow-up on PR #128 (independent code review of head `f74dd01`: no MUST FIX, one SHOULD FIX, cheap NITs); evidence corrected on C-002, C-006, C-013, C-014, C-015, C-016, C-017; C-019 recorded from the final head's CI
- Hypothesis: the reviewer's surviving mutant M17 (the period loop reversed to `for n in (MIN_TRIM_SPAN_WORDS..=m / 2).rev()`, 57/57 green) shows that "the shortest period's first copy is kept" was untested, and several comments and this contract overstate what the code does. Closing both needs tests and wording only, with no behaviour change.
- Change or investigation: merged `origin/main` (`b0a418d`, 94 commits, no conflicts; it carries this crate's whisper-rs 0.16 / cpal 0.18 / ureq 3 migration). Added three default-build tests: `repetition::tests::trim_keeps_the_shortest_period_when_the_span_repeats_four_or_more_times` (4 copies of a 4-word span, a partial last copy, a lead-in, a real phrase, and a span with a proper sub-period), `repetition::tests::the_documented_short_span_limitations_hold`, and `engine::tests::a_feedback_guard_suppression_close_is_never_trimmed`. Documentation only: the trim's cost note now lists the real allocations; its doc states the one- and two-word-loop limits and the accepted doubled-refrain false positive; "while the speaker was still talking" is replaced by the engine's real condition (`capped && silence_run < hangover_frames`) in `CloseReason`, `close_utterance` and the `process_current_frame` comment. No algorithm, constant or dependency changed.
- Verifier executed: on the merged tree, `cargo test --manifest-path .../selahcue-stt/Cargo.toml` (default features) 60 lib + 4 bounded_memory + 3 pipeline pass (57 + 4 + 3 before the new tests), `cargo fmt --check`, `cargo clippy -- -D warnings` (default and `--features whisper`), `cargo check --features whisper --tests`; mutation M17 on the whole lib suite: RED on `repetition::tests::trim_keeps_the_shortest_period_when_the_span_repeats_four_or_more_times` (left `Some("x y z w x y z w")`, right `Some("x y z w")`) and on `the_documented_short_span_limitations_hold`, restored and green; suppression-close mutant (`CloseReason::ForceClosed` at the suppression call site): RED on `engine::tests::a_feedback_guard_suppression_close_is_never_trimmed` only, restored and green.
- Result: the SHOULD FIX and the cheap NITs are closed; C-019 is recorded in the next commit, from the GitHub CI run on this one. NOT run: `make ci` (C-014), the `metal` suite, the `whisper_tests` and the real-model repro test (C-003 and C-015 evidence is from iteration 1 and the older head), real speech (C-009), the quiet-machine checks (C-010..C-012). The loop-rate figures in C-007/C-008 were measured on iteration 1's trim (ASCII-only `normalize_word`, harness head `298d036`) and were not re-measured after `37fad26`.
- New evidence: none on real speech or on latency.
- Open owner decisions, deliberately not taken here: add a Unicode-normalisation crate for full NFC/NFD coverage (a dependency decision), and restrict the trim to the LAST segment of a force-closed utterance (today the trim relies on the recognizer's `single_segment`).
- Decision: iterate (C-009 needs the owner's direct approval of the download; C-010..C-012 need Apple Silicon/Metal, a cached model and a quiet machine; C-014 needs a machine with Flutter and WebKit; C-020 the four-reviewer gate)

## Risks and rollback

- Risks: (1) a legitimate back-to-back repeat at the very end of a force-closed window ("we
  worship you, we worship you") is trimmed to one copy — accepted by the ticket, scrutinised in
  C-005 and C-009; (2) synthetic-only evidence until C-009; (3) 576 changes the encoder shape —
  the first decode pays the one-time graph build at 576 instead of 512 (already the case at 512);
  (4) one- and two-word loops are only partly handled (`MIN_TRIM_SPAN_WORDS` is 3): six or more
  identical words collapse to three copies, a 2-word span repeated exactly 3 times is not trimmed,
  and repeated 4 times is trimmed to 2 copies — documented on `trim_trailing_repeat` and pinned by
  `the_documented_short_span_limitations_hold`, not changed.
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
