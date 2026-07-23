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
    │   └── src/
    │       ├── lib.rs
    │       ├── scripture.rs        # Bible reference parser (FR-027)
    │       ├── plan.rs             # service-plan domain model (FR-001/002)
    │       └── timer.rs            # monotonic timers + TIME UP (FR-054/065, NFR-022)
    └── selahcue-data/             # persistence — SQLite (WAL), migrations, backups
        └── src/
            ├── lib.rs
            ├── db.rs               # open/configure, integrity, checkpoint, backup (FR-079)
            ├── migrations.rs       # versioned, append-only schema migrations
            ├── plan_repo.rs        # ServicePlan persistence (FR-001/002)
            └── error.rs
```

Future crates (subsequent Stage-7 batches, per `../../docs/architecture/ARCHITECTURE.md`):
`selahcue-engine` (wgpu compositor), `selahcue-lan` (WebSocket/TLS control server),
and the Tauri operator shell. At-rest encryption (FR-154) swaps `selahcue-data`'s
`rusqlite` feature to `bundled-sqlcipher` + a key pragma.

## Build & test

```bash
cd implementation/desktop
cargo build
cargo test          # 50 unit tests, all passing
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

Status: **Stage 7 — foundation batches 7a (domain core) + 7b (persistence). Verified:
`cargo test` 50/50, `cargo clippy` clean.** GPU/UI/LAN crates are subsequent batches.
