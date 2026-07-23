# ADR-0014 — Unicode text shaping

- **Status:** Accepted
- **Date:** 2026-07-23
- **Owner:** Software Architect
- **Confidence:** Medium — the *choice* of a HarfBuzz-class shaping layer is well-grounded; the *specific stack + bundled fonts rendering the cited diacritics correctly with working fallback* is unproven and gated on spike S10 (see §Confidence caveat)
- **Validating spike:** S10 (text shaping / Unicode / font coverage for the custom GPU text stack)
- **Related ADRs:** ADR-0001 (Rust core), ADR-0002 (wgpu compositor — this text stack lives inside it), ADR-0003 (Tauri operator-UI shell — its *own* text is the web stack, out of scope here), ADR-0012 (packaging — bundled fonts), and the font-decode-hardening requirement FR-173.

> **Evidence honesty note.** Every finding cited below is **DOCUMENTED** (framework/library docs, the feasibility work) or **INFERRED** (reasoned synthesis). The feasibility report contains **zero OBSERVED findings** — no software was executed in that environment (FEASIBILITY §Method, §10 classification summary). That is precisely why S10 exists. Note also that S10 (and S11) were *appended* to FEASIBILITY §10 after Stage-2, per DISCOVERY-REVIEW C2/M2; the §10 classification summary line still reads "UNKNOWN: 9 spikes (S1–S9)" — a documentation artifact, not a claim that shaping is resolved. Text shaping is an **UNKNOWN pending S10**, not a settled capability.

---

## Context

ADR-0002 chose a native wgpu compositor and, in doing so, made text correctness **our** responsibility rather than a browser's (ADR-0002 §Consequences: "Text correctness (Unicode, diacritics, fallback) is now our responsibility via ADR-0014/S10"). The output text path is: shaped glyphs → glyph atlas → textured quads, composited per output (ARCHITECTURE §6). This ADR decides how the *shaping* step is done for the **native output** rendered by the wgpu engine. It does **not** govern the operator-console UI text, which the Tauri WebView renders with the web text stack (ADR-0003) — a deliberate scope boundary.

The forces driving the choice come from the PRD and the feasibility evidence:

1. **Unicode + multi-language text is an unqualified MVP requirement.** FR-017 (MVP) requires "Unicode + multi-language text (Latin + diacritics incl. Yoruba/Hausa/Igbo/French/Spanish)," with the testable acceptance: **"Diacritic glyphs shape/render correctly on output; font fallback covers the character set."** The feasibility work flags Unicode as "an unqualified brief requirement" (FEASIBILITY §10 S10).

2. **The GPU glyph renderers do not, alone, shape.** The Rust text renderers the wgpu path uses — glyphon / wgpu-text — "render textured-quad glyphs **but do not, alone, do complex-script shaping/bidi**" (FEASIBILITY §10 S10; §1 Rust-native row and §2 wgpu row both list "glyphon/wgpu-text for text" as the *rendering* substrate). The cited MVP languages (Yoruba/Hausa/Igbo/French/Spanish) are **LTR Latin + diacritics** (FEASIBILITY §10 S10) — but their tonal/combining marks (e.g. Yoruba `ẹ́ ọ̀ ṣ`, Igbo `ị ọ ṅ`) still require real shaping to stack and position marks correctly. A bare glyph renderer with per-character placement mis-positions or fails to combine these — failing FR-017's acceptance.

3. **Font fallback must cover the character set.** FR-017's acceptance names font fallback explicitly. A missing glyph must resolve through a fallback chain, never render as tofu (□). Fonts are bundled under **OFL/Apache only** (PRD §Licensing; ADR-0012), which constrains the fallback set we may ship (Noto-class families with full diacritic coverage).

4. **Cross-platform parity is binding (NFR-014).** "Core presentation behaviour identical on Windows, macOS, Linux (test matrix passes on all three)." The same lyric slide must shape, break lines, position marks, and fall back **identically** on all three OSes, and preview must equal live (FR-012/013). This force weighs heavily against per-OS OS text APIs, which shape and substitute differently.

