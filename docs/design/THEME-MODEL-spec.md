# Theme Model + Theme Designer — Design Spec (S8-3a, FR-010)

**Status:** design (gates S8-3b/c/d) · **Owner:** /ui-ux-designer · **Requirements:** FR-010 (+ FR-009 layout regions, FR-011 content types) · **Depends on:** S8-2 shaping (done) · **Figma:** file `SYQn5hFY8YVQKm3c6rw0eJ` (Theme Designer + template mocks — node ids in the handoff comment)

> A **theme** is a reusable **slide-design template** the audience output uses to render scriptures, songs, announcements, and lower-thirds — *fonts, colours, safe areas, positions* (FR-010). It is **not** a light/dark colour mode. Applying/switching a theme **restyles content without losing it** (content is stored separately from the theme). Modelled on ProPresenter Themes + the owner's Pewbeam Theme Designer.

---

## 1. Core principle — content ⟂ theme

Content (verse text, a reference string, lyric stanzas, an announcement body) lives on the **PlanItem / Slide**. A theme supplies only **how** that content is laid out and styled. Therefore:

- **Switching a theme never mutates content** — the engine re-lays-out the *same* content under the new theme. Zero content loss is structural, not best-effort.
- **Overflow is surfaced, never truncated** (FR-010; COMPONENT-SPECS §Editor): if themed content is taller than its region, warn + show an overflow indicator; the engine paginates (later) or scales-to-fit per the region policy — it must not silently drop text.

---

## 2. Data model

All positions/sizes are **percent of the output frame** (resolution-independent → identical on 1080p and 4K; NFR-014 parity).

```
Theme {
  id:          ThemeId            // stable slug, e.g. "classic-center"
  name:        String             // "Classic Center"
  background:  Background
  templates:   [Template]         // named slide designs within the theme
}

Background =
  | Solid   { color: Rgba }
  | Gradient{ from: Rgba, to: Rgba, angle_deg: f32 }     // R-later; seam noted
  | Image   { asset_id: AssetId, fit: Cover|Contain }    // R-later (needs S8-6 sandboxed decode)

Template {
  id:      TemplateId             // "scripture.full", "song.center", "lower-third"
  name:    String                 // "Full Screen", "Lower Third"
  role:    ContentRole            // which content kind this template renders
  background: Option<Background>  // overrides the theme background when set
  safe_area:  Insets              // percent insets (top/right/bottom/left)
  regions:    [Region]            // ordered; back-to-front paint order
}

ContentRole = Scripture | Song | Announcement | SermonPoint | LowerThird

Region {
  role:         RegionRole        // Body | Reference | Title | Footer | Custom
  rect:         Rect%             // { x, y, w, h } each 0..100 (% of frame)
  lock_aspect:  bool
  align_h:      Left | Center | Right
  align_v:      Top | Middle | Bottom
  typography:   Typography
  reference_gap: Option<f32>      // % of frame height between Body and Reference (Scripture only)
}

Typography {
  font_family:     FontId         // from the BUNDLED OFL set only (MVP)
  weight:          100..900       // subject to bundled weights (see Feasibility)
  size_pct:        f32            // % of frame HEIGHT; enforced floor ≥ 48px-equiv (NFR-020)
  line_height:     f32            // multiplier (e.g. 1.2)
  letter_spacing:  f32            // em
  color:           Rgba
  fit:             ShrinkToFit | Clip | Paginate   // region overflow policy; DEFAULT = ShrinkToFit
}
```

### RegionRole semantics
- **Body** — the primary content stream (verse text, lyric stanza lines, announcement body).
- **Reference** — the scripture reference line ("Genesis 1:1 (NKJV)"); styled independently, offset from Body by `reference_gap`.
- **Title** — item/section title (song title, announcement heading).
- **Footer** — copyright/CCLI (S8-5) or attribution; small, low-emphasis.
- **Custom** — a free text/shape region (future authoring).

---

## 3. Templates & per-item override

- A **theme carries multiple named templates**, one active default per `ContentRole` (scripture → `scripture.full`, song → `song.center`, lower-third → `lower-third`). The audience output selects the template matching the item's role.
- **Per-item override** (S8-3d): a `PlanItem` carries `theme_override: Option<ThemeId>` and `template_override: Option<TemplateId>`. Resolution order for an item: `template_override` → `theme_override`'s role default → **active global theme**'s role default. Switching the global theme leaves overridden items on their chosen design (no clobber). Overrides persist + survive crash recovery.

---

## 4. Feasibility (against the current compositor + cosmic-text shaper)

| Capability | Feasible now? | Note / seam |
|---|---|---|
| Percent position/dimension regions | ✅ | `compose` maps `Rect%` → pixel `Rect`; already region-based (safe-area). |
| Horizontal alignment (L/C/R) | ✅ | S8-2 gives glyph-run measurement (cosmic-text) → measure line width, offset within region. |
| Vertical alignment (T/M/B) | ✅ | Measure total block height, offset within region. |
| Per-region size / line-height / letter-spacing / colour | ✅ | cosmic-text `Attrs` + `Metrics`; already blends colour. |
| **Font weight / multiple families** | ⚠️ Partial | Only **Noto Sans-Latin Regular** is bundled today. Multi-weight/family needs bundling more OFL faces in S8-3b — until then the designer offers **1 family + synthesized weight** (or the bundled set). Flag in the picker. |
| **Solid background colour** | ✅ | `Frame::with_background`. |
| **Gradient / image background** | ❌ Deferred | Gradient = a compositor add; image needs the **S8-6 sandboxed decode** path. Model supports it; engine ships Solid first. |
| **Custom font import** | ❌ Deferred | FR-173 (untrusted-font hardening) — later. MVP = bundled OFL only. |
| **Overflow = `ShrinkToFit` (DEFAULT, all templates)** | ✅ | A measure-loop: shrink the region's `size` until the block fits `rect.h` (down to a min floor), so a long verse **never clips** — it scales to fit. This is the default `fit` for **every** built-in (owner direction). `Clip` and `Paginate` are opt-in via the designer's **Fit** control; full pagination is a later slice. |

