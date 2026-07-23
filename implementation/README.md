# SelahCue — Implementation

Production code for SelahCue. Planning/product artefacts live in [`../docs/`](../docs/); ClickUp is the delivery source of truth.

## Layout

```
implementation/
├── Cargo.toml                     # Rust workspace
└── crates/
    └── selahcue-core/             # domain core — pure, deterministic, no I/O
        └── src/
            ├── lib.rs
            ├── scripture.rs        # Bible reference parser (FR-027)
            ├── plan.rs             # service-plan domain model (FR-001/002)
            └── timer.rs            # monotonic timers + TIME UP (FR-054/065, NFR-022)
```

Future crates (subsequent Stage-7 batches, per `docs/architecture/ARCHITECTURE.md`):
`selahcue-engine` (wgpu compositor), `selahcue-data` (SQLite/SQLCipher), `selahcue-lan`
(WebSocket/TLS control server), the Tauri operator shell, and the Flutter mobile app.

## Build & test

```bash
cd implementation
cargo build
cargo test          # 33 unit tests, all passing
cargo clippy --all-targets   # clean
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

Status: **Stage 7 — foundation batch 7a (domain core). Verified: `cargo test` 33/33,
`cargo clippy` clean.** GPU/UI/persistence/mobile crates are subsequent batches.