5. **RTL / complex-script is explicitly scoped past MVP — but the engine choice is made once.** NG-6 excludes RTL/complex-script (Arabic/Hebrew) from MVP; FR-018 (R6) carries it ("Arabic/Hebrew shape with correct bidi/joining on output," scoped later per OD-22). The MVP shaping engine should make R6 an **enablement, not a re-platform** — i.e. pick a shaper that already knows Arabic/Hebrew shaping + bidi even though we don't turn them on until R6.

6. **Fonts are untrusted input (FR-173).** Imported/theme fonts must "decode via memory-safe or actively-maintained decoders with header/type/size validation before full decode; decode is isolated/sandboxed where platform-feasible" (FR-173, MVP; threat T12). The shaping stack's font parser is on this attack surface, so a **memory-safe** parser is a security asset here, not just a convenience.

7. **Large-text / high-contrast legibility (NFR-020).** Configurable large text (≥48px-equiv) and high-contrast stage/confidence output — the text stack must scale glyphs cleanly at large sizes and integrate with per-output layout (ARCHITECTURE §6).

The brief *suggests* cosmic-text/HarfBuzz in the wgpu text stack (ARCHITECTURE §2, §6), but per feasibility discipline the options are evaluated on evidence, not on the suggestion (FEASIBILITY §Method).

---

## Options considered

### Option A — cosmic-text / HarfBuzz shaping (rustybuzz) rendered via glyphon into the wgpu atlas  ✅ CHOSEN

A Rust-native text stack: **cosmic-text** performs layout, bidi, line-breaking and per-run font fallback (via `fontdb`), delegating glyph shaping to **rustybuzz** (a pure-Rust port of HarfBuzz) over `ttf-parser`; **glyphon** rasterizes the shaped run into a wgpu glyph atlas drawn as textured quads (ARCHITECTURE §6: "Text via cosmic-text/HarfBuzz → glyph atlas → textured quads").

**Pros (evidence-grounded):**
- **Supplies exactly the missing layer.** FEASIBILITY §10 S10 states the renderers alone do not do shaping/bidi and calls to "confirm a **HarfBuzz / cosmic-text-class shaping layer** for the cited languages" — this option *is* that layer. It does the diacritic mark positioning FR-017 requires, which a bare glyph renderer cannot.
- **Font fallback is built in.** cosmic-text/`fontdb` does per-run font fallback across a font set, directly serving FR-017's "font fallback covers the character set."
- **One shaper on every OS ⇒ parity (NFR-014).** A single bundled shaper (rustybuzz) produces byte-identical shaping/fallback/line-breaking on Windows, macOS and Linux — the strongest guarantee available for "identical core presentation behaviour" and for preview == live. OS text APIs (Option C) cannot promise this.
- **Rust-native, memory-safe, aligns with the Rust core (ADR-0001).** rustybuzz + ttf-parser are pure-Rust — **no C-HarfBuzz FFI**, and a memory-safe font parser that materially helps FR-173's "memory-safe decoder" posture for untrusted fonts.
- **Integrates cleanly with the chosen compositor.** glyphon is purpose-built to render cosmic-text buffers into a wgpu atlas, so this drops into ADR-0002's pipeline without a new rendering paradigm.
- **R6 is an enablement, not a re-platform.** HarfBuzz/rustybuzz already shape Arabic/Hebrew and cosmic-text carries Unicode bidi — so FR-018 (RTL, R6) is switched *on* later rather than forcing a text-stack rewrite (satisfies force 5).

