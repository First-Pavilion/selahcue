# Presentation & Media — Interaction & State Design Spec

> **Story:** 86ajvjqw4 · **Epic:** Presentation & Slides (86ajp07ce) · **Design:** Figma
> `SYQn5hFY8YVQKm3c6rw0eJ` node **329:124** ("Presentation & Media — Design 2.0") + the **States**
> section authored alongside it (§9). · **Implements design for:** 86ajvccqr (console UI, shipped/QA)
> + 86ajv8qd9 (engine). · **Extends, does not restate:** `CANVAS-EDITING-spec.md` (86ajq6j29) §1/§2/§7/§8,
> `UX-STATE-MATRIX.md` §5, `THEME-MODEL-spec.md` §7, `UX-CANONICAL.md`, `DESIGN-TOKENS.md`.

## What this is

Node 329:124 shows exactly **one** state — a text element selected on the scripture slide. It has no
design for the other interaction/system states, so the shipped implementation had to infer them. This
spec designs **every** state of the Presentation & Media surface and the owner-chosen **right-side
per-element inspector**, so the surface can be built/verified without guessing and the design is the
source of truth. The shared element-editing *model* (select/move/resize/arrange/delete, the 8-handle
overlay, the keyboard grammar) already lives in `CANVAS-EDITING-spec.md`; this spec **references** it and
adds the Presentation-specific surfaces (the SLIDES rail, the media library, the bottom bar, present/live)
and the **inspector**.

### Owner decisions (2026-08-04)
1. **Deliverable** = Figma state frames (§9) + this spec.
2. **Editing model** = a **right-side per-element inspector** (like the Theme Designer / CANVAS-EDITING-spec
   §5). The right 360px column becomes **contextual**: the **Media Library** by default, the **Inspector**
   when an element is selected (§2). This is richer than the shipped on-canvas+keyboard-only model.

### Design ↔ implementation delta (honest)
The shipped surface (86ajvccqr) edits elements with the **on-canvas selection box + keyboard only** — there
is **no inspector**. This spec introduces one; that is an **implementation-rework follow-up** (§8). Until it
lands, the shipped on-canvas + keyboard model remains the valid interim (it is already accessible and
FR-012-safe). Everything below is design-authoritative; the traceability table (§7) marks each row as
**shipped**, **rework**, or **new**.

### Tokens (from `DESIGN-TOKENS.md` / `app.css`)
`--sc-base #0b0d12` · `--sc-surface #14161d` · `--sc-elevated #1c1f28` · `--sc-inset #0f1116` ·
`--sc-border #262a34` · `--sc-border-strong #363b47` · `--sc-text #f4f6fb` · `--sc-text-secondary #a7aebe` ·
`--sc-primary #6e5cf0` (selection/active) · `--sc-live #ff4d4d` (LIVE only) · `--sc-preview #35c08a` ·
`--sc-warn #f5a524` · `--sc-gold #f2b84b`. **Selection accent = `--sc-primary`** (a chrome accent — *not*
the reserved `--sc-live`/`--sc-preview` output-status tokens, per CANVAS-EDITING-spec §1). No state is
signalled by colour alone.

---

## 1. Surface anatomy (baseline, node 329:124)

```
┌ TOPBAR  ▦ Presentation · <deck name> · N slides            [Add to plan] [▶ Present] ┐
├───────────┬────────────────────────────────────────────────────┬──────────────────────┤
│ SLIDES    │  ┌ TOOLBAR  T Text · ▢ Shape · 🖼 Image · ▶ Video · 🎨 Bg · ↶ ↷ · Slide N/M │
│ (220px)   │  │ CANVAS ZONE (16:9 letterboxed native preview)                       │  R  │
│ 1 ▢       │  │            [ selected element → box + 8 handles ]                   │  I  │
│ 2 ◀ sel   │  │                                                                     │  G  │
│ 3 …       │  └ BOTTOM BAR  📝 notes            Transition [Fade▾]  Auto-advance [Off▾] │  H  │
│ + Add     │                                                                          │  T  │
└───────────┴────────────────────────────────────────────────────┴──── 360px ─────────┘
```
The **right 360px column (R)** is the contextual panel — §2. Emergency Clear/Blackout chrome and the
Present control stay present + operable in **every** state (UX-STATE-MATRIX §1 invariant). Editing never
touches Live (FR-012) in any state below.

---

## 2. The contextual right panel — Media Library ⟷ Inspector (NEW, core decision)

