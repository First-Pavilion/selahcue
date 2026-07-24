# SelahCue — Desktop

The Windows/macOS/Linux operator application: a Rust workspace pairing a pure,
deterministic domain core with a wgpu compositor and a Tauri operator shell
(ADR-0002). This is the only buildable platform today.

## Layout

```
desktop/
├── Cargo.toml                     # Rust workspace
└── crates/
    ├── selahcue-core/             # domain core — pure, deterministic, no I/O
    │   ├── src/                    # lib.rs, scripture.rs, plan.rs, timer.rs
    │   └── tests/                  # test_scripture.rs, test_plan.rs, test_timer.rs
    ├── selahcue-data/             # persistence — SQLite (WAL), migrations, backups
    │   ├── src/                    # lib.rs, db.rs, migrations.rs, plan_repo.rs, key.rs, error.rs
    │   └── tests/                  # test_db.rs, test_plan_repo.rs, test_encryption.rs
    ├── selahcue-lan/              # LAN control — protocol, RBAC, pairing + TLS transport
    │   ├── src/                    # protocol.rs, rbac.rs, session.rs; (server feature:)
    │   │                          #   pinning.rs, tls.rs, server.rs, client.rs, wire.rs
    │   └── tests/                  # test_protocol/rbac/session/server (server → loopback E2E)
    ├── selahcue-engine/           # render-engine test seam (ADR-0015) — GPU-free
    │   ├── src/                    # scene.rs, raster.rs, analysis.rs, fault.rs, engine.rs
    │   └── tests/                  # test_scene/raster/analysis/fault/engine
    ├── selahcue-present/          # presentation — Preview→Live + stage/confidence output
    │   ├── src/                    # slide.rs, compose.rs, present.rs, stage.rs
    │   └── tests/                  # test_slide/compose/present/stage
    ├── selahcue-gpu/              # wgpu compositor (ADR-0002) + offscreen SSIM parity
    │   ├── src/                    # compositor.rs, rect.wgsl, lib.rs
    │   └── tests/                  # test_parity.rs (GPU ≈ CPU, SSIM ≥ 0.99)
    ├── selahcue-desktop/          # native output window (winit + wgpu) — bin: selahcue-output
    │   └── src/                    # main.rs, blit.wgsl
    └── selahcue-app/              # LiveController — wires LAN control onto the presenter
        ├── src/                    # controller.rs, lib.rs
        └── tests/                  # test_controller.rs, test_remote.rs (server → E2E)
```

Tests live in each crate's `tests/` folder (one file per module, public-API
integration tests). The single exception is one white-box test that reads the private
scripture `BOOKS` table — it stays inline in `src/scripture.rs`, because integration
tests cannot reach crate-private items.

Future crates (subsequent Stage-7 batches, per `../../docs/architecture/ARCHITECTURE.md`):
`selahcue-engine` (wgpu compositor), the TLS-pinned WebSocket transport that carries the
`selahcue-lan` messages, and the Tauri operator shell.

## Build & test

```bash
cd implementation/desktop
cargo build
cargo test                                    # 50 tests (plain build), all passing
cargo clippy --all-targets                    # clean
# At-rest encryption (FR-154) — compiles SQLCipher + vendored OpenSSL:
cargo test  -p selahcue-data --features encryption   # 16 tests, all passing
cargo clippy -p selahcue-data --all-targets --features encryption   # clean
```

## `selahcue-core`

The side-effect-free domain foundation the rest of the app builds on. Kept pure so
it is exhaustively unit-testable and safe on untrusted input (the parser never
panics — it returns `Result`/`Option`).

- **`scripture`** — parses typed references (`"Romans 8:28"`, `"Rom 8:28-30"`,
  `"Ps 23"`, `"1 Cor 13:4"`, `"Jn 3:16"`, `"John 3:16; 1 Cor 13:4"`) across all 66
  books with abbreviations and numbered/roman/word forms; malformed input errors
  cleanly.
- **`plan`** — `ServicePlan` with add/insert/remove/reorder/duplicate, stable
  never-reused item ids, and planned-time roll-up.
- **`timer`** — monotonic `Timer` (count-up / count-down) driven by an **injected
  clock** so it is frame-rate-independent (NFR-022) and deterministic to test;
  supports pause/resume/reset/add/subtract, TIME UP, and overrun.

## `selahcue-data`

The persistence layer: a WAL-configured SQLite database (via `rusqlite` `bundled`,
so it compiles with no system libraries), versioned append-only migrations, integrity
checks, crash-safe online backups (FR-079; ADR-0007), and repositories that map the
pure `selahcue-core` types to tables and back.

- **`db`** — open/configure (WAL, `synchronous=NORMAL`, foreign keys on), schema
  version, `integrity_check`, WAL checkpoint, and `backup_to` via SQLite's online
  backup API. Refuses to open a database written by a newer schema than it understands.
- **`migrations`** — forward-only migrations tracked in `user_version`, each applied
  in its own transaction (crash-safe); append a SQL string to add one.
- **`plan_repo`** — transactional insert/load/list/delete of `ServicePlan`,
  preserving item order (unique `ord` + tie-breaker) and the id counter; unknown
  enum tags and out-of-range stored integers surface as `Corrupt`, never a panic.