**Cons / risks (evidence-grounded):**
- **We own the text-stack integration** — glyph-atlas management, layout caching, large-text scaling (NFR-020), per-output layout coupling. Real, ongoing engineering, consistent with ADR-0002's "we own the compositor" cost.
- **rustybuzz is a *port* of HarfBuzz** and can lag upstream on the newest OpenType/script features (historically weaker on Apple AAT `morx` and some edge GPOS cases). For Latin + diacritics this is well within its coverage, but it is a real caveat for future complex scripts — see Fallback.
- **Unproven for our specific inputs.** That this exact stack + our bundled OFL/Apache fonts render the cited diacritics correctly *with working fallback* is **UNKNOWN until S10** (FEASIBILITY §10 S10). This is the source of the Medium confidence.
- **Bundled-font licensing/coverage constraint.** We must ship OFL/Apache fonts (Noto-class) whose combined coverage spans the FR-017 character set; a coverage gap surfaces as a fallback miss (PRD §Licensing; ADR-0012).

### Option B — Glyphon-only (no complex shaping): a non-shaping glyph renderer  ❌ REJECTED as primary

Use the GPU glyph-rendering layer (glyphon, or a wgpu-text / glyph-brush-class renderer) for atlas rasterization and simple per-character positioning, **without** engaging a HarfBuzz-class shaping + bidi + fallback layer.

**Pros:** Simplest to integrate; smallest dependency surface; adequate for pure ASCII/basic Latin.

**Cons (decisive):**
- **This is exactly the gap FEASIBILITY §10 S10 warns about:** these renderers "render textured-quad glyphs but **do not, alone, do complex-script shaping/bidi**." Without a shaping pass, combining diacritics for Yoruba/Igbo tonal marks mis-stack or fail to compose — **failing FR-017's "diacritic glyphs shape/render correctly"** acceptance.
- **No font-fallback logic** ⇒ any glyph outside the primary font renders as tofu — failing FR-017's "font fallback covers the character set."
- **No forward path to RTL/complex-script** ⇒ FR-018 (R6) would force a text-stack re-platform later, the opposite of force 5.
- Technical nuance: glyphon is in fact a *renderer for cosmic-text*, so this option and Option A share the rendering substrate — the difference is solely whether a real shaping/bidi/fallback layer sits in front of it. Dropping that layer buys almost nothing and forfeits FR-017.

**Verdict:** rejected as the primary approach. The renderer (glyphon) is retained — as the *rasterization substrate underneath* Option A's shaping layer, not as a standalone text solution.

### Option C — OS text APIs (DirectWrite / Core Text / Pango-HarfBuzz)  ❌ REJECTED as primary

Shape via each platform's native text stack — DirectWrite (Windows), Core Text (macOS), Pango + HarfBuzz/FreeType (Linux).

**Pros:** Mature, high-quality shaping; excellent OS-integrated font fallback; shaping is "done for us" per platform.

