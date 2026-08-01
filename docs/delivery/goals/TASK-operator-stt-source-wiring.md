# Goal Contract — TASK-operator-stt-source-wiring

## Identity

- Goal ID: TASK-operator-stt-source-wiring
- Parent goal ID: EPIC 86ajp08py (R3 · Transcription) / related 86ajtxzre (STT engine)
- Title: Wire the on-device STT engine as the Operator Console's live-transcript source (feature-gated), so "Start listening" drives real transcription → detection
- Role: frontend-engineer
- Status: VERIFIED_COMPLETE
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86ajtxzre (STT engine follow-up; no dedicated story)
- Created: 2026-08-01
- Updated: 2026-08-01
- Maximum iterations: 10
- Independent verification required: yes

## Objective

The Operator Console's **Start listening** control drives the on-device `selahcue-stt`
engine in the host: captured audio → transcription → `ingest_transcript` → exact + fuzzy
detection → the transcript + detection panels the console already renders. The wiring is
**feature-gated** (`stt`, OFF by default) so the default operator compile-check (CI) stays
green without the native whisper toolchain/model; the real audio path is opt-in
(`--features stt`) on a whisper-capable machine. No override of the concurrent Design-2
operator-console rewrite (surgical staging).

## Baseline

- Backend: `ingest_transcript` (host command + `OperatorShell::ingest_transcript`) runs exact
  + fuzzy detection → `view.transcript` / `view.detections`. `selahcue-stt` provides
  `SttEngine`, `CpalSource` (feature `capture`), `WhisperRecognizer` (feature `whisper`),
  `SttProvider`, `pump`.
- The concurrent (uncommitted) Design-2 console already renders transcript + detections
  (`syncTranscript`/`syncDetections`) and wires Stage/Dismiss; the **Start listening** toggle
  (`#transcript-listen`) is client-only (no backend call). The operator does NOT depend on
  `selahcue-stt`; there is no listening command.
- `OperatorShell` is `Clone` and holds the shared `Arc<Mutex<LiveController>>` — a worker
  thread can hold a clone and call `ingest_transcript` (locks internally).
- Environment cannot build/run whisper (no cmake/model); the operator crate is
  workspace-excluded (compile-check only). The wireTranscriptListen handler in `app.js` is
  NOT in the concurrent diff (surgically wireable); `main.rs` insert points sit in gaps
  between the concurrent hunks (217 / 651 / 891).

## Inputs and evidence sources

- ClickUp 86ajtxzre, epic 86ajp08py; ADR-0019 (seam), ADR-0012 (model integrity).
- `selahcue-operator/src/main.rs`, `dist/app.js`; `selahcue-stt`; `selahcue-app/src/operator.rs`.

## Scope

### In scope

- Operator `Cargo.toml`: optional `selahcue-stt` (features whisper, capture) behind a new
  `stt` operator feature (default OFF).
- `src/listening.rs` (`#[cfg(feature = "stt")]`): a worker that runs `SttEngine` + `CpalSource`
  → `SttProvider` → `OperatorShell::ingest_transcript`, with start/stop + a bounded loop;
  model resolved from env (path + pinned SHA-256, verified before load — FR-156).
- `main.rs`: `start_listening` / `stop_listening` Tauri commands (real under `stt`, honest
  "not in this build" stub otherwise) + registration; surgical, in gaps.
- `app.js`: wire the `#transcript-listen` button to invoke start/stop and reflect real
  state/errors honestly (no fabricated transcript).

### Non-goals

- Verifying the real whisper audio path here (needs cmake + model — spike-gated S8/S11).
- Model download/delivery (ADR-0012 → Stage-13); editing the concurrent Design-2 files
  outside the untouched listen handler; the Remote-host STT path.

### Constraints

- Default build (no `stt`) MUST compile (CI operator check) with no whisper. Honest fallback
  when STT is absent. No fabricated transcript (empty until the host reports real segments).
- Surgical staging only — no concurrent Design-2 hunk is staged/overridden.

### Assumptions and unknowns

- ASSUMED: `--features stt` compiles on a machine with cmake + whisper — validated by C-008 there.
- UNKNOWN: real transcription accuracy/latency — spike-gated (S8/S11).

## Dependencies and approvals

