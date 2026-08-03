# Environment

## Measurement host (this session)

| Field | Value |
| --- | --- |
| Machine | Apple M5, 10 cores (4P + 6E), 16 GB unified memory |
| OS | macOS 26.3 (Darwin 25.3.0) |
| Toolchain | rustc 1.97.1 (8bab26f4f 2026-07-14) |
| Display | none attached (headless) — bounds the GUI NFRs (M18/M19) |
| Build | `--release` for latency/parity; default profile (feature-gated) for bounded/E2E/encryption/STT |

## Feature flags exercised

- `selahcue-lan --features server` — TLS-pinned WebSocket transport + loopback E2E.
- `selahcue-data --features encryption` — SQLCipher at-rest.
- `selahcue-stt` — pure-Rust pipeline (recognizer stub; `whisper`/`capture` native features off).
- `selahcue-gpu` — wgpu compositor (parity path; skips gracefully with no GPU, present here).

## Repeatability

- All suites are deterministic (injected clocks, seeded/fixed inputs, offscreen readback).
- Commands are recorded verbatim in `03-suite/EXECUTION-COMMANDS.md` and re-runnable via the root `Makefile`.
- The local mirror of CI gates is `make ci`; the release latency/parity numbers use explicit
  `cargo test --release -p <crate>` invocations.

## Environment differences that matter

- **Release vs debug** — the product latency budgets are release-build NFRs; debug carries a generous
  tripwire (1500 ms / 2000 ms) because oversubscribed CI runners measure the runner, not the product.
  This review reports release numbers.
- **Headless vs GUI** — idle-RSS and cold-start need an attached display; the same harness (`make nfr`)
  run by the owner on a display closes M18/M19.
- **Local vs CI runner** — observed CI raster is several-fold slower on shared runners (documented inline
  in the tests); the release budgets are enforced where the numbers are trustworthy.

## Emergency-stop / safety

Not applicable — no production or third-party system is touched. All tests are in-process or loopback.
