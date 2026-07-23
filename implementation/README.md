# SelahCue — Implementation

Production code for SelahCue, split by delivery platform for separation of concerns.
Planning/product artefacts live in [`../docs/`](../docs/); ClickUp is the delivery
source of truth.

## Platform layout

```
implementation/
├── desktop/     # Windows/macOS/Linux operator app — Rust core + wgpu engine + Tauri shell
├── web/         # browser-based control surface (planned)
└── mobile/      # Android/iOS controller — Flutter (planned)
```

Each platform folder is self-contained and owns its own toolchain and build:

| Folder      | Stack                                             | Status                          |
|-------------|---------------------------------------------------|---------------------------------|
| `desktop/`  | Rust workspace (`selahcue-core`, `selahcue-data`, …) | **Active** — Stage 7 foundation |
| `web/`      | TBD (see `web/README.md`)                          | Placeholder — later release     |
| `mobile/`   | Flutter/Dart (see `mobile/README.md`)              | Placeholder — later release     |

### Why this split

The three targets have different toolchains (Cargo vs. Flutter vs. a web bundler),
release cadences, and CI matrices, so keeping them in separate roots stops one
platform's build config from leaking into another. The pure domain logic
(`selahcue-core`) currently lives under `desktop/` because that is its only consumer
today; if `web` (via WASM) or `mobile` (via FFI/uniffi) later need to share it, it is
hoisted into a top-level `shared/` workspace at that point — an explicit, traceable
decision rather than a premature abstraction.

At-rest encryption (FR-154) is implemented in `desktop/`'s `selahcue-data` behind an
`encryption` feature (SQLCipher); key acquisition from the OS secret store is app-shell
work for a later batch.

## Getting started

See each platform's own README:

- [`desktop/README.md`](desktop/README.md) — the only buildable code today.
- [`web/README.md`](web/README.md)
- [`mobile/README.md`](mobile/README.md)
