# ADR-0020: Authored slide decks + media library engine (Design 2.0 "Presentation & Media")

- **Status:** Accepted
- **Date:** 2026-08-03
- **Confidence:** High (the model shape, determinism/never-blank/bounded invariants, and persistence are structural and test-verified). This is **not** a claim about the editor UX or live video playback, which are explicitly deferred below.
- **Owner:** Backend Engineer (delivery slice), under the Software Architect's presentation-service model (ARCHITECTURE.md §8).
- **Realises:** the ARCHITECTURE.md §8 `document`(slide/deck) entity + the media-ref concept (FR-003, FR-009). **Related:** ADR-0002/0003 (the compositor is native wgpu; the WebView is console-only — video render lands there, not the WebView), ADR-0015 (injected-clock determinism / testable-render seam), ADR-0018 (in-process still-image decode), ADR-0007 (persistence).
- **Design:** Figma `SYQn5hFY8YVQKm3c6rw0eJ` node **329:124** ("Presentation & Media — Design 2.0").
- **ClickUp:** story 86ajv8qd9. **Goal Contract:** `docs/delivery/goals/TASK-slides-deck-media-engine.md`.

---

## Context

Basic scripture/song presentation (a transient `Slide` title+body composed through a theme) already
ships. The Design-2.0 "Presentation & Media" surface adds a genuinely different content type — an
**authored slide deck**: an ordered list of slides that each own their **own layered content** (free
text boxes / shapes / images over a per-slide background), plus speaker notes, a per-slide transition,
and auto-advance — and a **media library** of imported assets (images, video, audio) referenced by
those slides. The ARCHITECTURE.md §8 `document`(slide) entity was spec'd but unimplemented (no data
table, no per-slide element ownership). This ADR records the backend realisation and its deliberate
limits; the in-webview editor is the sibling frontend story (S8-4).

## Decisions

1. **The authored-deck model lives in `selahcue-present::deck`, reusing the Canvas-Editing model.** A
   `SlideDeck` is an ordered, bounded (`MAX_DECK_SLIDES`) list of `AuthoredSlide`s with stable, never-reused
   `SlideId`s (mirroring `ItemId`). An `AuthoredSlide` **owns** a `Vec<theme::Element>` (the existing
   Shape/Image/Text canvas model — z-ordered, `visible`, opacity), an optional per-slide `theme::Background`,
   speaker `notes`, a `Transition`, and `auto_advance_secs`. Content stays **orthogonal to the theme**
   (the theme supplies only the fallback background), exactly as for a `Slide`. All non-id fields default
   and are `skip_serializing_if`-omitted, so a new slide's JSON is `{"id":N}` and adding a field never
   bloats existing decks (byte-stable, additive — the NFR-014 discipline).

2. **`compose_authored_slide` composes a slide's own background + z-ordered visible elements to a `Frame`,
   never blank (NFR-024).** It reuses `push_background` + `element_layers` + the deterministic raster —
   no title/body regions (the elements *are* the content). The background always fills, so a zero-element
   slide composes to a valid background frame, never nothing. A `Transition::Fade` renders through a
   deterministic per-pixel `crossfade(from, to, progress)` over rendered `FrameBuffer`s (endpoints exact).

3. **Playback is `DeckSession`, a self-contained Preview→Live state machine.** It mirrors the `Presenter`
   invariant — staging/navigating moves only the Preview cursor; `go_live` is the sole action that changes
   Live — and drives **auto-advance from an injected clock** (`tick(now)`), so it is fully deterministic
   (ADR-0015). It is a *new* type rather than an extension of `Presenter`, to avoid entangling with the
   concurrently-evolving per-screen/`LayerMask` presenter path.

4. **The media library lives in `selahcue-core::media` and stays dependency-free (no serde).** `MediaLibrary`
   is a bounded (`MAX_MEDIA_ASSETS`) registry of `MediaAsset` metadata (never file bytes), keyed by stable
   `MediaId`, idempotent by path. Missing-file detection takes an **injected existence probe**
   (`missing(|path| …)`), so the core takes no filesystem dependency and stays exhaustively testable;
   used/unused correlation against decks (`present::media_usage`) is computed where `Element` is visible.
   `MediaKind` carries a string tag (`as_tag`/`from_tag`) exactly like `ItemKind`.

5. **Persistence: a JSON-blob `deck` table + a *structured* `media_asset` table (forward-only migrations
   v16/v17).** `deck_repo` mirrors `saved_theme_repo` (opaque `deck_json`, so the data crate takes no
   `selahcue-present` dependency). `media_asset` uses structured, nullable columns (not a blob) so storage
   accounting and missing/unused stay first-class; an unrecognised `kind` row is **dropped on load, never
   fatal** (forward-compat). Both writes replace the whole set transactionally (removals persist).

6. **Video/audio are listed but NOT rendered this pass — the video-render deferral.** The registry holds
   `Video`/`Audio` assets now (the design shows `.mp4`/`.wav` entries), but **live playback on the audience
   output is deferred to its own story + ADR.** Rationale: video-on-wgpu is a heavy new subsystem (a decode
   pipeline, frame-clock synchronisation, and preserving the NFR-024 never-blank guarantee with a *live*
   decoder that can stall) that is out of proportion to a slide-engine slice and interacts with ADR-0016
   decode isolation. Per ADR-0002/0003 it renders in the native compositor, never the WebView. `Element`
   gains no `Video` variant yet; authored slides carry Shape/Image/Text only.

7. **No new LAN wire-protocol commands this pass.** The engine is exercised through the domain +
   `DeckSession`; commands to drive decks from the operator/mobile belong with the S8-4 editor and would
   otherwise churn the byte-pinned cross-language wire fixtures. The wire stays VERSION-stable.

## Deliberate non-goals / seams (carried honestly)

- **Live video/audio playback on the audience output** — deferred (decision 6); own ADR/story.
- **The in-webview slide editor, undo/redo (≥20), command palette** — the S8-4 frontend story (86ajpzhan).
- **Slide auto-pagination (FR-029, `Fit::Paginate`)** — still treated as `Clip`; a later slice.
- **New wire commands + a `PlanItem`→deck reference** — thin follow-ups (decision 7); the deck library is a
  standalone document set this pass.

## Consequences

- **Positive:** a real, testable authored-deck + media engine that reuses the whole compose→raster→Presenter
  stack; the S8-4 editor now has an engine to drive; persistence realises the long-spec'd §8 `document`
  entity. Every invariant (determinism, never-blank, bounded memory, byte-stable serde, forward-only
  migration) is test-verified.
- **Negative / watch:** the deck library is keyed by name (like saved themes) — a rename is a new key until
  a stable deck id is added; `DeckSession` duplicates a little `Presenter` structure by design (isolation
  from concurrent presenter work). Video's absence is visible in the UI (assets list but cannot go live) —
  the library surfaces the kind honestly rather than hiding it.
