# B1 — durable transcript storage health

Status: DONE_WITH_CONCERNS (implementation/local evidence complete; native pilot gates and independent review remain with controller).

Branch: `codex/pilot-b1-storage-health-20261111`. Base: `7f6dbcbb4782854cbb0fea14a3bb5a9ffcf7fcd0`. Worktree: `/Users/m.oluwole/.codex/worktrees/sermon-pilot-discovery/scph`.

Evidence directory: `/Users/m.oluwole/.codex/visualizations/2026/11/11/01a1c999-1923-7970-83c1-650fe3817d16/b1-storage-evidence`.

## Implemented behavior

- Installed one persistent `BackgroundTranscriptWriter` in desktop production. Its factory opens the existing plaintext/SQLCipher connection and sweeps orphans on the worker. Open, append and end run outside both controller and shared health/queue mutexes. There is no blocking send, join or durability wait on control, rendering or Drop. The synchronous batching helper remains for existing callers/tests and is not wrapped by the production worker.
- Reused the existing segment structure, UTF-8-safe text bounding helper and batching constants. There is one production deque and one in-flight segment, together capped at 64. Text is allocated once at at most 32,768 bytes and moved into/out of an append. At capacity, the oldest evictable pending segment is dropped; an in-flight append retains its permit until confirmed or explicitly counted discarded.
- Bounded FIFO lifecycle metadata to 64 descriptors, including the active worker descriptor, with label and provider limited to 1,024 bytes each. Rejected Starts invalidate the active selection and cannot attribute later finals to an older session. End marks an existing descriptor and cannot be displaced. Consecutive Start closes the preceding admitted generation.
- Preserved eight-segment, five-second and End flush policy; quiet periods wake through the worker condition variable. Failed active-session append retries wait until the next deadline, or an explicit final close; no retry spin. Tests inject monotonic/epoch clocks and wake the evaluator. Session timestamps are captured at the requesting boundary before I/O delay.
- Added memory-only four-field health with saturating sticky loss/truncation counters. Null, opening, failed/dead and closing storage is unavailable; successful writes cannot erase actual loss. Pending includes in-flight text. The synchronous helper exposes the same health contract; real adapter error strings are fixed/content-free.
- End ACK now means queued closure. The worker writes `ended_at` only after final flush or discard accounting. `TranscriptCompletion` supports explicit off-controller observation, including generation-specific completion that does not wait for a later session's stalled open. Completion means the work has finished accounting; health must still be checked for failed/lost writes. This does not promise crash/instant-exit losslessness.
- After a live Start, GetActiveTranscriptId returns only the latest generation's confirmed ID or none while opening/failed. Before any Start it preserves historical DB lookup. Ending a session retains its confirmed ID. Existing note-generation eligibility remains unchanged.
- Added independent LAN health view with optional/default/skip serialization and app mapping in both directions. Old host absence means unknown. Existing Rust/Dart pinned fixture bytes remain unchanged; no Dart or mobile lockfile edit was necessary.
- Operator renders an accessible persistent live status before transcript-tail dedup. Lost/truncated speech remains visibly unsafe after recovery; pending is saving; an absent old-host field is unknown. The new row has compact existing typography and its own bounded overflow; its transcript card scrolls at cramped heights and the status stays sticky. This prevents the new row from covering emergency controls.

## TDD and verification

All Cargo commands used `CARGO_TARGET_DIR=/private/tmp/selahcue-pilot-a1-target`; no cargo clean or placeholder recreation occurred. Commands ran from the worktree above. Logs below are in the evidence directory.

1. Initial health RED:
   `cargo test --manifest-path implementation/desktop/Cargo.toml -p selahcue-app --test test_transcript_durability`
   failed 1/8: `unwired_storage_is_explicitly_unavailable_in_the_real_host_view`, JSON Null versus false. `b1-red.log`.
