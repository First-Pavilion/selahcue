# ADR-0015 — Testable rendering engine (headless render, determinism, fault injection)

- Status: Accepted
- Date: 2026-07-23
- Confidence: High
- Owner: Software Architect
- Supersedes/relates: ADR-0002 (wgpu compositor), ADR-0006 (HW-decode interop)
- Raised by: Stage-5 independent review **B2** (blocker), **M6**, **M7**

## Context

SelahCue's headline reliability guarantees — "no component failure blanks or clears live output" (NFR-024), bounded GPU/decoder recovery (FR-160), slide-trigger latency (NFR-004/METRIC-002), seizure-safe flashing (FR-175), and cross-platform render parity (NFR-014) — all live in the bespoke Rust + wgpu compositor (ADR-0002). A rendering engine with no automated way to observe its output, no deterministic mode, and no way to inject faults **cannot have those guarantees verified**, and cross-platform parity would have no oracle. The Stage-5 review correctly flagged this as a day-one commitment: these seams must exist from the engine's first line of code, not be retrofitted.

## Decision

The render engine is built with a **test harness contract** as a first-class, non-optional part of its design:

1. **Headless / offscreen render path.** The compositor can render any scene to an offscreen wgpu texture and **read the pixels back** to CPU (RGBA), independent of a physical display. Every output window and the offscreen path share the same scene-graph and render code (no test-only render path divergence).
2. **Deterministic render mode.** A mode that drives the render loop from an injected, fixed monotonic clock and fixed random seed, producing **byte-reproducible frames on the same GPU/driver** for a given scene + timeline. For **cross-OS/GPU parity** (NFR-014/METRIC-010), byte-equality is infeasible across GPU vendors — so the parity oracle is a **perceptual comparison** against a committed reference render: **SSIM ≥ 0.99** (with a small per-pixel ΔE tolerance for anti-aliasing/subpixel differences), not byte-equality. The pass/fail tolerance is versioned with the reference set.
3. **Fault-injection hooks.** Programmatic injection of: GPU device-loss/reset, decoder failure, IPC stall between UI and engine, and disk-full on the autosave path — so NFR-024/FR-160 recovery can be asserted (affected output holds last frame; other outputs unaffected; bounded recovery time).
4. **Frame-capture + analysis.** Capture consecutive frames and compute (a) a **flash-rate / luminance-and-red transition analyzer** to assert FR-175 (≤3 flashes/sec, plus red-flash and flashing-area sub-criteria), and (b) an **input-to-photons latency proxy** — timestamp from the injected control event to the first frame whose readback contains the new content — to measure NFR-004/METRIC-002. FR-013's preview-capture point is the offscreen readback of the preview scene.
5. **Drivable render↔control IPC contract.** A documented, versioned command interface (set-scene, go-live, clear, blackout, timer-tick, inject-fault, capture-frame) that both the real UI/control plane and the test harness use. This is the single seam for engine tests and for the UI↔engine boundary (ADR-0003).

## Options considered

- **(Chosen) Build the test contract into the engine from day one.** Pros: the reliability invariants become verifiable; deterministic cross-platform parity oracle; latency/flash measurement is real, not asserted. Cons: modest up-front engine-design cost; discipline to keep offscreen and on-screen paths unified.
- **Retrofit testing later.** Rejected: a compositor not designed for readback/determinism is extremely hard to make testable afterwards, and the invariants would ship unverified — exactly the B2 risk.
- **Rely on manual/visual QA only.** Rejected: not repeatable, no cross-platform oracle, cannot catch regressions in CI.

## Consequences

- **Positive:** NFR-024, FR-160, FR-175, NFR-004, NFR-014 become automatically testable in CI (feeds Stage-8/12). The IPC contract also de-risks the ADR-0003 WebView↔engine preview (streamed downscaled readback is the same readback the tests use).
- **Negative:** the engine must keep the offscreen and on-screen render paths unified and expose fault hooks even in release builds (gated/segregated to avoid abuse). Small runtime cost for the capability, none when idle.
- **Commits us to:** a **GPU-hardware CI matrix** (M7) — one runner per interop backend (VA-API/Linux, NVDEC/NVIDIA, Metal/macOS, D3D11/Windows) running the deterministic parity + device-loss-recovery assertions; **wgpu is pinned** and version upgrades are gated on re-running that matrix.
- **Benchmark-harness spec (M6):** the latency proxy, preview-capture point, and flash-rate analysis method above are the normative measurement definitions for METRIC-002/NFR-004 and FR-175; the Stage-5/12 performance harness implements them.

## References

PRD: NFR-024, FR-160, FR-175, NFR-004/014, METRIC-002, FR-013. ADRs: 0002, 0003, 0006. Review: ARCH-UX-REVIEW-stage5 B2/M6/M7.
