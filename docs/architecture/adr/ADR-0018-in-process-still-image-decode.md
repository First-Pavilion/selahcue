# ADR-0018 — Bounded in-process still-image (PNG) decode, ahead of the sandbox

- Status: Accepted
- Date: 2026-07-27
- Confidence: High
- Owner: Software Architect + Security Reviewer + Backend Engineer
- Relates: **ADR-0016** (out-of-process sandboxed decode — this ADR refines its *sequencing*, not its end-state), ADR-0005 (media engine), ADR-0015 (testable engine), ARCHITECTURE §7/§11, threat model T12
- Raised by: Stage-8 batch S8-6 (`86ajpzhbc`) — the image render foundation the Canvas Editing image element (`86ajq6j49`) depends on

## Context

ADR-0016 fixes the **end-state** for untrusted media/font decode: an out-of-process, OS-sandboxed decoder worker (macOS App Sandbox/seatbelt; Windows AppContainer/restricted token + job object; Linux seccomp-bpf + namespaces), handing decoded surfaces to the engine over shared memory (ADR-0006). It also distinguishes two properties NFR-024 had conflated: **fault isolation** (a decoder crash must not blank an output) and **security isolation** (a decoder exploit must not compromise the host).

That worker + IPC + per-platform sandbox is a large, spike-S2-gated build. Meanwhile S8-6 needs a **still-image render foundation now** — a `Layer::Image` the deterministic CPU rasterizer can composite (scale + opacity + z-order) with a missing-media placeholder — so the theme image element and image slides can proceed. Shipping nothing until the full sandbox exists would block the whole Canvas Editing image track; shipping an *unbounded* in-process decoder would violate the no-leak rule and NFR-024. ADR-0016 itself names the documented fallback (its "Options considered": "decoder faults are contained by process-restart with a brief placeholder … record the residual security posture for the Stage-13 review").

## Decision

Adopt a **bounded, pure-Rust, in-process still-image decode NOW**, as a deliberate **sequencing refinement** of ADR-0016 — its out-of-process sandbox remains the accepted end-state; this decode boundary is designed so the worker later plugs in unchanged.

1. **Format.** **PNG only** this batch, via the pure-Rust `png` crate (memory-safe, FR-173; lossless → decoded RGBA8 is **byte-identical on every OS**, so the deterministic CPU raster path + golden tests hold, NFR-014). JPEG/WebP/GIF/BMP (FR-066) are **rejected to the missing-media placeholder** and are a documented later-format seam — a platform/HW decoder is explicitly NOT used for stills (it would break NFR-014 byte-parity; those are for video per ADR-0005/0006).
2. **Fault isolation is preserved now.** Decode is `Result`-based and **panic-contained**: a crafted/corrupt/oversize/missing/unsupported image **contains to the missing-media placeholder** (FR-070) — never a blank rect, never a crash — and the runtime `Fault::DecoderFault` still routes through the engine's OutputHeld/last-good-frame contract (NFR-024), unaffected outputs untouched. This is exactly the ADR-0016 fault-handling behaviour, delivered early.
3. **Security isolation is DEFERRED (the seam).** The in-process decoder is net-new attack surface (threat T12). We accept a bounded residual risk now — memory-safe pure-Rust decoder, minimal pinned dependency, header/type/size validation + a format allowlist **before** full decode, and a hard **dimension + decoded-byte budget enforced before allocation** (decompression-bomb defense, FR-173) — and keep ADR-0016's out-of-process sandbox as the end-state. The `Layer::Image` **reference→pixels** boundary is the plug point: a sandboxed worker later supplies the decoded surface in place of the in-process decoder with no scene/API change.
4. **Bounded (no-leak).** Decoded pixels live only in a thread-local cache capped by entry count AND a total-byte budget (a bounded reset on breach; full LRU is NFR-013/R2). Decoded pixels never enter the serde `Frame` — the scene carries only a bounded, validated reference.
5. **Import-path canonicalization (FR-138)** stays a named seam: this batch has no wire/authoring path that accepts an untrusted image path (the theme `Element::Image` is the follow-up `86ajq6j49`), which is where canonicalization + media-root confinement land before accepting a peer/user path.

## Options considered

- **(Chosen) Bounded in-process PNG decode now; sandbox deferred.** Pros: unblocks the image render foundation immediately; preserves fault isolation + determinism + no-leak; small pinned memory-safe dependency; the reference→pixels seam accepts the sandbox unchanged. Cons: a residual in-process security surface until the worker ships (bounded + documented; T12 revisited at the sandbox story / Stage-13).
- **Wait for the full out-of-process sandbox (ADR-0016 end-state) before any image.** Rejected for now: blocks the entire Canvas Editing image track behind the spike-S2 worker + per-platform sandbox; ADR-0016 already sanctions the placeholder-fallback interim.
- **In-process decode with no hard limits / a platform decoder.** Rejected: unbounded decode violates the no-leak rule and enables decompression-bomb OOM; a platform/HW still-image decoder breaks NFR-014 cross-OS byte-parity and the golden tests.

## Consequences

- **Positive:** the image foundation ships on the deterministic CPU path with **no wire/migration/RBAC/GPU change** (the GPU skips `Layer::Image` exactly as it skips `Text` today — GPU-native images are a later batch); fault isolation + FR-070 placeholder + determinism + no-leak are all delivered and tested; the sandbox seam is preserved.
- **Negative:** a bounded residual in-process decode attack surface (threat T12) until the ADR-0016 worker ships; **PNG-only** until the later-format story; a net-new dependency (`png` + `fdeflate`/`flate2`/`miniz_oxide`/…) that the NFR-027 SBOM/RustSec audit now covers.
- **Follow-ups:** ADR-0016 worker + OS sandbox (security isolation); FR-066 additional formats; FR-138 canonicalization at the image-element authoring path (`86ajq6j49`); GPU-native image compositing (with GPU glyphs); remote controller→host asset transfer (a real image cannot ride the 64 KB control frame).

## References

PRD: FR-066/070/138/173, NFR-014/024/027; threat T12. ADRs: 0005, 0006, 0015, **0016**. Goal: `docs/delivery/goals/TASK-86ajpzhbc-image-decode-foundation.md`. Code: `selahcue-engine` (`scene::Layer::Image`, `media`, `raster` blit + placeholder). ClickUp: `86ajpzhbc`.