**Cons (decisive):**
- **Breaks cross-platform parity (NFR-014).** Three different shapers (only Linux's Pango even uses HarfBuzz) shape marks, break lines, and substitute fonts **differently** — so the same slide can differ across OSes, and preview may not equal live. This is the same failure mode FEASIBILITY records against per-OS native paths generally (§1 SwiftUI/WinUI row "two+ separate codebases ... contradicts single cross-platform desktop goal"; §3 Option C "triples integration + testing").
- **Three separate integrations** — contradicting the single cross-platform desktop codebase (CON-1) and the Rust core (ADR-0001); larger FFI surface and divergent error semantics.
- **Awkward hand-off to the wgpu atlas.** OS text APIs want to draw into their own surfaces (Direct2D / CoreGraphics / Cairo), not hand back positioned glyph IDs for *our* atlas; marrying them to ADR-0002's compositor is friction, not a shortcut.

**Verdict:** rejected as the primary shaper. We still let `fontdb` enumerate **OS-installed fonts** as fallback candidates (a read-only assist), but shaping stays in our bundled, deterministic engine. Retained only as a last-resort per-OS fallback for a specific script where the bundled shaper fails (see Fallback).

---

## Decision

**Adopt cosmic-text with HarfBuzz-class shaping (rustybuzz) for the native wgpu output text stack, rendered via glyphon into the glyph atlas (ARCHITECTURE §6).** MVP scope is **Latin + diacritics** covering the FR-017 languages (Yoruba, Hausa, Igbo, French, Spanish); **RTL / complex-script (Arabic/Hebrew) is deferred to R6 (FR-018, NG-6, OD-22)** but the stack is chosen specifically so that R6 is turned *on*, not rebuilt. Ship a curated set of **OFL/Apache** fonts (Noto-class) whose combined coverage spans the MVP character set, with a defined font-fallback chain. Any imported/theme fonts pass through the FR-173 decode-hardening path (memory-safe/maintained parser — ttf-parser is Rust — with header/type/size validation before full decode, sandboxed where platform-feasible).

This keeps the brief's cosmic-text/HarfBuzz leaning where the evidence supports it, while explicitly rejecting (a) a non-shaping renderer that would fail FR-017 and (b) per-OS OS text APIs that would break NFR-014 parity.

---

## Confidence caveat (do not overstate)

The **Medium** confidence is deliberate and split:

- **Well-grounded:** that a **HarfBuzz-class shaping + bidi + fallback layer** is required and is the right architectural category — the renderers alone don't shape (FEASIBILITY §10 S10, DOCUMENTED), and only this category delivers correct diacritics + fallback + parity in-process. That part is not in doubt.
- **Unproven (the reason it is not High):** that *this specific* cosmic-text/rustybuzz stack, with *our* bundled OFL/Apache fonts, renders the cited diacritics correctly and falls back cleanly on all three OSes. That is **UNKNOWN until S10** (FEASIBILITY §10 S10), which must "confirm a HarfBuzz / cosmic-text-class shaping layer for the cited languages ... and prototype font-fallback." rustybuzz's port-lag caveat and the bundled-font coverage question both live here.

We therefore do not claim MVP Unicode is proven; we claim the approach is correct and the residual risk is a bounded, spike-checkable rendering-correctness question, with fallbacks below.

---

## Consequences

**Positive:**
- The only option that satisfies FR-017 end-to-end: real shaping (diacritic mark positioning), built-in font fallback, and — via one bundled shaper — **cross-platform parity (NFR-014)** and preview == live.
- Rust-native and memory-safe (rustybuzz/ttf-parser, no C FFI), reinforcing FR-173's untrusted-font decode-hardening posture and the Rust core (ADR-0001).
- Drops into the ADR-0002 wgpu pipeline (glyphon → atlas → textured quads) with no new rendering paradigm; scales to NFR-020 large-text/high-contrast output.
- Makes R6 RTL/complex-script (FR-018) an enablement of an already-present capability, not a text-stack re-platform.

**Negative / costs:**
- We own the text-stack integration (atlas management, layout/shaping caching, large-text scaling, per-output layout coupling) — sustained engineering and a bug surface, consistent with ADR-0002's compositor-ownership cost.
- rustybuzz can lag upstream HarfBuzz on the newest OpenType/AAT features; low risk for Latin+diacritics, a watch-item for R6 complex scripts.
- We must curate and license (OFL/Apache) a bundled font set with sufficient coverage, and keep the fallback chain maintained (ADR-0012).

**What it commits us to:**
- A bundled, deterministic shaper as the single source of shaping on all three OSes (no per-OS shaping divergence) — NFR-014.
- A curated OFL/Apache bundled-font set + fallback chain covering the FR-017 character set (ADR-0012; PRD §Licensing).
- Routing all imported/theme fonts through the FR-173 decode-hardening path.
- Treating RTL/complex-script (FR-018) as a **later enablement** of this stack (R6, OD-22), designing layout data structures now to allow bidi without a rewrite.
- Gating the *claim* that MVP FR-017 is met on S10 evidence, not on library reputation.

---

## Fallback & validation

**What S10 must confirm** (FEASIBILITY §10 S10): that cosmic-text/rustybuzz + the bundled fonts shape and render the cited **Latin+diacritic** languages (Yoruba/Hausa/Igbo/French/Spanish) correctly on Windows/macOS/Linux, and that font fallback covers the FR-017 character set with no tofu. RTL/complex-script (Arabic/Hebrew) is *not* on the MVP critical path (NG-6/FR-018/R6), so an S10 shortfall on complex scripts does **not** block MVP; only the Latin+diacritic + fallback result gates FR-017.

**Fallbacks if S10 finds a defect** (in rough order of preference; each keeps the same architectural category — an in-process HarfBuzz-class shaper — to preserve NFR-014):
1. **Broaden / re-curate the bundled font set** (e.g. add language-specific Noto faces) to close a fallback gap — most gaps will be coverage, not shaping.
2. **Swap the shaping backend to C HarfBuzz via FFI** (`harfbuzz_rs`-class bindings) if a specific diacritic combination mis-shapes in rustybuzz — identical HarfBuzz semantics, more complete/mature, at the cost of a C dependency and FFI. This *weakens* the memory-safety posture, so it is mitigated by keeping the C HarfBuzz surface behind FR-173's validation/sandboxing and treating it as a contained, audited dependency (NFR-027 SBOM/CVE scanning).
3. **Last resort, single-script / single-OS only:** use that OS's text API (Option C) for shaping *that one script* on *that one platform*, explicitly accepting the NFR-014 parity risk for it and documenting the divergence. This is a last resort precisely because it reintroduces the parity problem Option C was rejected for.

The renderer (glyphon) and the compositor hand-off (ADR-0002) are unaffected by any of these fallbacks — only the shaping backend behind the atlas changes — which is why the overall decision is robust to the S10 outcome.

---

## Requirement / PRD references

- **Non-goals / scope:** NG-6 (RTL/complex-script excluded from MVP; MVP = Latin + diacritics incl. Yoruba/Hausa/Igbo/French/Spanish), OD-22 (RTL/complex-script open decision), CON-1 (single cross-platform desktop codebase).
- **Functional:** FR-017 (MVP — Unicode + multi-language text; acceptance: diacritics shape/render correctly + font fallback covers the character set), FR-018 (R6 — RTL/complex-script bidi/joining), FR-012/013 (preview vs live separation; current/next views — depend on deterministic shaping), FR-173 (MVP — untrusted-media/font decode hardening; threat T12), FR-160 (GPU/renderer + decoder recovery — the text path is inside the recovered engine).
- **Non-functional:** NFR-014 (cross-platform parity — the decisive force for a single bundled shaper), NFR-020 (WCAG AA contrast + configurable large text ≥48px-equiv + high-contrast legibility), NFR-027 (SBOM / dependency + CVE + license scan — governs any C-HarfBuzz fallback and the bundled-font licenses).
- **Licensing:** PRD §Licensing (fonts OFL/Apache only); ADR-0012 (packaging bundled fonts).
- **Architecture (ARCHITECTURE.md):** §2 ADR index (ADR-0014), §4 Engine component ("text shaping"), §6 Rendering & output architecture ("Text via cosmic-text/HarfBuzz → glyph atlas → textured quads"); ADR-0002 §Consequences (text correctness delegated here) and §Decision (cosmic-text/HarfBuzz-shaped glyphs → atlas → quads).
- **Feasibility (FEASIBILITY.md):** §10 spike **S10** (the governing evidence — renderers don't shape alone; confirm a HarfBuzz/cosmic-text-class layer for the cited LTR Latin+diacritic languages; prototype font fallback; RTL scoped past MVP per OD-22), §1 Rust-native row & §2 wgpu row ("glyphon/wgpu-text for text" as the rendering substrate), §10 classification summary (OBSERVED: 0 — reason S10 is required) and the DISCOVERY-REVIEW C2/M2 provenance of S10/S11.
