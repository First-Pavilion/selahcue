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
    └── selahcue-lan/              # LAN control core — protocol, RBAC, pairing/sessions
        ├── src/                    # lib.rs, protocol.rs, rbac.rs, session.rs
        └── tests/                  # test_protocol.rs, test_rbac.rs, test_session.rs
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

The transport-independent core of the operator↔controller link (FR-118/119/120;
ADR-0009): the wire **protocol** (versioned JSON messages), **RBAC** (roles →
permissions with a single `authorize()` choke point), and **session** management
(single-use, TTL-bounded device pairing → constant-time-authenticated bearer tokens).
Pure and exhaustively testable; the TLS-pinned WebSocket transport that carries these
messages is a subsequent batch.

Status: **Stage 7 — foundation batches 7a (domain core) + 7b (persistence) + 7c
(at-rest encryption) + 7d (LAN control core). Verified: `cargo test` 80/80 (plain) +
16/16 (encryption), `cargo clippy` clean.** GPU/UI crates, the LAN TLS transport, and
app-shell key acquisition are subsequent batches.