- Owner (o.majiyagbe) chose "do the host wiring now, in-tree" (session, 2026-08-01), accepting
  the collision risk with the concurrent rewrite (mitigated by surgical staging).

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Default operator build (no `stt`) compiles — stub commands + handler registration + Cargo.toml | `cargo check --manifest-path implementation/desktop/crates/selahcue-operator/Cargo.toml` | compiles, no errors | check log | PASS |
| C-002 | yes | The default build pulls NO whisper/cpal (feature-gated); `stt` feature declares the optional dep | `cargo tree --manifest-path .../selahcue-operator/Cargo.toml -e no-dev` shows no whisper-rs; `--features stt` shows it | whisper only under `stt` | tree output | PASS |
| C-003 | yes | `start_listening` + `stop_listening` commands exist (both cfg variants) and are registered in `generate_handler!` | grep `main.rs` | both commands defined + registered | grep | PASS |
| C-004 | yes | Honest fallback: without `stt`, `start_listening` returns a clear "not in this build" error; no fabricated transcript | review stub + `app.js` empty-state | honest error surfaced; stream empty until real segments | code | PASS |
| C-005 | yes | The `#transcript-listen` button invokes start/stop and reflects real success/error state | grep `app.js` + headless operator check | button wired; state honest | app.js + operator_headless | PASS |
| C-006 | yes | `listening.rs` worker drives `SttEngine`→`ingest_transcript` with a stop flag + bounded loop; model verified before load (FR-156) | review `listening.rs` | correct structure; `verify_model` before `WhisperRecognizer::load` | code review | PASS |
| C-007 | yes | No concurrent Design-2 hunk is staged/overridden — only my files/hunks | `git diff --cached --name-only` + staged diff review | only Cargo.toml / listening.rs / my main.rs+app.js hunks | staged diff | PASS |
| C-008 | no | `--features stt` compiles on a whisper-capable machine (cmake + model) | `cargo check --features stt` on such a host | compiles (env-dependent) | unbuildable here (no cmake/model); import fix applied by inspection | BLOCKED |

## Verification plan

- Focused: default `cargo check` (operator) + `cargo tree` feature check + grep + headless operator check.
- Broader regression: the default build is unaffected by the OFF feature; C-007 proves no seam/concurrent override.
- Independent verifier: code review of `listening.rs` + the wiring (whisper path unbuildable here).
- Required environment: Rust stable + network (resolve optional deps). Real audio path needs cmake + a whisper model (`--features stt`).

## Iteration ledger

### Iteration 1 — implement the wiring (C-001..C-007)

- Change: `stt` feature + optional `selahcue-stt`; `listening.rs` worker; `start/stop_listening` commands (+ stub); button hookup. Surgical (main.rs/app.js hunks in gaps).
- Verifiers: default `cargo check` compiles (no whisper); commands registered; my app.js change passes headless (99/0) isolated on a clean baseline.
- Evidence: commit `5d035ae` (superseded).
- Decision: handoff to independent review.

### Iteration 2 — independent review + fixes (C-006/C-007)

- Investigation: review confirmed the Send split, no-deadlock, idempotence, honest fallback, model integrity, bounded memory, render isolation — but found a **BLOCKER** (`--features stt` would not compile: `CpalSource`/`WhisperRecognizer` imported from the crate root, which does not re-export them), a MEDIUM (mic-open failure left a phantom "listening" state), two LOWs (worker lock held across the slow model load; poisoned-lock made the worker unstoppable), and an INFO — the app.js commit had **bundled ~155 lines of concurrent Design-2 command-palette code** into my hunk.
- Change (`cb5b6bc`, supersedes `5d035ae`): import `CpalSource`/`WhisperRecognizer` by module path; startup handshake so mic/model failures surface (no phantom state); load the model outside the worker lock; consistent poisoned-lock recovery; **re-committed surgically so app.js contains ONLY my ~15-line handler** (verified 0 palette lines; the concurrent palette is preserved, unstaged, in the working tree).
- Verifiers: default `cargo check` compiles; my commit's app.js has 0 concurrent code; working tree still holds the concurrent rewrite intact; JS valid.
- Evidence: commit `cb5b6bc`.
- Decision: complete for the verifiable scope; `--features stt` compile is env-blocked (C-008).

## Risks and rollback

- Risks: enabling the optional dep perturbs the operator lock (mitigated: default build doesn't build whisper; verify `cargo check`); collision with the concurrent rewrite (mitigated: surgical staging, edits only in gaps + the untouched listen handler); real audio path unverified here (accepted; whisper-gated).
- Rollback: fully additive/feature-gated — drop the `stt` feature + `listening.rs` + the 2 commands + the button hunk; the default console is unchanged.

## Pause and escalation conditions

- If `cargo check` (default) cannot resolve the optional `selahcue-stt` dep offline and no network is available → pause, report the exact dependency-resolution requirement.

## Final evaluation

- Validator command: `python3 scripts/validate_goal_contract.py docs/delivery/goals/TASK-operator-stt-source-wiring.md --require-complete`
- Validator result: PASS (all 7 mandatory criteria PASS).
- Independent verification result: review confirmed the design (Send-correct, no deadlock, honest fallback, model integrity, bounded, render-isolated); its BLOCKER + MEDIUM + 2 LOW + the bundled-concurrent-code INFO were all addressed in `cb5b6bc`.
- Terminal state: **VERIFIED_COMPLETE** for the default build + wiring. Commit on `main`: `cb5b6bc`.
- Remaining / open follow-ups (non-blocking): **C-008 — verify `cargo check/run --features stt` on a whisper-capable machine (cmake + a model)**; the import fix + worker are correct by inspection but unbuilt here. Also: real accuracy/latency spike (S8/S11); the button hookup lives on the concurrent Design-2 app.js line — reconcile at their merge; model delivery (ADR-0012 → Stage-13).
- ClickUp final evidence comment: posted to 86ajtxzre.
