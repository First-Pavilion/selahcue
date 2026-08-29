# Slide View Density — Grid / Text / List + size slider — Design Spec (UI-B1)

**Status:** design · **Owner:** /ui-ux-designer (Uma) · **ClickUp:** [`86ak7kgjk`](https://app.clickup.com/t/86ak7kgjk) (sequence #1, ★ owner-flagged)
**Requirements:** FR-205 (view-density cluster), FR-206 (thumbnail-size slider + persisted preference) · **NFR-201, NFR-205** · **METRIC-203/204**
**Supplies:** the thumbnail **size tiers** consumed by FR-207 / UI-B2 [`86ak7kgkg`](https://app.clickup.com/t/86ak7kgkg) — §5 is the contract between the two tickets.
**Sources:** PRD `SelahCue-Operator-UI-PRD.md` §14 EPIC-UI-B + "Designer detail — FR-205/206" · research §4.3, §7.4, §10.1 (E02, E23, E41) · `DESIGN-2.0-HANDOFF.md` §3.1/§4/§6 · the shipped console `implementation/desktop/crates/selahcue-operator/dist/`.
**Figma:** built — [Section: SelahCue · Operator UI MVP — EPIC-UI-A/B/C/D (RISK-205 Figma catch-up)](https://www.figma.com/design/SYQn5hFY8YVQKm3c6rw0eJ/SelahCue?node-id=965-124).
Frames: [01 — Grid, default (step 7 · 6 columns · tier M)](https://www.figma.com/design/SYQn5hFY8YVQKm3c6rw0eJ/SelahCue?node-id=971-124) · [02 — Grid at slider minimum (step 1 · 12 columns · tier S)](https://www.figma.com/design/SYQn5hFY8YVQKm3c6rw0eJ/SelahCue?node-id=973-124) · [03 — Grid at slider maximum (step 9 · 4 columns · tier L)](https://www.figma.com/design/SYQn5hFY8YVQKm3c6rw0eJ/SelahCue?node-id=973-312) · [04 — Text mode, incl. an image-only slide](https://www.figma.com/design/SYQn5hFY8YVQKm3c6rw0eJ/SelahCue?node-id=974-124) · [05 — List mode, slider inert](https://www.figma.com/design/SYQn5hFY8YVQKm3c6rw0eJ/SelahCue?node-id=974-229) · [06 — One row per group](https://www.figma.com/design/SYQn5hFY8YVQKm3c6rw0eJ/SelahCue?node-id=975-124) · [07 — The three thumbnail tiers at true pixel size](https://www.figma.com/design/SYQn5hFY8YVQKm3c6rw0eJ/SelahCue?node-id=976-124) · [08 — Cluster anatomy, ⋯ menu, narrow collapse](https://www.figma.com/design/SYQn5hFY8YVQKm3c6rw0eJ/SelahCue?node-id=976-166) · [09 — Edge and failure states](https://www.figma.com/design/SYQn5hFY8YVQKm3c6rw0eJ/SelahCue?node-id=975-271).
In context, at real scale in the shipped console shell: [IN CONTEXT · 01 — console today (baseline)](https://www.figma.com/design/SYQn5hFY8YVQKm3c6rw0eJ/SelahCue?node-id=977-124) · [IN CONTEXT · 02 — console with UI-B1](https://www.figma.com/design/SYQn5hFY8YVQKm3c6rw0eJ/SelahCue?node-id=978-139).
Also: [legend + open questions](https://www.figma.com/design/SYQn5hFY8YVQKm3c6rw0eJ/SelahCue?node-id=965-125). The frames are drawn from this spec and the shipped `--sc-*` token values, not copied from the existing Design 2.0 frames (RISK-205: those lag the console on contrast). Chips read **PREVIEW / LIVE** pending Priya's ruling (F3). Colours bind to `sc/*` variables added to the file's `SelahCue Color` collection at their shipped values; the six structure-palette trios are present and marked **PROPOSED**.
PRD **RISK-205** directed that "Uma designs from the live console + tokens, Figma updated after"; this line records that the second half is now done. Two things only became visible once drawn to scale and are annotated on the frames: the 20px group footer strip does not fit a tier-S card (frame 02), and at the assumed default a 24-slide deck needs four rows where the real panel fits three (IN CONTEXT · 02).

> **Read this first.** "View mode" in this document means **density** — how many slides fit and how much of each you see. It is **not** a colour mode and it is **not** a theme. A SelahCue *theme* is a slide-design template (`THEME-MODEL-spec.md`). Nothing in this cluster may ever be worded in a way that lets an operator read it as a colour theme; §14 pins the copy.

---

## 0. The decisions this spec makes

| # | Decision | Why |
|---|---|---|
| D1 | Modes are named **Grid · Text · List**. | The vendor's own two current articles disagree on their view names (E02 vs E01). We do not import unstable vocabulary. |
| D2 | The size control is a **9-step slider** whose value is a *size step*, not a column count; the column count is derived (§4). | A step is meaningful in every mode and on every panel width; a raw column count is not. |
| D3 | Grid mode **wraps** in the console Slides tab. Today that panel is a one-row horizontal filmstrip. | A single row cannot honour a column count, so FR-206's "min 4 / max 12 columns" is unsatisfiable without this. See §15-F1 — this is a real change to a shipped surface and is flagged, not smuggled. |
| D4 | Three quantised engine thumbnail tiers — **S 192×108 · M 320×180 · L 480×270** — and CSS-scaling between them. | Bounds the cache at `3 × visible slides` (CON-U5) and honours the engine's ≤480×270 clamp. |
| D5 | Chips keep the **shipped vocabulary `PREVIEW` / `LIVE`**, not the ticket's "STAGED / ON AIR". | The console and Design 2.0 §2 both already say PREVIEW/LIVE; a second vocabulary for the same two states inside the same grid is worse than matching the ticket's literal words. Flagged for Priya — §15-F3. |
| D6 | The slider is **inert in List mode** (`aria-disabled`, still focusable, reason announced). | List is one full-width row per slide; there is no column count to set. Row-height density was considered and rejected — §4.4. |
| D7 | One component, one store, **two keys** — `console.slides.*` and `library.grid.*`. | The ticket asks for "one preference store" *and* "per-operator per-surface". Both are true: one table, two scoped keys. |

---

## 1. Where it lives (IA)

One component, mounted in two places. **No new surface.**

| Host surface | Container today | Cluster mount point |
|---|---|---|
| **Console → Slides tab** | `#cpanel-slides` → `#slide-strip` (`role="listbox"`, cards `role="option"`) | a new `.slides-foot` footer row, right-aligned, below the slide area and **above** the pinned emergency footer |
| **Presentations Library → slide grid** | `#pm-grid` → `#pm-grid-tiles` (`role="listbox"`, tiles `role="option"`) | a new `.pm-grid-foot` footer row, right-aligned, below the tiles and above `#pm-transport` |

The cluster is always the **last** thing in its panel's DOM and reading order, after the slides. It never floats over content and never overlaps the emergency footer (`NAV-IA-spec.md` §2 invariant).

Both hosts keep their existing `listbox`/`option` semantics in all three modes. Only the visual arrangement and the per-option content change.

---

## 2. Anatomy of the cluster

```
                                   ┌─ radiogroup "Slide view" ─┐  ┌ menu ┐  ┌──── slider ─────┐
   … slides … … … … … … … … … …   [ ⊞ Grid ][ ≡ Text ][ ☰ List ]   [ ⋯ ]   Size ──────○───   
```

- **Height** 40px. **Gap** 12px between the three groups, 3px inside the segmented track.
- **Segmented control** — the Design 2.0 §4 primitive verbatim: `--sc-inset` track, 3px inset, radius 8; the active segment is `--sc-primary` fill with `--sc-text` label. Each segment is icon **+ text label** (never icon-only — the three icons are not self-evident and a booth operator should not have to hover).
- **`⋯` options** — a 28×28 ghost button opening the options menu (§6).
- **Slider** — a visible `Size` label in `--sc-text-secondary`, then a 120px native `input[type=range]`.
- At panel widths below **560px** the segment text labels collapse to icons and the `Size` word is dropped, leaving the slider. Below **420px** the slider is dropped entirely and the size steps move into the `⋯` menu as a submenu. Nothing is ever silently lost.

---

## 3. The three modes

### 3.1 Grid (default — see §16/OQ-1)

A wrapping grid of 16:9 thumbnail cards. `grid-template-columns: repeat(var(--sc-slide-cols), minmax(0, 1fr))`, gap 10px, card radius 12.

Per card: the engine thumbnail, the slide number (top-left, existing `.slide-card-n`), the group colour band along the bottom edge if the deck is a song (**FR-210 — see `SONG-GROUPS-HOTKEYS-spec.md`**; it must render identically here and in Text and List), the attention badge if any (**FR-204 — see `ATTENTION-BADGES-spec.md`**), and the PREVIEW/LIVE chip when applicable.

### 3.2 Text

No thumbnails. Same grid geometry and same column count, but each cell is a text card on `--sc-inset`: slide number, then the slide's text lines at 13px/1.45 in `--sc-text`, clamped to 6 lines with a trailing ellipsis. The group colour band and badges stay.

This is the lyrics-scanning view. It must not request thumbnails at all — entering Text mode issues **zero** engine calls.

### 3.3 List

One full-width row per slide, 44px tall, radius 11, `--sc-elevated`, in a single column regardless of the slider.

Row layout, left to right: `[state chip] [n] [group swatch + name] [first line of text, ellipsized] … [badges] [duration if set]`.

The state chip column is fixed-width and always reserved, so rows do not shift when a slide becomes staged or live.

---

## 4. The size slider (FR-206)

### 4.1 Value model

`<input type="range" min="1" max="9" step="1">`. The value is a **size step**; larger step = larger thumbnails = fewer columns.

| Step | 1 | 2 | 3 | 4 | 5 | 6 | **7** | 8 | 9 |
|---|---|---|---|---|---|---|---|---|---|
| Columns | 12 | 11 | 10 | 9 | 8 | 7 | **6** | 5 | 4 |
| Tier (§5) | S | S | S | S | M | M | **M** | L | L |

Step **7** (6 columns, tier M) is the default. FR-206's "min 4 / max 12 columns-equivalent" is satisfied at the two ends.

### 4.2 Behaviour

- Dragging re-flows the grid **live**, on every step crossed, with no commit gesture.
- The column change is instantaneous (`grid-template-columns` swap). Card width may transition 120ms `ease-out`; that transition is **suppressed** under `prefers-reduced-motion`.
- Crossing a **tier** boundary (steps 4→5 and 7→8) triggers new engine thumbnail requests for the visible slides only. Within a tier, the existing textures are CSS-scaled and **no** engine call is made.
- At step 1 and step 9 the slider clamps with a visible end tick and a single soft detent; no wrap-around, no error.

### 4.3 Keyboard

On the focused slider: `←`/`↓` and `-` decrease one step; `→`/`↑` and `+` (and `=`) increase one step; `Home` → 1; `End` → 9; `PageUp`/`PageDown` → ±3. All of these `stopPropagation()` so they never reach the canonical keymap's Previous/Next — the same scoping the shipped filmstrip already uses (`app.js:4811`).

### 4.4 List mode

The slider is `aria-disabled="true"`, visually dimmed, **still focusable**, and `-`/`+` are no-ops. Its `aria-describedby` points at helper text: *"List view shows one slide per row — size doesn't apply."*

*Considered and rejected:* repurposing the slider to row height in List mode. It makes the same control mean two different things, gives the operator no way to know which meaning is active, and there is no user problem behind it. An honestly inert control is better than a quietly reinterpreted one.

---

## 5. Thumbnail size tiers — the contract UI-B2 consumes

**This section is the interface between UI-B1 (design) and UI-B2 / FR-207 (engineering, [`86ak7kgkg`](https://app.clickup.com/t/86ak7kgkg)).** UI-B2 owns the cache, its bounds and its LRU test; it does not choose the tiers. These are the tiers.

| Tier | Engine request | Aspect | Serves steps | Serves columns |
|---|---|---|---|---|
| **S** | **192 × 108** | 16:9 | 1–4 | 9–12 |
| **M** | **320 × 180** | 16:9 | 5–7 | 6–8 |
| **L** | **480 × 270** | 16:9 | 8–9 | 4–5 |

Rules that go with them:

1. **Three tiers, forever three.** The cache key is `(deckId, slideId, tier)`; the entry bound is therefore `3 × visible slides`, which is what makes CON-U5 satisfiable. Adding a fourth tier is a PRD change, not an implementation choice.
2. **Quantise, then CSS-scale.** Never request a per-pixel-perfect size per slider tick. Between tier boundaries the card grows or shrinks by CSS only.
3. **L is the ceiling.** 480×270 is the engine's existing clamp on the read-only preview path (`GetConsoleThumbnails` / `GetScreenFrame`). Do not raise it, and do not multiply by `devicePixelRatio` — on a HiDPI display an L card upscales, which is correct and cheap; a 2× request would double the cache for a thumbnail nobody inspects at pixel level.
4. **Tier changes fetch visible slides only**, through the same lazy `IntersectionObserver` the console and library grids already use (`app.js:4930`, `app.js:7509`).
5. **Text mode requests nothing.** List mode requests nothing.
6. The path stays the **read-only preview path** (CON-U1). The WebView never renders audience output; it displays engine-produced textures.

---

## 6. The `⋯` options menu

`role="menu"`, opens above the button (the cluster sits at the panel bottom), closes on `Esc` with focus returned to the `⋯` button, never traps focus over the emergency footer.

| Item | Type | Applies to | Behaviour |
|---|---|---|---|
| **One row per group** | `menuitemcheckbox` | Grid, List | Starts each song group on a fresh row (Grid) or inserts a group divider row (List). Off by default. Inert and dimmed in Text mode, with the reason in its `aria-describedby`. |
| **Reset view to default** | `menuitem` | all | Restores Grid, step 7, group-rows off, for **this surface only**. |
| *(footer, not focusable)* | static text | — | "These settings apply to the **Slides** tab." / "… to the **Presentations Library**." — the one place the per-surface scope is explained, so the operator is never puzzled that the two surfaces differ. |

---

## 7. State matrix

| State | Trigger | Treatment |
|---|---|---|
| **grid** | default, or Grid selected | wrapping thumbnail grid at the current step |
| **text** | Text selected | text cards, same columns, zero thumbnail fetches |
| **list** | List selected | one row per slide, single column, slider inert |
| **group-rows on** | options menu | Grid: each group starts a new row. List: a group divider row precedes each group |
| **slider at min** (step 1) | drag/`Home`/`-` | 12 columns, end tick shown, further `-` is a no-op |
| **slider at max** (step 9) | drag/`End`/`+` | 4 columns, end tick shown, further `+` is a no-op |
| **restored-on-boot** | app start | panel paints **once**, already at the stored mode and step — never default-then-reflow (§11) |
| **preference unreadable** | settings table read fails | silently fall back to Grid + step 7; log; do **not** show an error — this is cosmetic state and an error banner here would be noise |
| **empty deck** | no slides | the existing `#slides-empty` / `#pm-grid-empty` empty state; the cluster **stays visible and enabled** so the operator can set up their view before content arrives |
| **thumbnail render failed** | engine returns unavailable | the existing `.slide-card-fail` in-card message; the card keeps its number, chip and badges; other cards are unaffected |
| **narrow panel** | < 560px / < 420px | progressive collapse per §2 |

---

## 8. Edge cases

- **Image-only slide in Text mode** — the text card shows the slide number and the hint *"Image slide"* in `--sc-text-secondary`, plus the group band. Never an empty cell. If the slide has an image with a known filename, the hint reads *"Image slide · backdrop.jpg"*.
- **Extremely long lines** — ellipsized with `text-overflow: ellipsis`; the full text is available on hover **and on keyboard focus** (a `title` alone is mouse-only, so the full text also goes in the option's `aria-label`).
- **PREVIEW and LIVE markers survive every mode.** Grid and Text: 2px card border plus the corner chip. List: the leading state-chip column. There is no mode, no step and no group-rows setting in which a staged or live slide is unmarked. This is the single most important visual invariant in the cluster.
- **A slide is both staged and live** — LIVE wins on the border and the chip; the shipped `mark()` already resolves it this way (`app.js:4839`), and the aria-label appends "(live on the audience output)".
- **Group-rows on, with 12 columns and a two-slide group** — the row is left-ragged. Accepted; forcing justification would misrepresent group sizes.
- **Changing mode while a drag of the slider is in flight** — the mode buttons are inert during an active pointer drag on the slider; releasing re-enables them.
- **A deck loads while the operator is mid-drag** — the new deck renders at the current step; the drag is not interrupted.

---

## 9. Keyboard map and focus order

**Focus order within the panel:** slides listbox (one roving tab stop) → `Grid`/`Text`/`List` radiogroup (one roving tab stop) → `⋯` → slider. Then out to the next panel, and ultimately the emergency footer.

| Key | Where | Action |
|---|---|---|
| `←` `→` | segmented control | previous / next mode, activating on move (standard radiogroup) |
| `Home` `End` | segmented control | first / last mode |
| `←` `→` | slides listbox | previous / next slide (stages it — Preview only) |
| `↑` `↓` | slides listbox, Grid/Text | move by one **row** (± current column count). **New** — today the strip is one row and maps ↑/↓ to ±1 (`app.js:4823`) |
| `↑` `↓` | slides listbox, List | previous / next row |
| `Home` `End` | slides listbox | first / last slide |
| `⏎` | slides listbox | **Go Live** — the canonical keymap path, unchanged and never overloaded |
| `-` `+` `=` `←` `→` `↑` `↓` `Home` `End` `PgUp` `PgDn` | slider | §4.3 |
| `Esc` | `⋯` menu | close, return focus to `⋯` |
| **`` ` `` (Backquote), held** | slides listbox | *Optional, "could" only.* Hold-to-peek Text view; release restores the previous mode. Bound to `event.code === "Backquote"` so it is layout-stable, and **only** while the listbox has focus. It is free against the canonical keymap (`selahcue-app/src/keymap.rs` claims only `Space` `→` `←` `Enter` `Esc` `B` `Backspace`). Ship it only if it costs nothing; it is not an acceptance criterion. |

All cluster keys `stopPropagation()`. No new global chord is introduced, so there is nothing to collide with the canonical keymap (AS-U4).

---

## 10. Accessibility annotations

- **Segmented control** — `role="radiogroup"` with `aria-label="Slide view"`; each segment `role="radio"` with `aria-checked`. Roving `tabindex`. Not a set of toggle buttons: exactly one is always chosen, which is what `radiogroup` means.
- **Slider** — `role="slider"` (native `input[type=range]`), `aria-label="Thumbnail size"`, `aria-valuemin="1"`, `aria-valuemax="9"`, `aria-valuenow="<step>"`, and **`aria-valuetext`** carrying the human reading:
  - Grid / Text: `"Medium — 6 columns"` (size name + column count, per the ticket)
  - List: `"Size not applicable in list view"`
  The size names are **Smallest, Smaller, Small, Compact, Medium‑, Medium, Medium+, Large, Largest** for steps 1–9.
- **Mode change announcement** — a `role="status"` (polite) region in the panel announces `"Grid view, 6 columns, 24 slides"`. It does **not** re-announce on every slider step; it debounces 400ms after the last change, so dragging does not flood a screen reader.
- **Colour is never the only cue (WCAG 1.4.1)** — PREVIEW/LIVE are a coloured border **and** a text chip in every mode. Group colours are a band **and** the group name (§FR-210). Badges are a colour **and** a shape **and** an accessible name.
- **Focus visible** — 2px `--sc-primary-hover` ring at 2px offset, the shipped treatment (`app.css:3610`). Selection uses a violet fill/inset ring, so focus and selection stay distinguishable by geometry even at the same hue (Design 2.0 §6).
- **Reduced motion** — the card-width transition and the slider detent animation are suppressed. Nothing in the cluster is animation-dependent.
- **Touch targets** — the segments are 32px tall inside a 40px row; the slider thumb is 20px with a 32px hit area. Desktop surface, so 44pt is not required, but nothing is below 32px.

---

## 11. Persistence (NFR-201, METRIC-203)

**Store:** the existing settings table, per host. `localStorage`-class storage alone is **not** sufficient — the console WebView can reset, and the PRD calls this out explicitly.

**Keys** (six, three per surface):

```
console.slides.viewMode   grid | text | list      default grid
console.slides.sizeStep   1..9                    default 7
console.slides.groupRows  bool                    default false
library.grid.viewMode     grid | text | list      default grid
library.grid.sizeStep     1..9                    default 7
library.grid.groupRows    bool                    default false
```

"Per-operator" on a desktop-authoritative single-console app means **per host install**; there is no operator account on this surface. Stated so nobody builds a user-scoped store that has no user.

**Restore must not flash.** The preference read joins the same boot query batch that fetches the deck — not a second round trip after first paint. The slides panel paints once, already at the stored mode and step. A default-then-reflow would be visible, would feel broken, and would not meet the <100ms restore budget in perception even if it met it on the clock.

**Offline:** the settings table is local. Nothing here touches the network, so "restore on boot with network disabled" is satisfied by construction, not by a fallback path.

**Validation on read:** an out-of-range step clamps to 1–9; an unknown mode string falls back to `grid`. A corrupt value never blocks boot.

---

## 12. Tokens and redlines (Design 2.0)

Everything below already exists in `dist/app.css:29-56`. No new token is introduced.

| Element | Token | Value |
|---|---|---|
| Cluster row background | inherits panel `--sc-surface` | `#14161D` |
| Segmented track | `--sc-inset` | `#0F1116` |
| Segment, active | `--sc-primary` fill, `--sc-text` label | `#6E5CF0` / `#F4F6FB` |
| Segment, inactive label | `--sc-text-secondary` | `#A7AEBE` |
| `Size` label, helper text, "Image slide" hint | `--sc-text-secondary` | `#A7AEBE` |
| Card / row background | `--sc-inset` (Grid, Text) · `--sc-elevated` (List) | `#0F1116` / `#1C1F28` |
| Card border, hover | `--sc-border-strong` | `#363B47` |
| Card border, staged | `--sc-preview` | `#35C08A` |
| Card border, live | `--sc-live` | `#FF4D4D` |
| Focus ring | `--sc-primary-hover` | `#7E6EFF` |

### Two redlines against what ships today

**R1 — the `LIVE` chip on console slide cards fails AA; fix it.**
`.slide-card-tag.live` is `color:#fff` on `background: var(--sc-live)` (`app.css:3620`). White on `#FF4D4D` measures **3.27:1**, below AA for its 10px bold text. Change it to the Design 2.0 status-chip treatment already used by the library tile (`.pm-tile-live`, `app.css:6285`): `--sc-live` ink on `--sc-live-soft` with a 1px `--sc-live-border` — **5.31:1**.
This is *not* one of the three pinned inks. GO LIVE (8.70:1), BLACKOUT (7.19:1) and primary (4.72:1) are untouched by this cluster. CON-U7 forbids regressing them and welcomes improving what is genuinely open; this is the latter.
For symmetry the `PREVIEW` chip moves to the same treatment: `--sc-preview` on `--sc-preview-soft` + `--sc-preview-border` = **7.08:1** (today's `#05261a` on `--sc-preview` is 6.97:1, so this is a small gain and a large consistency gain).

**R2 — do not use `--sc-text-muted` anywhere in this cluster.**
`--sc-text-muted` `#6B7383` on `--sc-surface` measures **3.79:1** — the known open item across roughly 79 small-type sites. Every small label in this cluster uses `--sc-text-secondary` (**8.13:1**) instead. This adds no new failing site and quietly reduces the count by not growing it.

---

## 13. How CON-U2 is made structural, not merely intended

The cluster must be **incapable** of changing what the audience sees. "We didn't wire it up to anything live" is an intention. These are the properties:

1. **No control in the cluster dispatches a host command.** Mode, step and group-rows write to the settings table and to CSS custom properties. They never call `invoke()` on a controller command.
2. **Thumbnails come from the read-only preview path only** — `GetConsoleThumbnails` / `GetScreenFrame` and the existing `render_plan_deck_slide`. None of these has a Live write path.
3. **Mode switching does not touch selection.** The staged slide index and the live slide id are inputs to the render, never outputs of it. Re-rendering the panel in a different mode re-reads the same two values and re-marks the same slides.
4. **Reordering is impossible.** The grid renders slides in deck order; the cluster exposes no reorder, no delete, no edit.

**Testable form, for QA and for METRIC-204:** with a slide live on the audience output, exercise every mode, every one of the nine steps, and the group-rows toggle, and assert through the ADR-0015 fault-injection/pixel-readback seam that the live frame is byte-identical throughout and that zero frames were dropped. Visual inspection does not satisfy this (PRD §29).

---

## 14. Copy

| Element | Copy | Note |
|---|---|---|
| Radiogroup label | **Slide view** | Not "view mode", not "display mode", never "theme" |
| Segments | **Grid** · **Text** · **List** | |
| Slider label | **Size** | Not "zoom" — zoom implies magnifying one thing, this changes how many you see |
| Slider helper (List) | List view shows one slide per row — size doesn't apply. | |
| Options item | One row per group | |
| Options item | Reset view to default | |
| Options footer | These settings apply to the **Slides** tab. | Library variant: "… to the **Presentations Library**." |
| Text-mode hint | Image slide | with `· filename` when known |
| Status announcement | Grid view, 6 columns, 24 slides | |

The word **theme** must not appear anywhere in this cluster, its menu, its tooltips or its settings labels.

---

## 15. Findings — where the ticket could not be built as literally written

These are reported, not silently resolved.

**F1 — Grid mode changes the console Slides tab from a one-row filmstrip to a wrapping grid.**
`#slide-strip` today is `display:flex; overflow-x:auto` with fixed 168px cards (`app.css:3596-3605`) — a single horizontal row. FR-206's "min 4 / max 12 columns" cannot be satisfied by a one-row strip, so Grid mode must wrap. The keyboard model, `scroll-snap` and the `listbox`/`option` semantics carry over unchanged; the panel scrolls vertically instead of horizontally.
*Implementation trap, from prior WKWebView experience:* a grid inside a flex child needs `min-height: 0` on the flex child, and implicit auto-rows will otherwise overflow past the pinned emergency footer. This shows up in WKWebView and **not** in the Blink headless gate, so it must be verified with a real render (`scripts/operator_webkit_smoke.py`), not only `scripts/operator_headless.py`.
*If the owner wants the horizontal filmstrip kept*, that is a **fourth** mode ("Strip") and therefore a PRD change, not something this ticket can decide.

**F2 — "one shared component, one preference store" and "per-operator per-surface" read as contradictory.**
Resolved as D7: one component, one settings table, two key namespaces. Recording it because a reader of the ticket alone would reasonably build a single shared value.

**F3 — the ticket says the chips read `STAGED` / `ON AIR`; the shipped console says `PREVIEW` / `LIVE`.**
Design 2.0 §2 also says PREVIEW/LIVE. I have kept the shipped words (D5). The requirement being protected — a text label always accompanies the frame — holds either way. **Priya to confirm which vocabulary is canonical**, because it also touches UI-C1's announcement ("Staged: Chorus 1") and UI-D1's screen labels. My recommendation: chips stay the nouns `PREVIEW`/`LIVE`; announcements keep the verb "Staged", which reads naturally in a sentence and badly on a 10px pill.

**F4 — `aria-valuetext` "6 columns" is only true where columns exist.**
Kept verbatim in Grid and Text; in List it reads "Size not applicable in list view" (§10). Noted because the ticket quotes the literal string.

---

## 16. Open questions carried — assumptions, not decisions

> **OQ-1 is unanswered. The following is the PRD's stated consequence of silence, taken as an assumption awaiting owner confirmation. It is not a decision, and nothing here closes OQ-1.**
>
> **Assumed:** new operators get **Grid** at **step 7 — 6 columns, tier M**.
> **Reasoning offered to the owner, not asserted over them:** "middle tier" identifies M unambiguously; within M's range of 6–8 columns I have taken the *low* end, because the design target is the volunteer on a 13" laptop (G-4), and 6 columns keeps a thumbnail legible there while a 27" operator is one drag from 12. If the owner prefers the power-operator default, step 5 (8 columns) is the other defensible answer and is a one-line change to `console.slides.sizeStep`.
> **Cost of a late change:** one default constant per surface. No layout, no state, no acceptance criterion depends on it.

**OQ-8 is answered** — keep the staging invariant *and* add a double-click accelerator. The acceptance criteria in this spec therefore stand as written and CON-U2 is unchanged. The accelerator itself is specified separately, as a proposal, in **`DOUBLE-CLICK-GO-LIVE-proposal.md`** — it lands on this grid but it is not this ticket's requirement, and it needs an FR of its own before it is built.

**DEC-016 remains PROPOSED.** This spec does not change that.

---

## 17. Handoff and QA

**Build order:** (1) the cluster component + settings keys + restore-on-boot; (2) Grid wrapping and the column custom property; (3) Text; (4) List; (5) group-rows; (6) the R1/R2 token redlines. UI-B2's tier work (§5) can proceed in parallel once the tier table is agreed — it is the only cross-ticket dependency.

**QA steps** (the list-form version is posted on the ticket):

1. Open a deck of ≥24 slides in the console Slides tab. Confirm Grid, 6 columns, on a first run with no stored preference.
2. Step the slider 1 → 9. Confirm 12 → 4 columns, end ticks at both extremes, and no engine fetch except when crossing steps 4→5 and 7→8.
3. Switch Grid → Text → List → Grid. Confirm each switch completes in <100ms and that **no thumbnail is re-fetched** by the mode switch itself.
4. With a slide staged and a *different* slide live, cycle all three modes and all nine steps; confirm both markers stay visible and correctly attributed in every combination.
5. Put a slide on the audience output. Repeat step 4 while capturing the live frame through the ADR-0015 seam; confirm byte-identical frames and zero dropped frames throughout (METRIC-204).
6. Set Text + step 3 in the console; set List in the Presentations Library. Restart the app with the network disabled. Confirm both surfaces restore independently, in one paint, with no default-then-reflow flash.
7. Corrupt a stored value (step `99`, mode `"purple"`). Confirm a clean fallback to Grid/step 7 with no error banner and no boot delay.
8. Keyboard only: tab to the radiogroup, change mode with `←`/`→`; tab to the slider, change with `-`/`+`, `Home`, `End`; confirm `⏎` in the slides listbox still goes live and that arrows inside the listbox never fire the global Previous/Next.
9. Screen reader: confirm `aria-valuetext` reads "Medium — 6 columns", that a mode change announces once (not per slider tick), and that the List-mode slider announces why it is inert.
10. Text mode on an image-only slide: confirm "Image slide", never a blank cell. Long line: confirm ellipsis plus full text on focus, not hover alone.
11. Contrast: measure the `LIVE` chip after R1 — expect ≥5.3:1. Re-run the token audit and confirm GO LIVE 8.70:1, BLACKOUT 7.19:1 and primary 4.72:1 are unchanged.
12. Render in **WKWebView**, not only headless Chrome: confirm the wrapped grid scrolls inside its panel and never overflows past the pinned emergency footer (F1).
