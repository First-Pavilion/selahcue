# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

SelahCue — a cross-platform church presentation & ministry-assistance app. The repo is split:

- `implementation/` — production code, one self-contained root per platform: `desktop/` (Rust workspace — the only fully buildable platform), `mobile/` (Flutter controller app in `mobile/selahcue_controller/`), `web/` (placeholder).
- `docs/` — all planning/architecture/design/delivery artefacts. Decisions live in `docs/architecture/adr/` (ADR-0001…0019) and `docs/decisions/DECISION-LOG.md`; the master architecture is `docs/architecture/ARCHITECTURE.md`; the PRD is `docs/product/prds/SelahCue-PRD.md`; UI/UX specs are in `docs/design/` (Design 2.0 handoff: `DESIGN-2.0-HANDOFF.md`).
- ClickUp is the delivery source of truth; `docs/delivery/BUILD_STATE.md` is a lightweight pointer (Build Control task `86ajnx548`). Work lands in review-gated batches; each batch gets a `docs/delivery/CODE-REVIEW-batch*.md`.
- **Not in the repo**: the agent role skills and their shared process contract are user-level Claude Code configuration (`~/.claude/skills/`, `~/.claude/team/`). That contract is where the ClickUp discipline above is actually specified — read it before running a role skill. Any in-repo `.claude/` is gitignored, unauthoritative and absent from a fresh clone: don't hunt there for skills, and don't recreate it.

## Commands

The root `Makefile` wraps all the manifest paths and feature flags — prefer it. `make` alone lists all targets.

```bash
make ci          # the local RUST + FLUTTER gate (toolchain check, fmt --check, clippy
                 # -D warnings, all test suites incl. feature-gated ones, operator
                 # check, headless operator webview check, flutter analyze+test).
                 # Run before every push. It is NOT everything CI runs — see
                 # "What `make ci` does not cover" below.
make launch      # run the app: output window + Tauri operator shell together
make output      # just the native output window (press P to pair a mobile controller)
make operator    # just the Tauri operator shell
make mobile      # run the Flutter controller on this Mac
make mobile-test # flutter analyze + test
make fmt / clippy / test / build   # narrower slices of the above
make nfr         # measure idle-memory / cold-start NFRs on a release build
```

