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
make ci          # the FULL local CI gate (fmt --check, clippy -D warnings, all test
                 # suites incl. feature-gated ones, operator check, headless operator
                 # webview check, flutter analyze+test). Run before every push —
                 # CI has a cargo fmt --check gate.
make launch      # run the app: output window + Tauri operator shell together
make output      # just the native output window (press P to pair a mobile controller)
make operator    # just the Tauri operator shell
make mobile      # run the Flutter controller on this Mac
make mobile-test # flutter analyze + test
make fmt / clippy / test / build   # narrower slices of the above
make nfr         # measure idle-memory / cold-start NFRs on a release build
```

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
# Tauri operator shell (GUI; heavy toolchain deps). CI only compile-checks it:
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
- CI (`.github/workflows/ci.yml`) path-filters desktop vs mobile jobs and skips docs-only changes; `make ci` is the local mirror of its gates.
- Design-doc validators live in `scripts/` (`validate_prd.py`, `validate_goal_contract.py`, `validate_delivery_plan.py`) — run the matching one after editing those artefacts.
- **`cargo test --workspace` fail-fasts** (no `--no-fail-fast` anywhere), and so does `make ci` — each recipe line aborts the target. A failure in the `--workspace` line means the feature-gated suites, operator check, headless webview check and Flutter gate never ran at all. A green `--workspace` after a fix is therefore not evidence the *later* crates passed: re-verify the specific crate too.
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
