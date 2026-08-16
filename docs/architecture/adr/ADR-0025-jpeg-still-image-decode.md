# ADR-0025 — JPEG still-image decode, and what the determinism contract becomes

- Status: Proposed (for review)
- Date: 2026-08-15
- Confidence: High on the format-agnostic seam, the variant matrix and the determinism contract (all structural and test-verifiable). Medium on the crate pick — the criteria are firm, but two properties of the chosen crate must be confirmed at the pinned version before work starts.
- Owner: Software Architect, with Backend Engineer (delivery) and Security Reviewer (bounds)
- **Amends ADR-0018.** ADR-0018 remains accepted in full for its posture — bounded, panic-contained, pure-Rust, in-process decode with the ADR-0016 sandbox as the deferred end-state. Only its "**PNG only this batch**" format scope is superseded, and it is superseded by exactly the mechanism ADR-0018 itself named: "a documented later-format seam".
- Relates: ADR-0016 (out-of-process sandbox, still deferred), **ADR-0018**, ADR-0024 (presentation import, the requesting feature), ADR-0002/0015 (deterministic render + parity oracle), ADR-0020 (image elements)
- Security: `docs/security/THREAT-MODEL-presentation-import.md`. Its blocker **B5 currently lists JPEG in the drop-and-report set; this decision supersedes B5 for JPEG only.** Every other format B5 excludes stays excluded, and every bound B5 requires is preserved or tightened.
- Requirements: FR-066 (media formats), FR-070 (placeholder, never blank), FR-173 (decode hardening), NFR-014 (cross-OS byte parity), NFR-024 (never blank), NFR-027 (SBOM/licence, `86ajpew0j`)

---

## Context

`selahcue-engine::media` decodes **PNG only**. `decode_png` rejects everything else at an 8-byte signature check, returning `DecodeError::Unsupported`, which ADR-0018 records as "a documented later-format seam". That was the right call for the image-render foundation: PNG is lossless and spec-defined, so any conformant decoder produces identical RGBA8, which keeps the deterministic CPU raster path and its golden tests stable across operating systems.

Presentation import (ADR-0024) breaks the assumption that made PNG-only comfortable. Embedded images in real PowerPoint decks are predominantly JPEG. Built against today's decoder, the owner's approved "text plus images" scope would import a normal photographic deck's text perfectly and skip most of its images — accurate under the partial-import model, and indistinguishable from broken to the person reading the report.

The owner considered shipping text-only first, shipping PNG-only images with an honest drop report, and adding JPEG decode as part of this work. **The owner chose to add JPEG decode.** This ADR records how, and what it costs.

Two other realities force decisions that are easy to leave implicit and expensive to get wrong: `deck_import_image` already offers a `jpg`/`jpeg` file filter it cannot honour, so JPEGs picked there render as the missing-media placeholder today; and JPEG is not one format but a family, several members of which produce *plausible but wrong* output rather than an obvious failure.

---

## Decisions

### 1. The bounded discipline becomes format-agnostic, not PNG-shaped with JPEG bolted on

`decode_image(bytes, &DecodeLimits)` replaces `decode_png` as the entry point, with `sniff(bytes) -> Option<ImageFormat>` doing magic-byte detection and **never** consulting an extension. Every present and future format passes through one fixed order:

1. non-empty; 2. encoded-byte cap; 3. signature allowlist; 4. **header-only read, no pixel allocation**; 5. reject unsupported variants from the header; 6. dimension caps; 7. megapixel cap; 8. decoder-native second-line budget; 9. allocate and decode; 10. normalise to RGBA8; 11. apply EXIF orientation.

Steps 4–7 are what stop JPEG bypassing the pre-allocation cap by learning its dimensions later: the chosen crate exposes width, height and pixel format from `read_info()` before any pixel work, so the existing PNG discipline transfers exactly rather than being re-invented. Step 8 is the belt to step 7's braces and matters most for progressive JPEG, whose intermediate coefficient storage scales with image size during decode and can exceed the output buffer.

`DecodeError` gains `UnsupportedColour` and `UnsupportedVariant` so the import report can say *why* rather than collapsing every rejection into "unsupported".

