# implementation/desktop/CLAUDE.md

This supplements the repo-root `CLAUDE.md` with guidance specific to the desktop Rust workspace. It loads only when Claude is working with files under `implementation/desktop/`.

## Commands

`make launch`/`make run`/`make operator` (from the repo root) build the operator with **on-device STT, cloud (Deepgram) STT, `dev-keys`, and `openai-notes` all on by default** — `STT ?= auto` detects a local cmake toolchain and, when present, enables BOTH `stt` and `cloud-stt` (the latter implies the former at the Cargo level — mic capture lives in `selahcue-stt` regardless of which recognizer consumes it, so there is no toolchain-free way to offer cloud transcription independently); `AI ?= auto` (86akcmzyq/86akcmzrd) unconditionally enables the developer `.env` key loader (`dev-keys`, which also supplies `DEEPGRAM_API_KEY`) and the direct-to-OpenAI sermon-note path (`openai-notes`), since neither needs a native toolchain. Each prints what it enabled and why (`>> live transcript (STT): ...`, `>> AI-assisted sermon notes: ...`); force either family off with `STT=0`/`AI=0` — `STT=0` disables cloud transcription too, matching what a developer would expect "no live transcript feature" to mean. This exists because a shipped, merged, four-reviewer-tested feature (FR-122 notes, PR #19) stayed invisible from these exact commands until 86akcmzyq/86akcmzrd fixed it, and it happened again for cloud transcription (86akby7th, closed by 86akd10dq) — do not gate a future AI/STT feature behind an opt-in flag and expect anyone to find it. Compiling `cloud-stt` in does not itself pick a recognizer — that stays the runtime Settings choice — and a build with it on but no `DEEPGRAM_API_KEY` honestly reports "key missing", not "not available in this build".

**`RELEASE=1` (or `--release`) can never carry `dev-keys`/`openai-notes` through these targets — structurally, not by default.** `make`'s `release-ai-guard` prerequisite refuses (hard `exit 1`, before any cargo command runs) any `RELEASE=1` invocation whose resolved feature list contains either token, including a direct `OP_FEATURES=dev-keys,openai-notes` override — verified by actually running `make operator RELEASE=1 OP_FEATURES=dev-keys,openai-notes` and observing it abort at that prerequisite. That still leaves a bare `cargo build --release --features ...` typed outside Make, and here the two features are guarded **separately, by construction, not by one shared mechanism**: `selahcue-operator/src/dev_env.rs`'s `load()` checks `cfg!(debug_assertions)` and no-ops in any release profile regardless of features requested, closing the `--release --features dev-keys` route; `selahcue-cloud/src/openai.rs`'s `direct_key_permitted` gates `OpenAiNoteProvider::from_env` (the actual generation path) and `direct_notes_provider`'s status descriptor in `main.rs` on the same check, closing the separate `--release --features openai-notes` route (86akcmzyq PR #24 review: the first cut of this fix only guarded `dev-keys`, so `openai-notes` alone — no `dev-keys`, bypassing Make — still built a working direct-to-OpenAI release binary from whatever `OPENAI_API_KEY` happened to already be exported in the shell). Both are verified by building and running real `--release --features ...` binaries and observing the refusal rather than a working provider, for each feature independently. All three predicates (`should_load_env_file`, `direct_key_permitted`, and the call sites that wire them into `load()`/`direct_notes_provider`/`from_env`) are mutation-tested, including a dedicated release-profile `cargo test --release` pass in `make ci` and CI (`selahcue-cloud --features openai --release`, `selahcue-operator --features dev-keys,openai-notes --release`) — before this fix nothing built or tested either crate in `--release` at all, so a regression in any of these call sites passed every automated gate green. None of the three guards is airtight against an explicit `[profile.release] debug-assertions = true` or a `RUSTFLAGS` override — nothing in-repo can see either — which is exactly why `scripts/installer_secret_scan.py` (86akc041v) exists as an independent, byte-level check on artefacts this repo actually ships. The one workflow that ships a real installer (`.github/workflows/windows-installer.yml`) never reads `OP_FEATURES`/`AI` at all — it hardcodes its own `cargo tauri build --features stt` — so it is unaffected by this default either way.

Direct cargo (workspace manifest is `implementation/desktop/Cargo.toml`):

```bash
cd implementation/desktop
cargo test -p selahcue-core --test test_scripture            # one test file
cargo test -p selahcue-core --test test_scripture -- name    # one test by name filter
cargo test -p selahcue-lan  --features server                # TLS transport + loopback E2E
cargo test -p selahcue-app  --features server                # remote-control E2E — flag REQUIRED
cargo test -p selahcue-data --features encryption            # SQLCipher at-rest encryption
cargo test -p selahcue-gpu                                   # GPU↔CPU parity (skips w/o GPU)
```

`--features server` is **mandatory** for `-p selahcue-app`, unlike the others: `ControlClient` is `server`-only in `selahcue-lan`, but `operator.rs`'s `RemoteOperator` — which holds one — is not itself gated, so the bare form fails to *resolve* the type and reads as a broken tree, where bare `-p selahcue-lan` merely skips tests. `--workspace` hides it: `selahcue-desktop` takes `selahcue-app` with `features = ["server"]`, so Cargo unifies the feature on. The `ci` target gets this right; copy it, don't drop the flag.

Two crates are **excluded from the workspace** (each is its own root — `cargo test --workspace` does NOT cover them):

```bash
# Tauri operator shell (GUI; heavy toolchain deps). CI runs check + clippy + its unit
# tests, but never launches the GUI — the behavioural cover is the two headless webview
# gates below. Locally, compile-check it with:
cargo check --manifest-path implementation/desktop/crates/selahcue-operator/Cargo.toml
python3 scripts/operator_headless.py   # its behavioural check (headless Chrome; in `make ci`)

# On-device STT engine (whisper.cpp/cpal behind `whisper`/`capture` features, off by default):
cargo test --manifest-path implementation/desktop/crates/selahcue-stt/Cargo.toml
```

## Architecture

Layered crate graph; lower layers are pure and never depend on higher ones:

- `selahcue-core` — domain core: scripture reference parsing, `ServicePlan`, injected-clock `Timer`, the `TranscriptProvider` seam (ADR-0019). **Pure, deterministic, no I/O**; the parser never panics on untrusted input (workspace lint: `clippy::unwrap_used = warn`).
- `selahcue-scripture` — bundled public-domain scripture text (WEB) with lookup/keyword search.
- `selahcue-data` — SQLite (WAL) persistence, forward-only migrations, online backups; `encryption` feature compiles SQLCipher (`open_encrypted` exists only with the feature, so a keyless "encrypted" open cannot compile).
- `selahcue-lan` — operator↔controller control plane (ADR-0008). Default build is the transport-free core: versioned JSON wire protocol, RBAC (single `authorize()` choke point), pairing/session tokens. The `server` feature adds the TLS-pinned WebSocket transport (rustls, cert pinned by SHA-256 from the pairing QR), time-boxed and connection-capped.
- `selahcue-engine` — GPU-free render-engine test seam (ADR-0015): deterministic CPU rasterizer + pixel readback, fault injection (never-blank guarantee NFR-024), flash-rate analyzer, versioned render↔control IPC contract.
- `selahcue-present` — slide composition + `Presenter` (Preview→Live) + stage/confidence output. Core invariant: **staging never changes Live; only Go Live does.**
- `selahcue-gpu` — wgpu compositor rendering the same `scene::Frame`; offscreen readback must match the CPU rasterizer at **SSIM ≥ 0.99** (the cross-GPU parity oracle).
- `selahcue-desktop` — native output window (winit + wgpu), bin `selahcue-output`; hosts the LAN server and writes its endpoint file to the OS temp dir for the operator/CLI to find.
- `selahcue-app` — `LiveController`: maps RBAC-checked LAN commands onto presenter + plan (the full remote-control loop, E2E-tested with `--features server`).
- `selahcue-operator` (excluded) — Tauri operator console. Per ADR-0002/0003 the WebView is the operator *console only*; the *compositor* is native wgpu — never render audience output in the WebView. UI is plain HTML/JS/CSS in `dist/`.
- `selahcue-stt` (excluded) — offline STT implementing core's `TranscriptProvider`; pure-Rust pipeline (framing, resample, VAD, feedback guard, model integrity) tested with no native deps.

Guiding principles (from `ARCHITECTURE.md`): desktop-authoritative, offline-first, no component failure may blank live output, AI assists but never gates core controls, LAN peers are untrusted, resource use is bounded.

## Conventions and traps

- Tests are public-API integration tests in each crate's `tests/`, one file per module. (Single exception: a white-box test inline in `core/src/scripture.rs`.)
- Timers/animation take an **injected clock** — keep new time-dependent code deterministic the same way.
- **`selahcue-stt` is linted by nothing.** It is excluded from the workspace and no CI job references it, so its own `unwrap_used = "warn"` policy is unenforced — it currently has three violations under `-D warnings`. Only `cargo test --manifest-path .../selahcue-stt/Cargo.toml` exercises it, and nothing runs that in CI either. Tracked on 86ak5rjh7.

### Bounded-memory tests

Having one is necessary but not sufficient. Mutation batteries against this repo left roughly a third to a half of the controls believed "tested" surviving — including controls in tests written to remediate an *earlier* round of vacuous ones. The bar is a property of the **test**, not the suite: *this test must fail if the control it names is removed.* Phrased suite-wise, it gets satisfied by adding more tests. Worked example throughout: `selahcue-engine/src/raster.rs` + `tests/test_raster.rs`.

- Expose a **per-key** `Option`-returning hit accessor, never a global counter — a global lets a sibling test's hits mask a miss on your key (`prefix_cache_hits_for`).
- Assert the hit **before** the contract, in a message that names what went unexercised (`…the byte-identity contract was not exercised` in `a_cache_hit_is_byte_identical_to_a_cold_render`).
- Pin the premise at compile time so changing a cap cannot silently turn the test vacuous: `const _: () = assert!(…)`, both beside the constant (see `PREFIX_CACHE_ENTRY_KEY_HEADROOM`) and inside the test.
- Assert the **entity** — entry count, or a named key present/absent — never a proxy like `retained_bytes <= N * item_bytes`.
- Bound the entry **count** as well as the bytes (`PREFIX_CACHE_MAX_ENTRIES`): a byte budget alone admits unboundedly many tiny entries, which unbounds lookup cost.
- Add a **positive control** — assert both that the hostile case is refused *and* that the benign case still exercises the code, else "refused" is indistinguishable from a dead mechanism (`an_over_cap_frame_renders_correctly_and_bypasses_the_cache`).
- **Mutation-verify before claiming it**: break the guard, confirm RED, restore — running the file with its siblings, never `--exact`. One test here caught its mutation 5/5 in isolation and missed it 10/10 with siblings running.
- **A control that guards another control can be dead in a way none of the above catches.** The question to ask is: *if I mutate the original predicate, does the control still pass?* If it does, the control is reading a **copy**. This is distinct from the vacuous-cache trap above — that is a test asserting nothing; this is a control asserting something about the wrong expression, and it survives mutation of the real one. It happened here (86ak643rc): a control added to prove a selection predicate was live re-derived `resolved && distinct` as two separate reads instead of consuming the predicate's own verdict, so dropping `resolved` from the selection loop left the control untouched and the suite stayed green. The trap was not duplicating a variable — it was that **the conjunction** existed as one expression in the code under test and as a re-assembled pair in the control. Give the predicate, *including its conjunction*, a single definition that both the control and the code under test consume, then mutate that definition (`installed_serif`'s `verdict` in `selahcue-present/tests/test_measure.rs`).