- **`key`** *(`encryption` feature)* — at-rest encryption (FR-154): the feature
  compiles SQLCipher (vendored OpenSSL), and `EncryptionKey` applies a 256-bit raw key
  via `PRAGMA key`. `Database::open_encrypted` / `open_in_memory_encrypted` and
  `backup_to_encrypted` are compiled **only** with the feature, so a keyless
  "encrypted" open is impossible. Key derivation/storage (OS secret store; Argon2id on
  Linux) is the app shell's responsibility (ADR-0007).

## `selahcue-lan`

The operator↔controller link (FR-118/119/120; ADR-0009). The default build is the pure,
transport-independent **core**: the wire **protocol** (versioned JSON messages), **RBAC**
(roles → permissions with a single `authorize()` choke point), and **session** management
(single-use, TTL-bounded device pairing → constant-time-authenticated bearer tokens).

The **`server` feature** adds the TLS-pinned WebSocket **transport** (pure-Rust rustls +
`ring`): `pinning` (a rustls verifier trusting the operator's self-signed cert by SHA-256
pin, while still verifying the handshake signature), `tls` (rcgen self-signed cert +
configs), and `server`/`client`. It is time-boxed (handshake/auth timeout), connection-
capped (semaphore), and frame-size bounded — so hostile LAN peers cannot exhaust it.

```bash
cargo test -p selahcue-lan --features server   # + loopback TLS E2E (pinning, auth, RBAC)
```

## `selahcue-engine`

The render engine's **test-harness contract** (ADR-0015), built GPU-free so the
reliability guarantees are verifiable before the wgpu backend exists: a deterministic
CPU **rasterizer + pixel readback**, **fault injection** proving the never-blank output
guarantee (NFR-024 — a fault holds the last good frame), the **FR-175 flash-rate
analyzer** (worst 1-second window, per spatial tile), the **NFR-004 latency proxy**, and
the versioned **render↔control IPC contract**. The wgpu backend renders the same
`scene::Frame` later, with SSIM ≥ 0.99 cross-GPU parity.

## `selahcue-present`

Basic presentation rendering on the engine seam (FR-009/012/013/046): compose static
**slides** (`Slide` + audience `Theme`) into engine frames, and drive the **Preview→Live**
loop via `Presenter`. Its core invariant — **staging never changes Live; only Go Live
(`Enter`) does** — plus clear (`Esc Esc`), blackout toggle+restore (`B`), and the offscreen
preview readback, are all verified headlessly (preview/live isolation, ≤150 ms slide-trigger
latency, flash-safety). The operator's green/red preview/live chrome and the borderless
fullscreen output window are the operator-console/walking-skeleton UI batch.

The **`stage`** module adds the **stage/confidence monitor** — a second independent output
showing the current + next line, the active timer (colour-coded ok/warn/TIME-UP with a
progress bar), and a clock — plus the **display-identify** overlay (a number per physical
display). It composes the timer core + presenter, so main and stage show different content
from one live state.

## `selahcue-gpu` / `selahcue-desktop`

The walking skeleton's render half. **`selahcue-gpu`** is the wgpu compositor (ADR-0002):
it renders the engine's `scene::Frame` on the GPU, with an offscreen path whose pixel
readback is checked against the CPU rasterizer at **SSIM ≥ 0.99** (the ADR-0015 cross-GPU
parity oracle — runtime-verified on Metal). **`selahcue-desktop`** is a native output
window (winit + wgpu surface) that presents the presenter's live output:

```bash
cargo test  -p selahcue-gpu       # GPU↔CPU parity (skips if no GPU)
cargo run   -p selahcue-desktop   # opens the native output window (needs a display)
```

Slide text renders as **real glyphs** (a bundled public-domain 8×8 bitmap font in the CPU
rasterizer via `Layer::Text`), so the output window shows legible text; GPU-native glyphs
are a later optimization.

## `selahcue-app`

The application wiring: **`LiveController`** maps RBAC-checked LAN control commands onto the
presenter + service plan, so a remote/mobile controller drives the audience output — the
complete loop (client → TLS → server RBAC → handler → controller → presenter). With the
`server` feature, `handler_for` plugs it into the `ControlServer`, verified end-to-end.

Status: **Stage 7 — foundation batches 7a (domain core) + 7b (persistence) + 7c
(at-rest encryption) + 7d (LAN control core) + 7e (TLS transport) + 7f (render-engine
seam) + 7g (presentation rendering) + 7h (stage/confidence output) + 7i (wgpu compositor +
native window) + 7j (glyph text) + 7k (LAN control → presenter) + 7l (window ← remote
control) + 7m (Tauri operator shell) + 7n (operator ↔ output wiring) + 7o/7p (timers on
the stage/confidence second window) + 7q (QR pairing + the Flutter mobile client, in
`../mobile/`). Verified: `cargo test` 198 workspace (incl. GPU parity) + 16 (encryption)
+ 50 (LAN server, incl. 6 pairing E2E) + operator/remote E2E, `cargo clippy` clean;
`flutter analyze`/`test`/`build macos` clean.** CI and app-shell key acquisition are
subsequent batches. Run everything: `make launch` (see the repo-root Makefile) — press
`P` in the output window to pair a mobile controller (grants **Producer** control after
the host confirms with `Y`).