### 2. `jpeg-decoder`, pinned, with `rayon` off

| Criterion | `jpeg-decoder` | `zune-jpeg` |
|---|---|---|
| Licence | MIT / Apache-2.0 | MIT / Apache-2.0 |
| Maintainer | image-rs — **the same organisation as `png`, which we already depend on** | newer, smaller |
| Unsafe | none on stable; SIMD behind an opt-in nightly feature we do not enable | hand-written `unsafe` SIMD with runtime dispatch |
| Determinism | one code path everywhere | decode path differs by CPU |
| Speed | slower | faster |

The decisive criteria are the middle two, not speed — we decode once at import and cache, so throughput is not a constraint. **Runtime SIMD dispatch is actively harmful here**: the same binary can produce different pixels on a machine with AVX2 than without, which is not merely a cross-OS difference but a cross-CPU one, and would break byte-identical golden tests in a way that reproduces only on some CI runners. Choosing image-rs also keeps the whole still-image decode surface under one maintainer, one release cadence and one advisory feed to track under NFR-027.

**Confirm before starting** (the contract in decision 3 is what must hold; the crate serves it, not the reverse): that the pinned version is scalar-only on stable with no runtime dispatch, and that `read_info()` and a decoding-buffer limit exist with the semantics above.

### 3. The determinism contract is restated — and the reason must be understood, not just the wording

ADR-0018's argument was that PNG is lossless and spec-defined, so *any* conformant decoder agrees, so decoded RGBA8 is byte-identical everywhere. **That argument does not transfer, and no crate choice can make it transfer.** The JPEG specification defines the bitstream, not an exact inverse DCT; it permits IDCT implementations within an accuracy tolerance, and chroma upsampling is likewise a choice. Two conformant decoders will legitimately disagree by ±1 in places, and so will two versions of one decoder whose IDCT changes.

But SelahCue never needed format-inherent agreement. It needs *our build* to produce the same pixels everywhere, so that golden tests and cross-OS parity mean something:

> **Determinism contract.** For a **pinned decoder version**, decoding the same bytes yields byte-identical RGBA8 on every supported OS and CPU. For PNG this is guaranteed by the format. For JPEG it is a property of the pinned crate, not of the format.

Three obligations follow:

- **JPEG decode joins the pinned-and-gated set.** The repository already has this pattern and states it: wgpu is pinned and upgrades are gated on re-running the parity matrix (ARCHITECTURE §12). A `jpeg-decoder` bump becomes a golden-test-affecting change, recorded beside the wgpu pin so it is never treated as a routine dependency update.
- **No runtime code-path selection** — scalar only, no SIMD dispatch, no `rayon`.
- **The contract is tested, not asserted.** A determinism test decodes a committed benign JPEG and asserts a pinned hash of the RGBA output, across the existing CI matrix, so an x86-64/aarch64 divergence fails on the day it becomes true rather than months later in a golden diff.

**The GPU↔CPU SSIM ≥ 0.99 parity oracle is unaffected**, for two reasons in increasing order of durability. Today the GPU compositor does not render `Layer::Image` at all — ADR-0018 records that it skips images exactly as it skips text — so no image enters the comparison. More durably: when GPU-native image compositing lands, **both paths must consume the same decoded RGBA buffer produced once upstream**, so the decoder's choices are common-mode and cancel exactly. The oracle compares rasterisers, not decoders. It would be affected only if the GPU path ever decoded independently, which it must not — recorded here as a constraint on the future GPU-image story rather than discovered then.

**No existing golden test needs regenerating**, because no golden contains a JPEG — JPEG cannot currently decode. The real regression surface is every test asserting JPEG is *rejected*: a `DecodeError::Unsupported` assertion on JPEG bytes, or a missing-media-placeholder assertion for a `.jpg` reference. Those flip from "rejected" to "decoded" and must be updated deliberately, not deleted when they turn red. That grep is the change's true blast radius.

### 4. The variant matrix is decided up front, and favours an honest skip over wrong pixels

