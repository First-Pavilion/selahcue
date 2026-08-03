# Execution Commands

All commands run from `implementation/desktop/` unless noted. The root `Makefile` wraps manifest paths and
feature flags — prefer it for the full gate.

## Full local gate (mirror of CI)

```bash
make ci   # fmt --check, clippy -D warnings, all suites incl. feature-gated,
          # operator compile-check, headless operator webview check, flutter analyze+test
```

## Latency (release — product NFRs are release budgets)

```bash
# Stage->Live distribution at 1080p (prints [AUDIT] median/p90/max)
cargo test --release -p selahcue-app --test test_controller \
  scripture_stage_to_live_latency_is_measured -- --nocapture --exact

# Slide-trigger + longest-verse auto-fit budgets (150 ms release)
cargo test --release -p selahcue-present --test test_present -- go_live

# Keyword search 500 ms budget
cargo test --release -p selahcue-scripture --test test_scripture_data \
  keyword_search_meets_the_500ms_budget -- --exact
```

## Render correctness (GPU↔CPU parity, SSIM ≥ 0.99)

```bash
cargo test --release -p selahcue-gpu   # test_parity: 2 passed (skips cleanly with no GPU)
```

## Memory bounds / leak (default profile)

```bash
cargo test -p selahcue-core   --test test_transcript
cargo test -p selahcue-core   --test test_detection
cargo test -p selahcue-engine --test test_raster
cargo test -p selahcue-engine --test test_media
cargo test -p selahcue-present --test test_present
cargo test -p selahcue-present --test test_tokens
```

## Concurrency / streaming (feature `server`, loopback TLS E2E)

```bash
cargo test -p selahcue-lan  --features server         # server, session, pairing, protocol, rbac, remote
cargo test -p selahcue-app  --features server         # controller, operator_remote, operator, quote_detection, remote
```

## At-rest encryption (feature `encryption`)

```bash
cargo test -p selahcue-data --features encryption
```

## STT pipeline (excluded root)

```bash
cargo test --manifest-path crates/selahcue-stt/Cargo.toml   # incl. bounded_memory.rs + 2 interim tests
```

## Idle memory / cold start NFR (owner-run — needs a display)

```bash
# From repo root, on a machine with an attached display:
make nfr    # measures idle RSS (<=300 MB) and cold start (<=3 s) on a release build
```
