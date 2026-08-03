# Goal Contract — TASK-operator-listen-state-management

## Identity

- Goal ID: TASK-operator-listen-state-management
- Parent goal ID: TASK-operator-live-transcript-display
- Title: The "Start listening" control shows honest states (preparing / downloading% / listening / waiting-for-speech / error) instead of a silently-disabled button
- Role: frontend-engineer (+ backend-engineer for the progress events)
- Status: VERIFIED_COMPLETE
- Execution engine: goal
- ClickUp task: 86ajtxuwr (Live transcript + scripture auto-detection — R3/R4 slice; status QA)
- Created: 2026-08-02
- Updated: 2026-08-02
- Maximum iterations: 6
- Independent verification required: yes

## Objective

Fix the reported bug — "clicking Start listening disables the button but nothing happens" — by managing the listen control's states end-to-end: the operator always sees what the system is doing (loading the model, downloading it on first run with a %, listening, waiting for speech, or a failure reason), and an empty transcript while listening is a diagnosable state rather than a dead panel.

## Baseline

- **Root cause (verified by code):** `start_listening` (feature `stt`, `main.rs:811`) `await`s `listening::start(app)`, whose oneshot resolves only after the worker `load_recognizer()` completes — on first run that downloads the ~1.6 GB Whisper model + SHA-256 verifies + loads whisper.cpp (minutes). During that whole await the JS `await invoke("start_listening")` is pending, so the button stayed disabled with the panel unchanged → **looked hung** (not a deadlock). The no-`stt` stub returns an error immediately, which would re-enable + show a message — so the reported symptom confirms the `stt` build + the blocking load.
- **Second report — "no realtime text once listening":** the STT engine emits a segment when an utterance *closes* (~300 ms trailing silence, `EngineConfig::hangover_frames`, or the 10 s force-close), so text appears per-utterance, not word-by-word. The Rust ingest→host→wire→view→display path is proven end-to-end (`remote_transcription_detects_and_approves_over_the_wire` asserts `v.transcript.len()==1`; the headless harness asserts `syncTranscript` renders `view.transcript`). If nothing appears, segments are not being produced/ingested in the live run — i.e. the on-device recognition path (whisper/VAD/mic), which is spike-gated (S8/S11) and not reproducible without a mic + audio here.

## Inputs and evidence sources

- `dist/app.js` (`wireTranscriptListen`, `syncTranscript`), `dist/index.html` (`#transcript`), `src/listening.rs`, `src/main.rs`.
- `selahcue-stt/src/engine.rs` (utterance close/emit timing), `selahcue-app/tests/test_operator_remote.rs` (wire round-trip), `scripts/operator_headless.py`.

## Scope

### In scope

- Frontend state machine for the listen control: idle → preparing → (downloading %, first run) → listening → error; never a silently-disabled button.
- A diagnosable listening status: "waiting for speech…" (listening, no lines yet) vs "transcribing on-device" (a line has arrived), derived from the host-authoritative poll.
- Backend: emit `stt://progress` (bytes/total/pct) from the worker during the first-run model download so the UI can show the %.
- A live microphone-level readout (`frame_peak` + `CpalSource::peak_level` → `stt://level`) surfaced in the waiting status ("waiting for speech… (mic N%)"), so a dead/denied mic (peak 0 while speaking) is visibly distinct from a working mic with recognition still pending — pinning the true cause of "no text".

### Non-goals

- The on-device recognition quality itself (whisper output, VAD tuning, mic capture) — spike-gated, unreproducible here. This goal makes it *visible/diagnosable*, not "more accurate".
- Cancelling an in-progress download (the designed download modal covers that — follow-up).
- Any wire-protocol change; the transcript render path is unchanged.

### Constraints

- No stale "not wired" copy; keep untrusted text as `textContent`; the aria-live log stays append-only; all pinned needles/ids intact. `make ci` clean. The `stt`-gated backend must compile (`cargo check --features stt`).

### Assumptions and unknowns