`make launch`/`make run`/`make operator` build the operator with **on-device STT, `dev-keys`, and `openai-notes` all on by default** — `STT ?= auto` detects a local cmake toolchain, `AI ?= auto` (86akcmzyq/86akcmzrd) unconditionally enables the developer `.env` key loader (`dev-keys`) and the direct-to-OpenAI sermon-note path (`openai-notes`), since neither needs a native toolchain. Each prints what it enabled and why (`>> on-device STT: ...`, `>> AI-assisted sermon notes: ...`); force either off with `STT=0`/`AI=0`. This exists because a shipped, merged, four-reviewer-tested feature (FR-122 notes, PR #19) stayed invisible from these exact commands until this fix — do not gate a future AI feature behind an opt-in flag and expect anyone to find it.

**`RELEASE=1` (or `--release`) can never carry `dev-keys`/`openai-notes` through these targets — structurally, not by default.** `make`'s `release-ai-guard` prerequisite refuses (hard `exit 1`, before any cargo command runs) any `RELEASE=1` invocation whose resolved feature list contains either token, including a direct `OP_FEATURES=dev-keys,openai-notes` override — verified by actually running `make operator RELEASE=1 OP_FEATURES=dev-keys,openai-notes` and observing it abort at that prerequisite. That still leaves a bare `cargo build --release --features dev-keys` typed outside Make, so `selahcue-operator/src/dev_env.rs`'s `load()` additionally checks `cfg!(debug_assertions)` and no-ops in any release profile regardless of features requested — verified by building and running a real `--release --features dev-keys,openai-notes` binary and observing it print the refusal rather than reading `.env`. Both guards are mutation-tested (`dev_env.rs`'s `should_load_env_file` tests). Neither guard is airtight against an explicit `[profile.release] debug-assertions = true` or a `RUSTFLAGS` override — nothing in-repo can see either — which is exactly why `scripts/installer_secret_scan.py` (86akc041v) exists as an independent, byte-level check on artefacts this repo actually ships. The one workflow that ships a real installer (`.github/workflows/windows-installer.yml`) never reads `OP_FEATURES`/`AI` at all — it hardcodes its own `cargo tauri build --features stt` — so it is unaffected by this default either way.

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

## Architecture (desktop Rust workspace)

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
- The LAN wire protocol is contract-tested **cross-language**: JSON fixtures in `implementation/mobile/selahcue_controller/test/models/protocol_test.dart` are pinned byte-for-byte by `selahcue-lan/tests/test_protocol.rs` (`wire_fixtures_are_stable_for_cross_language_clients`). Change both sides together.
- Timers/animation take an **injected clock** — keep new time-dependent code deterministic the same way.
- Memory must stay bounded: no unbounded queues/caches/logs; new buffering code gets a bounded-memory test — one that actually bites, see below.
- A SelahCue "theme" is a slide-design template (typography/background/elements, ProPresenter-style) — **not** a light/dark colour mode. See `docs/design/THEME-MODEL-spec.md`.
- CI (`.github/workflows/ci.yml`) path-filters desktop vs mobile vs api vs marketing jobs and skips docs-only changes.
- **The Rust toolchain is pinned in `rust-toolchain.toml`, and that pin is the gate.** rustup reads it for every `cargo`/`rustc` call under the repo (including the two out-of-workspace crates), so `make ci` and CI compile with the same compiler *by construction*; `scripts/check_toolchain.sh` then asserts it, and both gates run that same script first. Before the pin existed, CI installed whatever stable was newest at run time while developers ran whatever they had: on 2026-08-18 stable moved 1.97.1 → 1.98.0, the new `clippy::chunks_exact_to_as_chunks` met `-D warnings`, and `main` went red on the next push and had no green run for nine days while `make ci` kept printing ALL GREEN. Bumping the pin is a normal reviewable change — edit `channel`, run `make ci`, fix what the new lints find, one MR for the bump. `.github/workflows/rust-canary.yml` runs the gates weekly against floating stable and files an issue when a future release would break us, so the pin's deliberate lag stays visible. Never set `channel` to a floating value; the check script refuses it.
- **What `make ci` does not cover** — it is the Rust/Flutter gate on *one* machine, not the whole pipeline. The two biggest gaps are structural and cannot be closed locally:
  - **One OS, not three.** CI runs `rust` and `operator` as a **ubuntu + macOS + Windows** matrix. `make ci` runs whichever one you are sitting at. Cross-OS breaks (path handling, line endings, the vendored-OpenSSL encryption suite that CI skips on Windows) are invisible locally.
  - **A different GPU stack.** The ADR-0015 parity oracle runs on **Metal** on a Mac, **lavapipe** (software Vulkan) on CI's Linux, and **DX12/WARP** on Windows. A local pass says the CPU rasterizer matches *your* GPU, not that it matches the ones CI uses.

  Beyond those, CI also runs `cargo audit` + `cargo deny` (supply chain), the Playwright **WebKit** engine smoke (`scripts/operator_webkit_smoke.py` — the Blink gate in `make ci` cannot catch a WebKit-only break), `launch-smoke` + `make nfr`, the Android APK compile-check, `actionlint` over the workflows, and the **`api (django)` and `marketing (vue spa)` jobs — which `make ci` does not touch at all.** Changing `implementation/api` or `implementation/marketing` and running only `make ci` verifies **nothing** about that change; run those projects' own tooling. Closing this gap is tracked as 86ak5rjh7.
- **`selahcue-stt` is linted by nothing.** It is excluded from the workspace and no CI job references it, so its own `unwrap_used = "warn"` policy is unenforced — it currently has three violations under `-D warnings`. Only `cargo test --manifest-path .../selahcue-stt/Cargo.toml` exercises it, and nothing runs that in CI either. Tracked on 86ak5rjh7.
- **A failing run on `main` opens a `ci-red` GitHub issue** (**live and proven end to end** — run `32933626119` on `main` created [issue #6](https://github.com/First-Pavilion/selahcue/issues/6), the `ci-red` label, and the marker, with `DRY_RUN` correctly false; a `workflow_dispatch` off `main` runs the same job under `DRY_RUN` and writes nothing, which is how to rehearse it safely), and it closes only when every job that was failing has *actually reported success again*. It tracks **which jobs** are outstanding rather than one red/green bit, because CI path-filters by area: an api-only push skips the whole desktop matrix, and a naive alarm would read that skip as "nothing failed" and close itself while `main` was still broken. A **skipped** job is not evidence of anything and never clears the alarm. Logic and its self-test live in `.github/scripts/ci_alarm.py` (`--self-test` runs anywhere, and runs in CI on every `main` push). The repo has no branch protection available on this plan, so nothing prevents a red commit landing — the issue is the only alarm. While one is open, treat every branch's CI result as unreadable: a real failure cannot be distinguished from the standing one.
- Design-doc validators live in `scripts/` (`validate_prd.py`, `validate_goal_contract.py`, `validate_delivery_plan.py`) — run the matching one after editing those artefacts.
- **Masking still exists locally, but less of it than it used to.** Every `cargo test` line in `make ci` and in CI now carries `--no-fail-fast`, so a failure in one crate no longer hides the *other crates'* test results (measured on the real ubuntu CI run: **51 of 138 test suites** sit at or after the failing binary and never report at all without the flag — do not go looking for a second *failing* binary, there is exactly one). What remains is **line-level**: `make ci` still aborts the target at the first failing recipe line, so a clippy failure there still means the feature-gated suites, operator check, headless webview check and Flutter gate never ran at all. CI no longer has that property — its steps after Clippy run under `if: ${{ !cancelled() }}`. So a green `make ci` line is evidence about that line only; after fixing a failure, re-run the whole target rather than assuming the later gates were reached. Closing the line-level gap is tracked as 86ak5rjh7.
- **Run one `make ci` at a time in this checkout.** Concurrent Flutter runs race on `implementation/mobile/selahcue_controller/ios/Flutter/ephemeral/Packages`, which `generatePluginsSwiftPackage` deletes and recreates on every invocation. Two signatures — `Waiting for another flutter command to release the startup lock…` followed by a delete failure, and `FileSystemException: Deletion failed, OS Error: Directory not empty, errno = 66` — are **false reds** (never false greens) and pass on retry with no code change. Check for other active sessions and serialise instead of re-diagnosing them.
- **The checkout is shared**: one worktree on `main`, several agent sessions at once, large uncommitted WIP. Check `ListAgents` and declare your file footprint to peers before starting; never commit, stage, stash or revert another session's work; never `cargo clean` or clear target-dir locks to escape a transient failure.

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