The right column has two **modes**, switched by selection, with a persistent 2-tab header so the operator
always knows where they are and can move between them by pointer OR keyboard:

```
┌ [ Media ] [ Inspector ]  ← segmented tabs (roving tabindex; the active one is aria-selected) ┐
│ …the active mode's body…                                                                     │
└──────────────────────────────────────────────────────────────────────────────────────────────┘
```

- **Default mode = Media Library** (the shipped panel: Import · All/Images/Video/Audio filters · search ·
  grid · AUDIO · storage footer). The **Inspector** tab is **disabled** ("Select an element") when nothing
  is selected.
- **Selecting an element** (click on canvas, `Tab` to it, or add one) **auto-switches to the Inspector**
  and binds it to that element. **Deselecting** (`Esc`, click empty canvas, delete) returns to **Media**.
- The operator can also switch **manually** via the tabs (e.g. keep the Inspector open while browsing media
  is *not* allowed in one panel — switching tabs is explicit; selection drives the auto-switch).
- **A11y:** `role="tablist"` with two `role="tab"` buttons controlling one `role="tabpanel"`; roving
  tabindex + `Left/Right/Home/End`; the auto-switch on selection announces *"Inspector — {kind} element
  selected"* via a polite live region; focus moves to the panel's first control only on an **explicit** tab
  activation, never on the auto-switch (so a canvas drag-select doesn't yank focus off the canvas).
- **Rationale:** keeps the 329:124 3-column layout (no 4th column, no canvas shrink), reuses the 360px, and
  matches the Theme Designer's right-inspector muscle memory. The Media Library is one tab away at all times
  (needed while placing images).

### 2a. The per-element Inspector — variants

Common header for all kinds: **`{kind} element` title · `n of m` (paint order) · `👁 visibility` toggle ·
`🗑 Delete`**. Common **Arrange** row: **Send to back · Backward · Forward · Bring to front** + a
**behind/in-front-of the slide** chip (the z-badge from CANVAS-EDITING-spec §1). Common **Position/Size**:
X · Y · W · H in per-mille (or %) + **Lock aspect** (image/shape) — mirrors the on-canvas 8 handles. Common
**Opacity** slider. All controls are `--sc-*`, AA, keyboard-operable, and each commit announces (e.g.
"width 42%").

| Kind | Inspector body (kind-specific, above the common rows) |
|---|---|
| **Text** | multi-line **content** field (the live text) · **Font** (system-font picker, bundled default) · **Size** (‰ of height) · **Weight** · **Line-height** · **Align** H (`≡ ≣ ≡`) + V (top/middle/bottom) · **Colour** · **Fit** (Shrink-to-fit default / Clip). |
| **Shape** | **Fill** colour · **Border** colour + thickness · **Corner radius** (rounded-rect) · **Shape kind** (rect / rounded / ellipse / triangle — the engine's `ShapeKind`). |
| **Image** | **source thumbnail + file name** (or the **⚠ Missing — relink** state, §5.4) · **Replace…** (opens the media library filtered to images, or the host picker) · **Fit** = **Fill / Fit / Stretch** (default Fill — the engine stretches today; Fit/letterbox is the design target, flagged as a render seam) · a **"Reveal in Media Library"** link. |

**Image-selected is the row the owner specifically called out:** the inspector shows the bound asset (name
+ thumb), a **Replace…** action, a **Fit** control, and — when the asset is missing — the inline **relink**
affordance, so a selected image is never a dead end.

---

## 3. State matrix — element selection (canvas)

The selection overlay itself (1px `--sc-primary` outline + 8 handles + z-badge) and the shared
select/move/resize/arrange/delete grammar are **CANVAS-EDITING-spec §1/§2** — not restated. Per **kind**:

| State | Visual (delta) | Interaction | Keyboard / focus | Aria / SR announce |
|---|---|---|---|---|
| **None selected** | no overlay; right panel = **Media Library**; Inspector tab disabled ("Select an element") | click an element to select; click empty canvas = no-op | canvas focusable; `Tab` (with elements) selects the topmost; `Esc` no-op | canvas name "Slide preview — editable canvas"; hint line lists the keys |
| **Text selected** | selection box + 8 handles + z-badge; right = **Inspector · Text** (§2a) | drag = move; handles = resize; double-click = inline text edit (caret) | `Tab`/`Shift+Tab` cycle; arrows nudge (Shift ×5); `[`/`]` z; `H` hide; `Del` remove; `Cmd+arrow` resize | "Text element, {behind/in front of} slide, n of m selected"; edits announce ("width 42%") |
| **Shape selected** | as above; right = **Inspector · Shape** (fill/border/corner/kind) | same grammar | same | "Shape element, …selected" |
| **Image selected** | as above; right = **Inspector · Image** (thumb + name + **Replace** + **Fit**) | same grammar; **Replace…** swaps the source; **Fit** changes fill/fit | same; **`R`** = Replace (opens media→images); Fit reachable in the inspector | "Image element '{file}', …selected"; Replace/Fit commits announce |
| **Image selected — source missing** | the element renders the **missing-media placeholder** on canvas (FR-070) + a red **⚠** corner tag; Inspector Image body shows **"⚠ Missing — {file}"** + **Relink…** | **Relink…** re-picks a file / re-points to a library asset; the element stays in place | Relink reachable from the inspector; `Del` still removes | "Image element, media missing, selected — relink available"; not colour-only (⚠ + text) |
| **Multi-element z-stack** | overlapping elements paint by z; the selected one's z-badge shows "2 of 5"; a compact stack hint | `Tab` cycles in z-order; Arrange re-stacks | `Tab`/`Shift+Tab`; `[`/`]` | z-order change announces ("moved behind the text") |
| **At element cap (64)** | Add-content tools disabled + tooltip "Maximum 64 elements" | add blocked | disabled tools leave the tab order | "Maximum elements reached" |
| **View only (permission-denied)** | Add bar + inspector edit controls **hidden**; handles disabled; elements selectable to **inspect** only; "View only" text chip | inspect, not mutate | edit tools removed from tab order | "View only" in text (not colour) |

---

## 4. State matrix — SLIDES rail, playback

| State | Visual | Interaction | Keyboard / focus | Aria / SR |
|---|---|---|---|---|
| **Slide — default** | numbered card + content thumbnail lines | click = select (stages to canvas, **Preview only** — never Live) | roving list; `↑/↓` move; `Enter` select | `role="list"`; card name "Slide n" |
| **Slide — selected** | `--sc-primary` border + `aria-current` | — | focus retained across re-render (shipped fix) | "Slide n (selected)" |
| **Slide — live** | left `--sc-live` rule + a **"LIVE" text badge** (not colour-only) | — | — | name appends "(live on the audience output)" |
| **Slide — reorder** | drag handle / `Alt+↑/↓`; drop indicator | drag or `Alt+↑/↓` | `Alt+↑/↓` (NFR-019 keyboard parity) | announces "moved to position k" |
| **Empty deck** | rail shows a single **"No slides yet — + Add slide"** CTA; canvas shows an empty-slide placeholder; right = Media Library | Add slide | CTA is a button, focused | canvas name "Empty deck — add a slide" |
| **Present / live** | topbar **▶ Present** → the selected slide is marked live (LIVE badge in the rail); **Present** button reflects the live slide; *(routing the composite to the physical audience output is the deferred seam — the button is honest about that until wired)* | Present takes the slide live (Preview→Live) | Present is a button; `Enter` on it | "Slide n presented (live)"; the deferred-routing note is surfaced in the button's title, not hidden |

---

## 5. State matrix — canvas content, media library, editing controls

### 5.1 Slide canvas content states
| State | Visual | Notes |
|---|---|---|
| **Empty slide** | background only + a faint centered **"Empty slide — add content with the toolbar"**; toolbar Text/Shape/Image/Bg are the CTAs | never blank/broken (NFR-024 — the background always fills) |
| **Loading / rendering** | a subtle **"Rendering…"** overlay + `aria-busy="true"` on the canvas while the native preview composites | live output unaffected; focus retained (UX-STATE-MATRIX §5 Loading) |
| **Error / decode-fail** | the failing **image** shows the safe placeholder inline + a scoped **"This image couldn't be loaded"** (FR-173); the rest of the slide renders | inline `role="alert"` scoped to the element, not the whole canvas |

### 5.2 Media library — asset cell states
| State | Visual | Interaction | Aria / SR |
|---|---|---|---|
| **Default (image)** | thumbnail + name + `KIND · size` | click = **add to the current slide** (deck_add_image_element) | "Add {file} to the slide" |
| **Default (video)** | thumbnail + **▶** + duration badge; kind chip | listed; **on-slide video is a later affordance** — the cell is inert with a "Video · later" note (honest) | "{file}, video, not yet placeable" |
| **Hover / focus** | `--sc-primary` outline + a subtle lift; the "+ add" affordance surfaces | pointer + keyboard focus share the same visual | focus-visible ring (WCAG 2.4.7) |
| **Selected** (the asset bound to the current image element) | `--sc-primary` filled corner check + name in accent | reflects which library asset the selected image element uses | "{file}, in use on this slide" |
| **Missing** | red `--sc-live` tinted tile + **⚠ Missing** + "File moved"; name in `--sc-live` | **Relink…** (re-point to a file); cannot be placed until relinked | "{file}, media missing — relink" (⚠ + text, not colour-only) |
| **Unused** | a small **"unused"** tag on the cell; counts into the footer "· M unused" | informational; a bulk "remove unused" is a later affordance | "{file}, unused" |
| **Importing / loading** | a skeleton cell + spinner while the host reads/derives metadata | Import (image picker today; video/audio disk import is later) | `role="status"` "Importing {file}" |

### 5.3 Media library — collection states
| State | Visual |
|---|---|
| **Empty library** | "No media yet — **+ Import**" empty state; footer "0 of media" |
| **Empty filter/search** | "No {filter} media" / "No results for '{q}'" with a clear-search affordance |
| **Footer accounting** | "{total} of media" + "· N missing · M unused" (missing count in `--sc-live` when > 0) |

### 5.4 Bottom-bar editing controls
| State | Visual / interaction | Aria |
|---|---|---|
| **Speaker notes — editing** | focused input shows the wrapper focus ring; edits autosave on change; a re-render never clobbers a mid-type value | labelled "Speaker notes"; not shown on the audience output |
| **Transition — open** | the `Transition [Fade ▾]` select open (Cut / Fade); the choice is the *selected slide's* transition | native `<select>` semantics; change announces |
| **Auto-advance — open** | `Auto-advance [Off ▾]` open (Off / 3s / 5s / 8s / 15s / 30s) | "Auto-advance {value}" |

---

## 6. State matrix — destructive & system

| State | Visual | Interaction | Copy | Aria |
|---|---|---|---|---|
| **Delete slide (confirm)** | a small confirm popover on the slide's ⋯/Delete: **"Delete slide n?"** + Cancel / **Delete** | two-step (never a single-click destroy); undo also available | "Delete slide n? This can't be undone from the rail, but ⌘Z restores it." | `role="alertdialog"`; focus on Cancel; `Esc` cancels |
| **Delete element** | select → `Del`/inspector 🗑 → removed; a brief **"Element deleted — Undo"** toast | reversible via ⌘Z (≥20 steps) | "Shape deleted — Undo" | toast `role="status"`; announced |
| **Remove media (confirm)** | confirm on a media cell's remove: **"Remove {file} from the library?"** (+ a warning if it is **in use**: "Used on k slide(s)") | two-step; blocked-with-warning when in use | "Remove {file}? It's used on 2 slides." | `role="alertdialog"` |
| **Loading (surface)** | deck view loads → skeleton rail + "Loading…" ; canvas `aria-busy` | wait; Live untouched | — | `role="status"` |
| **Error (host command failed)** | a non-blocking banner "Couldn't {action} — retry"; the surface stays on its last good state | retry | action-specific | `role="alert"` |
| **Permission-denied (View only)** | edit tools hidden; "View only" chip; elements inspect-only | inspect / stage if role allows | "View only — you don't have edit rights" | text, not colour; tools out of tab order |

---

## 7. Traceability — state → Figma frame → implementation → requirement

`impl` = **shipped** (in 86ajvccqr) · **rework** (the inspector model — build follow-up) · **new** (design only).

| State | Figma frame (§9) | impl | Requirement |
|---|---|---|---|
| None selected / Media default | `PM-States/01 Default` | shipped | FR-009 |
| Text selected + Inspector·Text | `02 Text selected` | **rework** (inspector) / selection shipped | FR-009, FR-016 |
| Shape selected + Inspector·Shape | `03 Shape selected` | **rework** / selection shipped | FR-009 |
| **Image selected + Inspector·Image (replace/fit)** | `04 Image selected` | **rework** (inspector) / place shipped | FR-009, FR-070 |
| Image missing (canvas + relink) | `05 Image missing` | **new** (relink) / missing-render shipped | FR-070, FR-173 |
| Right-panel context switch (tabs) | `06 Right panel — Media⟷Inspector` | **rework** | FR-009 |
| Empty deck / empty slide | `07 Empty states` | shipped (empty) | FR-009, NFR-024 |
| Media cell states (hover/selected/missing/unused/importing) | `08 Media library states` | shipped (missing/unused) / **new** (hover/selected/importing) | FR-003, FR-070 |
| Empty / filtered media | `08 Media library states` | shipped | FR-003 |
| Present / Live (rail badge) | `09 Present & Live` | shipped (LIVE badge) / **rework** (routing later) | FR-012, FR-013 |
| Transition / Auto-advance editing | `10 Bottom-bar editing` | shipped | FR-009 |
| Delete slide / element / remove media | `11 Destructive confirms` | **new** (confirms) / element-undo shipped | FR-016 |
| Loading / Error / View-only | `12 System states` | **new** | UX-STATE-MATRIX §5 |

---

## 8. Implementation delta + the follow-up

The one substantive divergence from the shipped surface is the **right-side per-element inspector** + the
**Media⟷Inspector context switch** (owner decision). The shipped UI edits via the on-canvas selection box +
keyboard only. This requires a build follow-up:

- Add the contextual right panel (tabs `Media` / `Inspector`; the Inspector binds to the selected element;
  auto-switch on select, back on deselect) to `#surface-presentation`.
- Add the per-element inspector bodies (Text/Shape/Image) driving new `deck_*` commands (set font/size/
  align/colour/fit/fill/border/corner; **Replace image**; the Arrange buttons already map to `deck_set_element_z`).
- Add the **relink** flow for a missing image; the media-cell **hover/selected/importing** visuals; the
  **delete/remove confirm** popovers.
- Keep the shipped on-canvas + keyboard grammar (it becomes the inspector's on-canvas counterpart).

Tracked as **follow-up story 86ajvjtax** ("implement the per-element Inspector + right-panel context
switch"). The shipped surface stays valid until it lands (already accessible + FR-012-safe).

## 9. Figma frame index (authored under the 329:124 page — "Presentation & Media — States" section)

**Authored** as the **"Presentation & Media — States"** board (Figma node **509:124**, on Page 1, directly
below node 329:124), using the file's `SelahCue Color` variables. Three sections:
- **① Contextual right panel — Media ⟷ Inspector** (row **510:125**): `Inspector · Text` (**510:126**),
  `Inspector · Shape` (**511:124**), `Inspector · Image` (**511:158** — thumbnail + **Replace…** + **Fit**),
  `Right panel · Media (default)` (**512:124**, Inspector tab disabled).
- **② Canvas — element selection** (**512:137**): selection box + 8 handles + z-badge + the keyboard model.
- **③ State gallery** (grid **514:125**, 12 tiles): Empty deck · Empty slide · Empty/filtered media ·
  Media cell Missing/Unused/Importing/Hover-Selected · Present/Live · Delete slide (confirm) · Delete
  element/Undo · Remove media (in use) · System (Loading/Error/View-only) — each annotated with a11y + copy.

Each frame uses the `--sc-*` palette (the file's `SelahCue Color` variables). Deep per-kind detail for the
inspector + the shared 8-handle/keyboard grammar lives in §2a/§3 above and CANVAS-EDITING-spec §1/§2/§8.

## 10. Accessibility summary (per role checklist)

- **Focus order:** SLIDES rail → Toolbar → Canvas objects (regions + elements, composite paint order,
  CANVAS-EDITING-spec §8) → Bottom bar → Right panel (Media/Inspector tabs → body). Emergency chrome always
  reachable.
- **Never colour-only:** selection (box + handles), LIVE (badge text), missing (⚠ + "File moved"), unused
  (tag), selected media (check + accent), View-only (text) all carry a non-colour cue.
- **Announcements (polite live region):** selection ("{kind} selected, n of m"), z-order, transform commit,
  add/delete, missing-media/relink, at-cap, panel auto-switch, import status, permission ("View only").
- **Contrast:** all text/controls on `--sc-*` meet WCAG-AA (pinned by `test_tokens.rs`); the selection
  accent `--sc-primary` is chrome, not information carried by colour alone.
- **Keyboard parity:** every pointer action has a key path (Tab-cycle select, arrow move/resize, `[`/`]` z,
  `H` hide, `Del`, `Alt+↑/↓` reorder, tab-switch the right panel) — no mouse-only control.