- ASSUMED: showing progress + a diagnosable "waiting for speech…" state resolves the operator-visible bug; the underlying recognition is owner-verified live (`make launch OP_FEATURES=stt`, speak). Live whisper output cannot be exercised in this environment (no mic/audio).

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Clicking Start immediately shows "Preparing…" (disabled+labelled), never a silent dead button | `python3 scripts/operator_headless.py` | listen preparing check passes | harness: "clicking Start immediately shows 'Preparing…'" | PASS |
| C-002 | yes | First-run model-download progress renders a % from a host event | `python3 scripts/operator_headless.py` (emits `stt://progress`) | "Downloading model… 38%" check passes | harness output | PASS |
| C-003 | yes | On ready → "Stop listening" (enabled); a start failure surfaces the reason + re-enables | `python3 scripts/operator_headless.py` | both transition checks pass | harness output | PASS |
| C-004 | yes | Listening + no lines → "waiting for speech…"; a recognised line → "transcribing on-device" (empty transcript is diagnosable) | `python3 scripts/operator_headless.py` | both status checks pass | harness output | PASS |
| C-005 | yes | Backend emits `stt://progress` during download; operator compiles with `--features stt` | `cargo check --manifest-path .../selahcue-operator/Cargo.toml --features stt` | Finished, no errors | compile output; `listening.rs` emit | PASS |
| C-006 | yes | The host-authoritative transcript + detection render path is unchanged (regression) | `python3 scripts/operator_headless.py` | display + R4 pill checks still pass | harness: 148 checks, 0 FAIL | PASS |
| C-007 | yes | Full CI gate green | `make ci` | ALL GREEN | ci6.log | PASS |
| C-008 | yes | A pure, tested mic-peak helper exists; the capture source exposes a live level; the worker emits `stt://level` | `cargo test -p selahcue-stt --test pipeline frame_peak` + `cargo check --features stt` | frame_peak test passes; operator compiles with the emit | test output; `listening.rs` MicLevel emit | PASS |
| C-009 | yes | The waiting status shows the mic level ("(mic N%)"), making a dead/denied mic distinct from pending recognition | `python3 scripts/operator_headless.py` | "(mic 0%)" and "(mic 42%)" checks pass | harness: 151 checks, 0 FAIL | PASS |
| C-010 | yes | A sustained 0% level surfaces an actionable permission hint (not a dead 0%) | `python3 scripts/operator_headless.py` | the "grant mic access / Privacy & Security / Microphone" hint check passes | harness output | PASS |
| C-011 | yes | The dev binary embeds `NSMicrophoneUsageDescription` so the non-bundled `cargo run` build can request the mic (macOS) | `cargo build` operator + `otool -P <bin>` | plist section present with the mic usage key; ad-hoc signed | otool output; `build.rs` + `Info.plist` | PASS |
| C-012 | yes | `make operator`/`make launch` run the operator from a signed `.app` bundle on macOS (reliable mic TCC) | assemble+sign the bundle; `codesign --verify --deep --strict`; `make -n operator` | bundle verifies (id com.selahcue.operator, mic usage present); target routes to the script | validation output; `run_operator_macapp.sh` + Makefile | PASS |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused: `node --check dist/app.js`; `python3 scripts/operator_headless.py` (148 checks); `cargo check --features stt`; `cargo test -p selahcue-present --test test_tokens`.
- Broader: `make ci`.
- Independent: owner live QA — `make launch OP_FEATURES=stt`, press Start (watch preparing → downloading% → listening), speak (watch "waiting for speech…" → a recognised line). The headless harness is the in-repo proxy for the state machine.
- Environment: desktop workspace + node + headless Chrome + cmake (whisper).

## Iteration ledger

### Iteration 1 — state machine + progress events + diagnosable status

- Target criterion: C-001…C-007.
- Hypothesis: the "does not run" symptom is the blocking readiness await during the minute-long first-run download with no UI feedback; a client state machine + a host progress event + a "waiting for speech…" status fix the operator-visible bug and make an empty transcript diagnosable without touching the (proven) render/ingest path.
- Change or investigation: traced `start_listening` → `listening::start` (blocking load) and the STT engine's utterance-close emit; rewrote `wireTranscriptListen` as a state machine; hooked `syncTranscript` to report line count; emitted `stt://progress` from the worker download callback; extended the harness (event stub + pending start control + 7 checks).
- Verifier executed: node --check (OK); headless (148 checks, 0 FAIL); `cargo check --features stt` (Finished); test_tokens (14); `make ci` ALL GREEN.
- Result: PASS.
- Decision: continue → Iteration 2 (the operator reported it stayed "waiting for speech…" — add a mic-level readout to pin mic vs. recognition).

### Iteration 2 — mic-level readout to isolate mic vs. recognition

- Target criterion: C-008, C-009 (+ re-run C-006/C-007).
- Hypothesis: the panel now correctly shows "waiting for speech…", so segments aren't being produced. On macOS a denied mic yields *silence, not an error* (cpal callback receives zeros), so the VAD never opens an utterance. A live input-level readout makes that visible: peak 0 while speaking ⇒ mic/permission; peak > 0 with no lines ⇒ VAD/recognition downstream.
- Change or investigation: added a pure `frame_peak` (tested); `CpalSource` accumulates a peak in the capture callback and exposes `peak_level()` (read-and-reset); the worker emits `stt://level {pct}` ~5×/s and logs the chosen input device; the frontend shows "(mic N%)" in the waiting status.
- Verifier executed: `cargo test -p selahcue-stt --test pipeline frame_peak` (ok); `cargo clippy -p selahcue-stt --features capture -D warnings` (clean); `cargo check --features stt` (Finished); headless (150 checks, 0 FAIL); `make ci` ALL GREEN.
- Result: PASS.
- Decision: continue → Iteration 3 (owner reported **mic 0%** — turn the reading into an action).