| Variant | Decision |
|---|---|
| Baseline sequential (SOF0) and extended sequential (SOF1), 8-bit YCbCr | **Supported** |
| **Progressive (SOF2), 8-bit** | **Supported** — very common from "save for web" and web-sourced photos; a user cannot see the difference, so skipping it would look arbitrary |
| Grayscale (1 component) | **Supported**, expanded to RGBA |
| **CMYK / YCCK (4 components, Adobe APP14)** | **Dropped and reported** |
| **EXIF orientation (APP1 tag 0x0112, values 1–8)** | **Supported, applied at decode** |
| ICC colour profiles | **Ignored**; pixels treated as sRGB, consistent with the rest of the pipeline. Not reported — not a loss a user would recognise |
| 12-bit / 16-bit precision, arithmetic-coded (SOF9–11), lossless (SOF3) | **Dropped and reported** |
| Truncated or corrupt | **Dropped and reported — never a partial image** |

Two of these are the load-bearing ones.

**CMYK is dropped because converting it without the embedded ICC profile produces plausible-but-wrong colour, and Adobe's inverted-value convention makes photo-negative output a live possibility.** These are common in print-oriented decks. A visible "CMYK images aren't supported" beats a wrong-coloured photograph in front of a congregation; this product's principles do not permit silently wrong output. Whether that trade is right for our users is the one product judgement in this ADR, and it is routed to Priya rather than assumed.

**Truncated JPEGs are skipped rather than partially rendered**, because some decoders return what they got, and a photo that is correct on top and grey on the bottom is worse on an audience screen than a placeholder.

### 5. EXIF orientation is applied inside the decoder, by a hand-rolled single-tag reader

Ignoring orientation imports photographs sideways, which is common, obvious and embarrassing. Applying it inside `decode_image` means every consumer — import, the canvas image element, `deck_import_image` — gets upright pixels with no schema change, no new `Element` field, and no per-callsite discipline to forget.

A hand-rolled reader, not an EXIF crate: we need one tag out of a large, untrusted format, and `kamadak-exif` would bring an entire TIFF/EXIF parser — every tag type, sub-IFDs, maker notes — as new untrusted-input surface for ~80 lines of value. This is the same hand-roll-versus-dependency judgement as ZIP in ADR-0024 and lands the same way for the same reason. Bounds: scan at most the first 64 KiB for an APP1 payload beginning `Exif\0\0`; require `II*\0` or `MM\0*`; walk **IFD0 only**, never following sub-IFD or maker-note pointers, entries capped at 512; accept tag `0x0112` type SHORT count 1 with value 1..=8, and treat anything absent, malformed or out of range as orientation 1, silently — a broken EXIF block is not a report entry, it is simply no rotation. All offsets checked, `slice::get` never indexing, under the same lint regime as the ZIP reader.

Orientations 5–8 transpose, so the probe reports **post-rotation** dimensions (which is what the per-mille rect and the `media_asset` row want) and the megapixel cap is **halved** for those values, because the transpose needs a destination buffer alongside the source. The staged file keeps the **original** bytes including the orientation tag; only the decoded pixels are rotated, since re-encoding would be lossy and pointless.

---

## Options considered

- **(Chosen) Add pure-Rust JPEG decode through the existing bounded seam.** Pros: the owner's approved scope becomes true on real decks; fixes `deck_import_image`'s unhonourable jpg filter; unblocks JPEG for the canvas image element; preserves every ADR-0018 property (bounded, panic-contained, memory-safe, pre-allocation caps, placeholder on failure) and every security bound. Cons: a second parser on the in-process decode path (ADR-0016 still deferred); the determinism claim weakens from format-inherent to pinned-version; a new crate in the SBOM; a small regression surface in tests asserting JPEG rejection.
- **Ship text-only import now, add JPEG later.** Rejected by the owner. Architecturally it was the lowest-risk sequencing and remains a valid fallback if the JPEG work slips — the import design keeps the image stage severable.
- **Ship PNG-only images with an honest drop report.** Rejected. Technically consistent with the partial-import model, but it converts an accurate report into a product that appears defective.
- **A platform or hardware still-image decoder** (WIC, ImageIO, gdk-pixbuf). Rejected outright, as in ADR-0018: it would break cross-OS byte parity, and the security constraint set forbids handing untrusted media to an OS decoder.
- **`zune-jpeg`.** Rejected on determinism and unsafe-SIMD grounds, not on quality — see decision 2.
- **Convert CMYK JPEGs with a naive transform.** Rejected: without the ICC profile the result is wrong, and wrong-but-plausible colour on an audience screen is worse than a visible skip.

