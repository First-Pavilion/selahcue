# Toolchain

No toolchain was supplied in the prompt, so tools were selected from repository convention. The
guiding principle: reuse what the repo already gates in CI; add nothing that would need to be
maintained separately.

| Dimension | Tool (source) | Scope covered | Measurement boundary | Limitations |
| --- | --- | --- | --- | --- |
| Render / cue-trigger latency | `cargo test --release` timing tests (repo convention) | Compose + CPU rasterize at 1920×1080; Stage→Live | In-process `Instant` around `go_live()` / controller `apply()` | Excludes GPU present + OS window swap (that path is measured for correctness by GPU parity, not timed) |
| Rendering correctness under the fast path | `selahcue-gpu` parity test (repo convention) | wgpu compositor vs CPU rasterizer | Offscreen readback SSIM | GPU-present frame pacing not timed |
| Memory bounds / leak detection | Per-crate bounded-memory + flood tests (repo convention) | Every queue/cache/ring/log on hot + long-running paths | Cap assertions after adversarial floods | Static + test-driven; not a running-process RSS soak (see NFR gap) |
| Concurrency / streaming | `selahcue-lan --features server` loopback E2E (repo convention) | Connection lifecycle, session caps, half-open reaping | Real TLS WebSocket over loopback | Loopback only; no WAN shaping |
| At-rest encryption cost | `selahcue-data --features encryption` E2E (repo convention) | SQLCipher open/migrate/backup | Functional + bounded | Not a throughput benchmark |
| STT real-time cost | `selahcue-stt` pipeline + bounded tests (repo convention) | Framing, VAD, interim/final emission, backpressure | Injected-clock determinism | Recognizer is the test stub; whisper RTF is analysed statically (see bottleneck #1) |
| Idle memory / cold start NFR | `scripts/measure_nfr.sh` (repo convention) | Idle RSS ≤300 MB, cold start ≤3 s | Live process RSS + wall-clock to first frame | **Needs a display; owner-run — not executed headless this session** |
| Whole-codebase hot-path audit | Independent static scan (fresh-context subagent) | Every buffering site + hot loop, all crates | Source-level `file:line` evidence | Static reasoning about RTF/allocation, not a sampling profiler run |

## Coverage gaps (explicit)

1. **Live-process RSS soak / cold-start** — deferred to owner-run `make nfr` (GUI display required).
2. **Sampling profiler (py-spy/perf-style flamegraph)** — not run; the workspace is small and pure, and
   the static hot-path scan + timing tests localised cost precisely enough for this gate. A profiler run
   is the natural next step only if a follow-up (bottleneck #1/#2) is picked up for optimisation.
3. **WAN/network-shaped LAN latency** — out of scope; LAN peers are same-network by design (ADR-0008).

## Rejected alternatives

- **k6 / Locust / Artillery / JMeter** — rejected: there is no hosted HTTP/service surface to load. The
  only network surface is a same-network, single-operator control channel already E2E-tested in-repo.
- **Adding Criterion benches** — rejected for this gate: the repo already encodes budgets as pass/fail
  release tests, which double as CI regression gates. Adding a parallel bench harness would duplicate
  intent without adding a decision-relevant signal now. Flagged as a follow-up if #1/#2 are optimised.
