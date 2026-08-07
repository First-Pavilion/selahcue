# SelahCue — Cross-Functional Decision Log

Durable record of material product/scope/architecture decisions, with traceability. Newest first.

---

## DEC-003 — Slides & Media engine: build the authored-deck + media library, defer live video/audio render

- **Date:** 2026-08-03
- **Stage:** Stage 8 (Presentation & Slides epic 86ajp07ce)
- **Decided by:** User (product owner), scoping the /backend-engineer build of the Design-2.0 "Presentation & Media" surface (Figma node 329:124)
- **Type:** Scope boundary (architecture)
- **Status:** DECIDED

**Decision.** The Slides/presentations engine is built as **two subsystems this pass** — the authored slide-deck engine (domain model where slides own layered elements + compose + Preview→Live playback + persistence) and the **media library** engine (a bounded registry of image/video/audio assets with import, missing-file and used/unused detection, and storage accounting) — with a **new forward-only SQLite `deck` + `media_asset` schema**. **Live video/audio playback on the audience output is explicitly deferred** to its own story + ADR: the media library *lists* video/audio assets now, but they cannot yet go live.

**User rationale.** Selected "Deck engine + media library" scope with "new deck/document repo" persistence when the engine was scoped; live video-on-output was surfaced as the largest, highest-risk slice and held back.

**Supporting evidence.** Video-on-wgpu is a heavy new subsystem (decode pipeline + frame-clock sync + preserving the NFR-024 never-blank guarantee with a *live* decoder that can stall), out of proportion to a slide-engine slice and interacting with ADR-0016 decode isolation. Per ADR-0002/0003 it renders in the native compositor, never the WebView. See **ADR-0020** for the full realisation + non-goals.

**Affected items.** New: `selahcue-present::deck` (`SlideDeck`/`AuthoredSlide`/`DeckSession`/`crossfade`/`media_usage`), `compose_authored_slide`; `selahcue-core::media` (`MediaLibrary`/`MediaAsset`/`MediaKind`); `selahcue-data` migrations v16 (`deck`) + v17 (`media_asset`) with `deck_repo`/`media_repo`. Deferred (own follow-ups): live video/audio render; the S8-4 in-webview editor + undo/redo; new LAN wire commands to drive decks; FR-029 auto-pagination.

**Reversibility.** Additive throughout (new modules + additive `CREATE TABLE` migrations); no wire or existing-schema change. Video render can be added later without reworking the model (assets already carry kind/duration/dimensions).

---

## DEC-002 — RBAC: `Clear` (wipe live output) tightened to Producer+ (revised)

- **Date:** 2026-07-23 (original) · **Revised:** 2026-07-24
- **Stage:** Stage 7 gate (batch 7d original; batch 7k revision)
- **Decided by:** User (product owner)
- **Type:** RBAC policy
- **Status:** REVISED — `Clear` is now Producer+ (superseding the 7d "keep as-is")

**Revision (2026-07-24, batch 7k).** When the LAN control was wired to the presenter (7k), `Clear` gained teeth: the batch-7k independent review confirmed a **HIGH** consequence — an **Assistant** (a role that "cannot push to the live output") could `Clear` the live audience output *and* lift an operator-set blackout over the wire. Presented at the 7k gate, the user chose to **tighten it** ("refine: tighten it").

**Decision (revised).** `Command::Clear` now requires a dedicated **`Permission::ClearLive`**, held only by **Operator** and **Producer**. Assistant retains `Navigate` (Next/Previous/SelectItem — which stage *Preview* and do not change Live) plus SearchScripture and Monitor, but **cannot wipe the live output**. `GoLive`, `Blackout`, `Timer` remain Producer+ as before.

**User rationale.** Original (7d): "keep as is; revisit later if there's a need." Revision (7k): "tighten it" — an emergency wipe of the congregation screen must not be available to the lowest control role, especially once it can also lift a blackout.

**Affected items.** `selahcue-lan::rbac` — added `Permission::ClearLive`; `required_permission(Clear)` now maps to it; granted to Operator + Producer. `test_rbac.rs` updated (Clear removed from the navigate set; Assistant/Viewer `Clear` denials asserted; `Clear` added to the Producer+ matrix). The `LiveController` is unchanged — RBAC is enforced by the server before the handler.

**Reversibility.** Trivially reversible by re-mapping `Clear` to `Navigate`.

---

## DEC-001 — Text-to-Speech (TTS) removed from the product roadmap (de-scoped)

- **Date:** 2026-07-23
- **Stage:** Stage 2 gate (refine)
- **Decided by:** User (product owner)
- **Type:** Scope reduction (authorized at gate)
- **Status:** DECIDED

**Decision.** TTS is **not** a requirement for SelahCue's MVP or its planned roadmap. It is reclassified from "later release" to a **non-goal / on-hold** feature, revisited only if the user explicitly requests it in future.

**User rationale.** "Let's hold off on TTS. I don't see it as a major requirement in the long run."

**Supporting evidence (discovery).** Independent research already assessed TTS as the **lowest-value** of the four AI features (a presentation app's congregation reads the screen) and the **highest live-room risk** (audio feedback, mic bleed / self-re-transcription, accidental routing to the house system). See [../research/PROVIDER-TRADEOFFS.md](../research/PROVIDER-TRADEOFFS.md) §3, [../research/CAPABILITY-ASSESSMENT.md](../research/CAPABILITY-ASSESSMENT.md), and open decision OD-02. Discovery already recommended deferring it; the user's decision goes further and removes it from the roadmap.

**Affected items.**
- Product brief `product/PRODUCT-BRIEF.md` §"Text-to-speech requirements" → now a documented non-goal (brief remains the historical source; PRD will mark TTS as an explicit non-goal with this decision cited).
- Open decision **OD-02** → DECIDED (hold off).
- Risk **RISK-008** (TTS audio routing / feedback) → no longer active roadmap risk; retained as conditional (re-activates only if TTS is reconsidered).
- **Stage 11** ("Sermon intelligence and TTS") → becomes **"Sermon intelligence"** only; TTS deliverables dropped.
- Build Goal Contract `BUILD-selahcue.md` → TTS added to Non-goals; TTS-specific sub-clauses of completion predicates C-013/C-018/C-019/C-021 become NOT_APPLICABLE.
- Voice-selection/routing/pronunciation/audio-export TTS work → removed from scope.

**Impact.** Reduces scope and live-service risk; simplifies the audio path (no TTS output-routing/feedback-safety subsystem). No negative impact on core presentation, transcription, scripture detection, or sermon notes. Accessibility use cases that TTS might have served are noted for the PRD's accessibility section to address by other means (e.g. screen-reader compatibility, large-text/high-contrast) rather than built-in TTS.

**Reversibility.** Fully reversible before implementation; TTS research artifacts are retained. Re-scoping TTS back in would return to Stage 2/3 for that feature only.