**S8-3b/rev MVP cut:** Solid backgrounds, the bundled family, full alignment + per-region typography + reference styling, **`ShrinkToFit` overflow by default on all built-ins** (user-selectable via the Theme Designer's **Fit** control — Shrink to fit / Clip / Paginate), 3 built-in templates (scripture/song/lower-third). Gradient/image backgrounds, multi-family/weight, full pagination, custom-font import = flagged deferrals with the seams above.

> **Resolves the S8-3b review finding** (lower-third clipping a 6-line verse to ~2 lines): with `ShrinkToFit` as the default, switching a long verse into a small template **shrinks the text to fit the band** rather than dropping lines — a visual guarantee, not only a data one.

---

## 5. Theme Designer — interaction spec (per Pewbeam/ProPresenter)

**Layout (3 zones):**
- **Left rail** — theme list (thumbnails) + `＋ New` / `⤓ Import` / `⤒ Export`; search; **Scriptures / Slides** tabs (filter templates by role); each row `⋯` menu (Rename/Duplicate/Delete[T2 inline-confirm]).
- **Center canvas** — the 16:9 output preview with the selected template; **Add content** bar (Text · Scripture · Shape · Image[deferred]); elements selectable (click), movable (drag), resizable (handles); a real sample verse/lyric renders via the **live engine** (S8-3c) so preview == audience output.
- **Right inspector** — for the selected region: **Layout** (Alignment 9-point · Position X/Y · Dimension W/H · Lock aspect · Reference gap), **Typography** (Font · Weight · Size · Line height · Letter spacing · Colour), and **Fit** — a segmented control **Shrink to fit** (default) · **Clip** · **Paginate** that sets the region's overflow policy, so the author chooses how over-long content behaves. Collapsible sections.

**Save model:** autosaved continuously (FR-074); `Save changes` is an explicit commit affordance; edits **never touch Live** (FR-012) — the designer stages to preview only.

---

## 6. State matrix

| State | Trigger | Designer surface | Audience effect |
|---|---|---|---|
| **empty** | no themes yet / first run | left rail shows "Create your first theme / Import"; canvas empty-hint | none |
| **default** | a theme selected | canvas shows the template; inspector reflects the selected region | none (preview only) |
| **editing** | a field changed | live preview updates; row marked dirty; autosave pending | none until applied globally |
| **applying-template** | template applied to a group | brief "Applying…"; content re-lays-out; **overflow indicator** if it would clip (never truncate) | on next stage/Go-Live |
| **import-error** | bad/oversized theme file | inline error "Couldn't import — {reason}"; no partial apply | none |
| **save** | Save changes / autosave commit | "Saved" toast; row un-dirtied | persisted; recovery restores it |
| **overflow** | content > region | region shows an overflow badge; auto_fit policy applies (shrink/paginate) | content preserved, fitted |

---

## 7. Accessibility & output legibility

- **Audience text floor ≥ 48px-equivalent** (NFR-020); the size picker clamps below it with a warning. High-contrast template offered.
- **Designer UI:** WCAG AA on all inspector controls (tokens are AA-audited); full keyboard path — `Tab`/`Shift+Tab` cycle elements, arrows nudge (Shift ×10), `Cmd/Ctrl+]`/`[` reorder, `Esc` exits text edit (COMPONENT-SPECS §11); focus order Left → Canvas → Inspector; every control has an SR name; colour is never the only cue (labels on alignment/weight).
- **Contrast guard:** the designer warns when a region's text colour vs its background falls below AA on the audience output (reuses `tokens::contrast_ratio`).

---

## 8. Design-system usage

Bind all Designer chrome to the existing tokens (`DESIGN-TOKENS.md` / `tokens.rs`): bg/base `#0e1116`, bg/panel `#171b22`, border `#2b323d`, text/primary `#eef1f6`, accent green/red/amber. **Extend, don't fork.** The *audience-output* colours (background, text) are theme data, not chrome tokens — they're authored per-template.

---

## 9. Handoff → build

- **S8-3b (engine):** implement §2 model + §4 MVP cut; `compose` honours regions/alignment/typography/reference-gap; switch = recompose retained content (zero loss); persist active theme (additive migration) + recovery; 3 built-in templates from the Figma mocks.
- **S8-3c (Designer UI):** build §5 against the S8-3b engine (live preview == output); §6 states; §7 a11y.
- **S8-3d (templates + override):** §3 per-item override + named templates; overflow policy §4.

**Open decisions for the gate:** (a) how many built-in themes ship in MVP; (b) bundle additional OFL weights/families now or defer; (c) gradient background in MVP or R-later.