---

## Consequences

**Positive.** "Text plus images" is true on real church decks. The decode seam becomes format-agnostic, so the next format is a signature entry and a header check rather than a redesign. `deck_import_image`'s long-standing jpg-filter defect is fixed as a side effect, and should appear in the release note as a fix. EXIF handling means photographs import upright, which is the single most visible quality difference a user will notice. Every ADR-0018 bound is preserved and import tightens them further.

**Negative / watch.** The in-process decode surface (threat T12) now has two parsers rather than one; this feature is also the first routine path for internet-downloaded files to reach it, which strengthens the case for re-prioritising the ADR-0016 out-of-process worker — recorded as a recommended follow-up. `jpeg-decoder` joins the pinned-and-gated dependency set and must be recorded in the SBOM with the licence gate re-run (NFR-027, `86ajpew0j`). The determinism contract is now a property of a pin rather than of a format, which is weaker and must be tested rather than argued. There is still **no wall-clock bound inside the decoder** — the import-level 30 s timeout bounds the import path, but the render path's decode remains untimed, and progressive JPEG is more CPU-intensive than baseline; that pre-existing gap is now slightly more reachable and stays flagged for the Security Reviewer.

**Follow-ups.** Re-prioritise ADR-0016. Consider a decode wall-clock for the render path. GIF, BMP, TIFF, WMF, EMF, SVG and HEIC remain dropped-and-reported and are not scheduled.

## References


## Amendments (remediation round 2)

**`decode_png` is deprecated, not merely wrapped.** Keeping the old name as a live alias was a
trap: a function called `decode_png` that also decodes JPEG reads as a PNG-only path to anyone
skimming, and the render path's `load_and_decode` called it — so decks referencing `.jpg` quietly
started rendering instead of showing the placeholder, with no line of the diff saying so. The alias
now carries `#[deprecated]` naming the widening, every in-tree caller has moved to `decode_image`,
and the render path calls `decode_image` directly.

**`probe_image(bytes, &DecodeLimits) -> Result<ImageInfo, DecodeError>` is added: steps 1–7 without
step 9.** Validating an image by decoding it and discarding the pixels was measured at over 99 % of
presentation-import time — around fifteen seconds at the cap on a fast machine, extrapolating to
45–75 s on church hardware against a 30 s import timeout that would then keep nothing — and the
render path decoded the same bytes again afterwards. No cap is weakened: every admission decision
is still made on header-derived dimensions before any allocation, which is the B5-J requirement, and
`decode_png_inner` now routes through the same probe so the two cannot make different decisions.

The one thing given up, deliberately: an image with a sound header and a corrupt payload is now
staged by the importer and shows the missing-media placeholder at render time, instead of being
reported at import time. A structurally bad header — a damaged IHDR, a failed chunk CRC, a refused
JPEG variant, a frame past the caps — is still refused and still reported.

**The JPEG decoder-buffer budget cannot fire while steps 6–7 hold**, and that is now stated in the
code with the arithmetic rather than implied. Removing it fails no test, and so does re-introducing
the cap-sized defect its comment describes; both were checked. It is kept for the case the caps
cannot cover — a decoder version whose internal requirement grows relative to the frame.

PRD: FR-066, FR-070, FR-173, NFR-014, NFR-024, NFR-027; threat T12. ADRs: 0002, 0015, 0016, **0018**, 0020, **0024**. Code: `crates/selahcue-engine/src/media.rs` (`decode_png`, `DecodeLimits`, `DecodeError`, the signature allowlist), `raster.rs` (`MAX_DIMENSION`, placeholder). Design: `docs/architecture/IMPORT-presentation-design.md` §9. Security: `docs/security/THREAT-MODEL-presentation-import.md` (B5, revised for JPEG).