2. Actual disk-boundary RED, same command: 7 passed/2 failed. Besides missing health, `stalled_store_calls_leave_shared_controller_timer_manual_and_frames_responsive` failed `open blocked the live controller` against the old synchronous writer. Gate released before cleanup/assertion. `b1-red-stall.log`.
3. Worker GREEN progressed through 9, 15 and 16 passing focused tests. Boundary/lifecycle/recovery tests were developed with the implementation; the additional memory controls were mutation-verified with siblings rather than represented as separate pre-implementation REDs.
4. Self-review RED, same focused command: 16 passed/1 failed, `queued_close_cannot_report_saved_until_the_store_finishes_ending` caught a zero-pending stalled end incorrectly reporting available. Added current-generation closing guard; 17 passed. `b1-close-red.log`, `b1-close-green.log`.
5. Browser RED: `python3 scripts/operator_headless.py`, unsandboxed, measured 2,912 checks and exactly six new B1 failures. The old expected count was then updated from 2,906 to the measured 2,912. `b1-ui-red-unsandboxed.log`.
6. First browser implementation passed all B1 checks but exposed two real new-row layout regressions: NOTIF-83/1280x720 and NOTIF-87/1280x720. A focused real-Chrome probe showed BLACKOUT/CLEAR hitting `transcript-status` with the row present, and the correct controls when only the new row was hidden. Compact typography fixed 720px but NOTIF-87 remained at the 640px shrink. A second probe proved containing the new card overflow restored both targets without moving the footer. `layout-probe720.json`, `layout-probe640.json`, `b1-ui-green.log`, `b1-ui-green2.log`. These were B1 regressions, not asserted baseline/environment problems.
7. Final actual browser: `python3 scripts/operator_headless.py` → **2,912 checks, 0 FAIL**. The exact existing emergency hit tests were preserved and now also run with lost/truncated/pending transcript state. `b1-ui-final.log`.
8. Complete desktop workspace: `cargo test --manifest-path implementation/desktop/Cargo.toml --workspace --features selahcue-app/server --no-fail-fast` → **2,097 passed, 0 failed, 13 ignored**, 181 result groups. This run preceded the close-health correction and final additional tests; it is not misrepresented as an exact-final-head full-workspace rerun. `b1-workspace.log`; every ignored test/reason is in `workspace-ignored-tests.txt` (measurement/network/host-font probes and child-process entrypoints).
9. Complete affected app/LAN suites after the source corrections: `cargo test --manifest-path implementation/desktop/Cargo.toml -p selahcue-app -p selahcue-lan --features selahcue-app/server --no-fail-fast` → **611 passed, 0 failed, 5 ignored**, 44 groups. Includes 27 note durability, 10 real remote/TLS notes and 38 protocol checks. `b1-final-siblings.log`.
10. Latest focused durability after adding the actual GetOperatorState sticky-loss assertion: `cargo test --manifest-path implementation/desktop/Cargo.toml -p selahcue-app --features server --test test_transcript_durability` → **20 passed, 0 failed**. `b1-durability-final.log`.
11. Final lint: `cargo clippy --manifest-path implementation/desktop/Cargo.toml -p selahcue-app -p selahcue-lan -p selahcue-desktop --all-targets --features selahcue-app/server -- -D warnings` → exit 0, no warnings. Earlier runs caught two Option::map/unit uses and one needless borrow in a test; fixed, not suppressed. `b1-clippy.log`, `b1-clippy2.log`, `b1-clippy-final2.log`.
12. `cargo fmt --manifest-path implementation/desktop/Cargo.toml --all -- --check` and `git diff --check` → exit 0.
13. Memory-bound mutation verification, restoring source after each run, using the whole focused transcript file (no --exact): excluding the in-flight permit failed with 65 versus 64 pending; allowing a 65th lifecycle descriptor failed with 65 versus 64 stored sessions; doubling allowed label bytes failed the oversized-admission loss assertion (1 versus 2). Each run: 16 passed/1 failed, exit 101. `b1-mutation-inflight.log`, `b1-mutation-sessions.log`, `b1-mutation-metadata.log`.

Sandbox limitations were distinguished from implementation failures: the first browser launch aborted with SIGABRT/no results; the first real TLS tests failed nine socket-bind tests at setup with Operation not permitted. Authorized unsandboxed reruns passed (27 notes + 10 remote + 37 protocol at that stage). `b1-ui-red.log`, `b1-notes.log`, `b1-notes-unsandboxed.log`. No automatic approval rejection blocked work.

## Meaningful acceptance coverage

The store gates block inside open/append/end without holding observation locks. While each remains held, the shared controller exercises real handler state/manual commands when server is enabled, pause/frozen/resume/TIME UP via injected time, manual Go Live and audience/stage frame reads. Watchdogs detect deadlocks; gate cleanup releases storage before thread joins/assertions.

The suite proves total-64 accounting and exact oldest-evictable contents for held open and append, sticky loss after subsequent writes, UTF-8 truncation, factory/open/append failure, worker panic, nonblocking Drop, count/quiet interval/End flush, bounded retries, FIFO repeated Start/End, full/oversized admission refusal, captured A/B timestamps and exact attribution. Real SQLite tests exercise 304 producer finals (including non-ASCII text), interim exclusion, live-ring eviction, explicit completion and reopen; separate real DB evidence proves End cannot make history eligible while final append is held. Notes regression proves historical A is not selected while B opens. Real GetOperatorState emits the four honest fields both before and after lost-speech recovery.

## Files and self-review

Production: app `transcript_sink.rs`, `controller.rs`, `lib.rs`, narrowly required `operator.rs` projection; desktop `main.rs`; LAN `protocol.rs`; operator `dist/app.js` plus the controller-approved minimal `dist/app.css` row/card containment. Tests: app transcript/note durability and remote notes; LAN protocol; actual operator headless driver. This report is the only added delivery evidence file in the source commit; raw logs are in the external artifact directory.

Self-review checked queue ownership across failed append, exact permit release, bounded lifecycle metadata, current-generation acknowledgement, FIFO end barrier, no database call under observation locks, no synchronous Drop join, unchanged note eligibility, unknown old-host status, unchanged ring/timer/output behavior, and emergency hit testing. Corrected false-saved closing state and actual warning layout regressions before completion.

File-size boundary concern: `transcript_sink.rs` is now 1,307 lines including retained existing synchronous helper/unit tests; `test_transcript_durability.rs` is 1,042 lines. Kept the approved file boundary rather than performing an unrelated module reorganization. Independent reviewers should pay particular attention to lifecycle/retry/completion invariants.

## Limits / controller-owned work

- Windows 10 / 4 GB latency, real device/provider operation, GPU/platform equivalence and native Tauri WebKit rendering remain unmeasured. The browser evidence is actual local Chrome, not native Windows evidence.
- No model, provider, credentials, release, deployment, PR, push, ClickUp, schema, retention or note-provider-policy work occurred. Existing ignored compile-only placeholders and unrelated mobile lockfiles were preserved.
- The worker cannot cancel a stalled native syscall. Drop requests closure and returns; a live shutdown deadline/wait policy was not invented. Process death may lose admitted-but-uncommitted speech. Loss/truncation health is lifetime memory, not persisted restart history.
- OS thread-spawn failure is handled fail-closed but was not fault-injected; factory failure and a worker adapter panic were exercised.
- A real save loss is still a failed pilot durability gate even though controls remain usable. Four independent reviews, any resulting corrections/re-review, and external/native integration evidence remain the controller's responsibility.