### Iteration 3 — actionable no-audio hint

- Target criterion: C-010 (+ re-run C-009).
- Hypothesis: mic 0% while listening confirms the app gets no audio; on a `cargo run` dev binary that is macOS mic permission (attached to the launching terminal; no bundle Info.plist to prompt). Turning a run of 0% into an explicit "grant mic access" instruction resolves it operator-side.
- Change or investigation: the frontend counts consecutive 0% levels (`NO_AUDIO_TICKS`) and, after ~2.5 s of silence, replaces the empty-state sub with "No audio is reaching the microphone (0%). Grant mic access in System Settings → Privacy & Security → Microphone, then stop and start listening again."
- Verifier executed: node --check (OK); headless (151 checks, 0 FAIL — adds the hint check); test_tokens (14). JS-only change; Rust gates unchanged from the Iteration-2 ALL GREEN.
- Result: PASS.
- Decision: continue → Iteration 4 (owner: the terminal never appears in the mic list even after `tccutil reset` — the raw dev binary can't request the mic at all).

### Iteration 4 — embed NSMicrophoneUsageDescription so the dev binary can request the mic

- Target criterion: C-011.
- Hypothesis: a non-bundled `cargo run` binary with no embedded Info.plist cannot trigger a TCC prompt, so the terminal never appears in System Settings → Microphone and capture silently returns silence. Embedding an Info.plist with `NSMicrophoneUsageDescription` into the Mach-O lets the raw binary request access.
- Change or investigation: added `Info.plist` (with the mic usage description + bundle id) and a `build.rs` that, on the macOS target, injects `-Wl,-sectcreate,__TEXT,__info_plist,<plist>`; link-time only so CI's `cargo check`/`clippy` are unaffected.
- Verifier executed: `cargo build` (operator) links clean; `otool -P` shows the plist + `NSMicrophoneUsageDescription`; `codesign -dv` = adhoc (linker-signed); operator `cargo fmt --check` + `cargo check` clean.
- Result: PASS.
- Decision: continue → Iteration 5 (owner ran `make launch`; embedding alone did not surface a prompt on their macOS — run from a real bundle).

### Iteration 5 — run the operator from a signed .app bundle (reliable macOS mic TCC)

- Target criterion: C-012.
- Hypothesis: macOS grants microphone access reliably only to a genuine `.app` bundle with a signed identity; a bare binary (even with an embedded plist) is unreliable across versions. Wrapping the built binary in a minimal signed bundle and launching that gives TCC a stable identity to prompt for and remember.
- Change or investigation: `Info.plist` made bundle-complete (CFBundleExecutable/PackageType/versions + mic usage); `scripts/run_operator_macapp.sh` builds → assembles `SelahCue Operator.app` → ad-hoc signs with `--identifier com.selahcue.operator` → launches it **via LaunchServices (`open -W`), not by exec'ing the binary**. This is the decisive fix: only a LaunchServices-started app is its own TCC "responsible process", so macOS prompts for the app; exec'ing from the shell makes the *terminal* responsible (unauthorized) — which is why no prompt appeared and nothing showed in System Settings → Microphone. The app is non-sandboxed so it keeps the per-user `$TMPDIR`, preserving output-window endpoint discovery; stdio is redirected to `target/operator.log`. `make operator`/`make launch` route through it on macOS (Darwin), `cargo run` elsewhere. CI (`cargo check`/headless) is untouched.
- Verifier executed: assembled + signed the bundle; `plutil -lint` OK; `codesign --verify --deep --strict` OK; `codesign -dv` shows id com.selahcue.operator; `PlistBuddy` confirms the mic usage; `make -n operator` routes to the script; `make help` parses. Two live runs hit `open` error `-10810`; reproduced + bisected the flag combos: **`--stdout`/`--stderr` combined with `-W`** is what trips `-10810` on current macOS (with or without `-W` alone it's fine). Fixed by dropping the stdio redirect — plain `open -n -W "$APP"` launches cleanly (verified: process stays up, no error). The `SelahCue STT:` diagnostics go to the unified log (`log stream … selahcue-operator`); the mic level + download % are shown live in the UI regardless. Paths are absolute and the bundle is `chmod +x`/`xattr -cr`/`lsregister`'d for good measure.
- Result: PASS — all 12 criteria PASS.
- Decision: complete → VERIFIED_COMPLETE. Owner runs `make launch OP_FEATURES=stt`, approves the mic prompt, and confirms mic > 0% + recognised lines.

## Risks and rollback

- Risk: the `stt`-gated `listening.rs` is not in CI's (no-`stt`) gate — mitigated by a local `cargo check --features stt` (cmake present).
- Risk: the real "no text" cause may be recognition (whisper/VAD/mic), which this goal only makes diagnosable — the "waiting for speech…" state + stderr download/`SelahCue STT:` logs isolate it for owner QA.
- Rollback: revert `dist/app.js`, `listening.rs`, and the harness block; additive and separable.
