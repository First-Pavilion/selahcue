# On-Canvas Element Editing — Design Spec (86ajq6j29, Canvas Editing epic)

**Status:** design (gates the impl stories `86ajq6j4p` interactions · `86ajq6j49` image · `86ajq6j64` text/shape) · **Owner:** /ui-ux-designer · **Requirements:** FR-009/FR-010 (layout/theme), FR-070 (missing-media placeholder), NFR-020 (audience text floor), NFR-014 (parity) · **Extends:** [THEME-MODEL-spec.md](THEME-MODEL-spec.md) §5 (Theme Designer canvas) · **Figma shell:** node `204-124` (file `SYQn5hFY8YVQKm3c6rw0eJ`) · **Deliverable phase:** spec-first (this doc); the Figma frame set is the next phase after owner approval (§11).

> **What this is.** The Theme Designer already lets an author drag/resize the **regions** (Title/Body) of a template on a live-preview canvas (S8-3c). This spec extends that to full **layered elements** — the `Shape` and `Image` element kinds are **already implemented in the engine** (`theme::Element`, composited by z-order + opacity); what's missing is the **authoring experience**: how an author adds, selects, moves, resizes, arranges (sends-to-back), and adjusts an element on the canvas, and every state that entails. The **Text** element is a noted seam.

---

## 0. Grounding — the model is already built

This design proposes **no new engine capability**. Every interaction maps onto a shipped field (§9). The engine today (Canvas Editing epic):

- `Element::Shape { x/y/w/h_permille: u16, fill, border, border_permille: u16, opacity: u8, z: i16 }` (86ajq6j2q).
- `Element::Image { x/y/w/h_permille: u16, source: MediaRef, opacity: u8, z: i16 }` (86ajq6j49) — decoded (PNG) through a bounded cache; a missing/corrupt/unsupported source draws the **non-black missing-media placeholder** (FR-070); the image **stretches to its rect** (aspect-preserving Fit = seam).
- `Theme.elements: Vec<Element>`, bounded by **`MAX_ELEMENTS = 64`**; `compose_slide` renders elements with **`z < 0` behind the text, `z >= 0` in front**, each alpha-blended at its `opacity`. Positions/sizes are **per-mille of the output frame** (resolution-independent → identical at 1080p/4K, NFR-014).

**Consequences for the design (must hold):**
- **Opacity is 0–255 (`u8`)** → the UI slider is **0–100%**, mapped `round(pct * 255 / 100)`; display the % .
- **z is a signed `i16` relative to the text** → "arrange" reorders elements *and* can cross the text plane (an element can sit behind or in front of the verse). The UI never exposes raw z; it exposes **Send to back / Bring to front / Forward / Backward** + a visible **behind-text / in-front-of-text** indicator.
- **≤ 64 elements** → Add-content is disabled at the cap with an inline reason.
- **Preview only** — the four invariants (§ UX-STATE-MATRIX) hold: **editing never touches Live** (FR-012); emergency Clear/Blackout chrome stays reachable; desktop authoritative; no AI auto-action.

---

## 1. Canvas & coordinate model

- The center canvas is the **16:9 output preview**, rendered by the **live engine** (`render_sample` / `compose`), so *preview == audience output* (same compositor + rasterizer). Elements draw exactly as they will on the audience screen, including the missing-media placeholder.
- **Coordinates are per-mille** (0–1000) of the frame. The inspector shows **percent** (0–100.0%, one decimal) for familiarity; the store is per-mille. Drag/resize math works in canvas pixels then converts to per-mille on commit (so the value is resolution-independent).
- **Safe area:** a **5%** inset guide (dashed, `border` token) on all four edges — the audience-legibility margin. Snapping (§4) prefers the safe-area edges + frame centre. Elements *may* extend outside the safe area (a full-bleed background image is valid) but text regions warn if they cross it (reuses the NFR-020 legibility guard).
- **Selection overlay** (`td-sel`): a 1px **selection-accent** outline (a neutral chrome accent — **not** the reserved `PREVIEW`/`LIVE` semantic tokens, which denote preview/live *output status*; reuse the existing `td-sel` selection colour) + **8 resize handles** (4 corner, 4 edge) + a small **z-badge** ("behind text" / "in front") near the top-left of the selection.

---

## 2. Element interactions

| Interaction | Pointer | Keyboard | Result |
|---|---|---|---|
| **Select** | click an element (topmost at the point wins) | `Tab` / `Shift+Tab` cycle elements in z-order; `Esc` deselect | selection overlay + handles appear; inspector binds to the element; SR announces "{kind} selected, {behind/in front of} text, {n} of {m}". |
| **Move** | drag the element body | arrow keys nudge 1‰; **`Shift`+arrow** ×10 (10‰) | updates `x/y_permille`; snapping (§4) engages; live preview follows. Clamp: the per-mille origin is **unsigned** (`u16` ≥ 0), so an element can bleed off the **right/bottom** (`x+w > 1000`) but its origin can't go negative — top/left overhang isn't representable; the clamp keeps `x`,`y` in `[0,1000]` and keeps ≥5% of the element on-frame. |
| **Resize** | drag one of **8 handles** — corners scale both axes, edges scale one | `Cmd/Ctrl`+arrow resizes by 1‰ from the active edge | updates `w/h_permille`; **`Lock aspect`** (inspector toggle + hold `Shift` while dragging a corner) constrains the ratio; min size floor (e.g. 20‰) so an element can't collapse to 0; anchored edge/corner never jumps. |
| **Delete** | select → `Del`/`Backspace`, or the inspector `🗑` | — | removes the element (with a brief undo affordance — undo is a general seam, at minimum a toast); selection moves to the next element in z-order. |
| **Arrange** | inspector buttons | `Cmd/Ctrl+]` bring forward · `Cmd/Ctrl+[` send backward · add `Shift` for front/back | rewrites the element's **`z`** value per §2a (NOT a `Vec` splice — see below); the z-badge + paint order update live; SR announces the new stacking ("moved in front of the text", "2 of 5"). |

**Notes / seams:** **multi-select** (marquee + shift-click, group move/arrange) is a **seam** — single-selection this batch. Double-click a **Text** element enters inline text edit (Text element = seam `86ajq6j64`; the interaction is specified here so it lands consistently).

### 2a. Z-order / arrange — exact algorithm (normative)

**Why this must be pinned:** `compose_slide` paints elements by a **stable sort on `z`** (`ordered.sort_by_key(|e| e.z())`), so **`z` is the sole determinant of paint order**; `Vec`/list order only breaks ties *among elements with equal `z`*. Therefore arrange MUST manipulate the **`z` value**, not the `Vec` position — a list splice/swap that leaves `z` unchanged is a **no-op** whenever the two elements differ in `z` (and only "works" by accident when they tie, e.g. two freshly-added elements both at `z=0`).

To keep paint order unambiguous, the authoring UI **maintains distinct `z` values** across a template's elements:

- **On Add** (§4): assign `z := (max z among existing elements, or −1) + 1` — a new element lands in front of all others (and in front of the text, since that yields `z ≥ 0`), with a distinct value.
- **Bring to front** (`Shift+Cmd/Ctrl+]`): `z := max(z over all elements) + 1`.
- **Send to back** (`Shift+Cmd/Ctrl+[`): `z := min(z over all elements) − 1`.
- **Forward** (`Cmd/Ctrl+]`): let `n` = the element with the **smallest `z` strictly greater** than this element's `z`; **swap** the two `z` values. If none (already frontmost), no-op.
- **Backward** (`Cmd/Ctrl+[`): symmetric with the **largest `z` strictly less**; swap. If none (backmost), no-op.
- **Text plane:** the text renders at the `z = 0` boundary (`z < 0` behind, `z ≥ 0` in front — matching `compose_slide`). The **behind-text / in-front-of-text chip** reflects `sign(z)`; a Forward/Backward step that swaps across the boundary flips the side (and announces it). Explicit **"Send behind text"** / **"Bring in front of text"** affordances set `z := −1` / `z := 0`-or-`max+1` respectively when a one-shot cross is wanted.
- **`i16` range guard:** `z` is `i16` (±32767). The UI **renormalizes** to a compact contiguous range (…, −2, −1, 0, 1, …) whenever a bring-to-front/back would approach the bound, preserving relative order — so repeated arranging can never overflow.
- **"n of m" indicator + `Tab` order + post-delete selection:** all use the **composite paint order** = sort by `z`, then (for any residual ties) `Vec` index; `1` = backmost. Because the UI keeps `z` distinct, ties are the degenerate case only.

**Persisted model:** the `z: i16` values (kept distinct by the above). This is a pure design/UI convention over the *unchanged* engine field — no engine change.

---

## 3. Snapping, safe area, alignment hints

- **Snap targets:** frame edges, frame centre (H+V), the 5% safe-area edges, and the centre-lines of other elements. Snap threshold ≈ 1% of frame; a thin accent guide flashes on snap. Hold **`Alt`/`Option`** to temporarily disable snapping.
- **Alignment hints:** while dragging, show live guides when the moving element's edge/centre aligns to a target; on release the value commits snapped.
- **Safe-area warning:** if a **text** element's rect crosses the 5% inset, show a non-blocking WARN badge on the selection ("outside the safe area"). Image/shape may bleed intentionally (no warning).

---

## 4. Add-content flow

The **Add-content bar** (extends THEME-MODEL-spec §5) offers **Text · Scripture · Image · Shape**. **R1 scope (this epic): only `Shape` and `Image` create elements** — they are the element kinds shipped in the engine (`Element::Shape`/`Element::Image`). `Text` depends on the not-yet-built `Element::Text` (`86ajq6j64`), and `Scripture` is intrinsic content, not an element. So:

1. **Add Shape / Add Image** create an element placed at a **default centred rect** (e.g. 300‰×200‰ centred), `z := max(z among existing)+1` (in front of everything, distinct — §2a), `opacity = 100%`, **auto-selected** (handles + inspector bound) so the author can immediately move/resize/style it.
2. **Add Image** opens a **host file picker** (host-local file). The picked path is **canonicalized + confined to the app's media root before a `MediaRef` is created** (FR-138 import-path hardening) — this authoring path is where that confinement lives; the `MediaRef` type itself only bounds length/NUL/non-empty, **not** path traversal, so an out-of-root or non-canonical pick is rejected here with an inline reason. On a valid pick, the canvas shows the **image loading** state, then the decoded image or the **missing/failed** placeholder (§7). Only PNG decodes today (other formats → placeholder + an inline "format not supported yet" note — the S8-6 later-format seam).
3. **Add Text** is present but **disabled** with a "Text elements coming soon" affordance (mirroring the disabled image-Fit control) until `Element::Text` ships (`86ajq6j64`). **Add Scripture** targets the template's **intrinsic Body region** content (the existing scripture flow) — it does **not** create a new element in R1; if/when a free scripture *element* is wanted it rides the Text-element seam. (Both buttons stay visible so the bar's IA is stable when they light up.)
4. At **`MAX_ELEMENTS = 64`** the Add-content controls (Shape/Image) are **disabled** with a tooltip ("Maximum 64 elements per theme").

---

## 5. Per-element controls panel (right inspector)

Bound to the selected element; sections collapsible; all controls WCAG-AA (tokens).

- **Layout:** **X / Y / W / H** numeric fields (percent, one decimal; ↔ per-mille) · **Lock aspect** toggle · a 9-point alignment pad (align the element within the frame/safe-area).
- **Opacity:** a **0–100%** slider + numeric (↔ `u8`); live preview blends.
- **Arrange:** **Send to back · Bring to front · Forward · Backward** buttons + the **behind-text / in-front-of-text** state chip.
- **Per-kind:**
  - **Image:** current-file name + **Replace…** (re-pick → `MediaRef`); **Fit** control shown **disabled** with "Stretch (fit modes coming soon)" — the aspect-preserving seam; opacity (shared).
  - **Shape:** **Fill** colour · **Border** colour · **Border width** (‰ of height) — mapping to the shipped `fill`/`border`/`border_permille` fields. The Fill/Border pickers are **RGB (opaque)**; the element **Opacity** slider is the **single alpha control** (the engine multiplies whole-element opacity into the fill+border alpha, so the pickers must not *also* carry an alpha channel — that would double-apply). A **new** shape defaults to a **visible** fill (a neutral panel, e.g. `#3a4150`, opaque) + **no border**, so it is never added invisibly.
  - **Text:** Font · Weight(seam) · Size · Line-height · Colour (reuses the region typography controls) — Text-element content editing is seam `86ajq6j64`.
- **Delete** element (`🗑`).

**Save model:** autosaved to the theme **library** (FR-074); `Save changes` is the explicit commit. **Editing never touches Live** (FR-012) — the designer renders to the **preview** only. A theme becomes the audience output **only** via a **separate, explicit, RBAC-gated Console action** (Set/Apply theme → the normal Go-Live path), never as a side effect of editing here. So the invariant holds: authoring changes the **library + preview**; *applying* a theme to Live is a deliberate action on the operator's authoritative seat, not this surface.

---

## 6. Relationship to existing region editing

The Title/Body **regions** (THEME-MODEL-spec §5) keep their current inspector + drag/resize. **Elements are an additional, arrangeable layer** on the same canvas, drawn behind/in front of the region text per `z`. The Add-content bar adds elements; regions are intrinsic to the template. **Selection + focus traversal + click hit-testing across BOTH classes** (which of an overlapping region/element is picked, and the `Tab` order) are defined in **§8** (composite paint order; front-of-text elements beat the region, behind-text elements yield; `Alt`+click cycles the stack). A future unification (regions-as-elements) is out of scope.

---

## 7. State matrix (ten-state vocabulary — UX-STATE-MATRIX)

| State | Trigger | Canvas / inspector surface | A11y contract | Audience effect |
|---|---|---|---|---|
| **empty** | template has no elements | canvas shows only the regions + a subtle "Add content to design" hint on the Add bar | Add bar is the first focus stop; hint is SR-readable | none (preview only) |
| **default / selected** | an element clicked or `Tab`-focused | selection outline + 8 handles + z-badge; inspector bound to the element | handles are focusable with roles + labels (§8); selection announced | none |
| **multi-element z-stack** | ≥2 elements overlap | overlapping elements paint by z; the selected one's z-badge + a compact "layers" affordance shows its position ("2 of 5") | `Tab` cycles in z-order; arrange announces the new order | none |
| **image loading** | image element added / replaced; decode in flight | a shimmer/placeholder-tone fill in the element rect + a small spinner; controls remain operable | "loading image" announced; not a blocking modal | none |
| **missing-media** | source missing / corrupt / unsupported | the element renders the **engine's non-black placeholder** (FR-070) verbatim (preview == output) + an inline inspector note ("Image not found — showing placeholder" / "Format not supported yet") | placeholder announced as "media missing"; the note is SR-readable + actionable (Replace…) | the SAME placeholder shows on the audience output — never black, never a crash |
| **drag / resize in progress** | pointer or keyboard transform | live guides + snap flashes; the numeric fields update live; a size/position readout follows the cursor | keyboard transform announces the committed value; `Esc` cancels the in-flight drag | none (preview updates) |
| **out-of-bounds** | element dragged/resized past the frame | clamped so a ≥5% sliver stays on-frame; a text element crossing the safe area shows the WARN badge | clamp + warning announced | none |
| **disabled (no displays)** | no audience output configured | the canvas still previews; a banner "No audience screen — preview only" ; Add/edit stay enabled (authoring is offline-safe) | banner announced; controls remain reachable | N/A — nothing on air |
| **at-cap** | 64 elements | Add-content disabled + tooltip ("Maximum 64 elements") | disabled state announced with reason | none |
| **error (save/import)** | autosave/commit fails | inline "Couldn't save — {reason}"; the edit stays in preview, not lost; retry affordance | error announced; non-occluding | none — never leaks to Live |
| **permission-denied** | a read-only role (Observer, or an operator without theme-edit rights) | **canvas is "View only"** — the Add-content bar + the per-element inspector edit controls are **hidden**, the 8 resize handles are **disabled**, elements are still selectable to inspect but not mutate (mirrors UX-STATE-MATRIX §5 "Read-only canvas") | edit tools **removed from the tab order**; the surface states "View only" in text (not colour-only); selection-to-inspect still announced | none — read-only |
| **recovery** | app restart after a crash mid-edit | autosave (FR-074) restores the in-flight element edits (positions/opacity/z/added elements) into **preview**; a "Restored your unsaved design changes" note | restore announced; nothing auto-applied to Live | none — restored to preview only (NFR-023) |
| **degraded** | a very large image decodes slowly / the preview is under load | the preview may **downscale/throttle** the image render (the engine's decode is bounded); authoring stays responsive — drag/resize/inspector never block on decode; the element shows the loading tone until ready | "preview updating" is non-blocking; controls stay operable | none (audience unaffected; the engine bounds decode) |
| **offline** | LAN/network down | **N/A** — theme authoring is **desktop-local** (no network dependency); the designer + live engine run on the authoritative host, so offline does not change this surface | — | N/A |
| **mobile-disconnected** | the mobile controller drops | **N/A** — the Theme Designer is a **desktop-only authoring surface**, not mirrored to or driven by mobile (mobile controls Live, not design); its loss does not affect authoring | — | N/A |

**Invariant rows (always true, per UX-STATE-MATRIX §1):** emergency **Clear/Blackout** chrome stays present + operable in every state; no state leaks preview → Live; desktop stays authoritative.

---

## 8. Accessibility

- **Key map (unambiguous — reconciled with the shipped `td-sel`):**
  - **Move:** arrow (1‰); **`Shift`+arrow** = ×10. *(Move is the ONLY meaning of `Shift`+arrow.)*
  - **Resize:** **`Cmd/Ctrl`+arrow** grows/shrinks the selected element from its anchored (opposite) edge by 1‰; **`Cmd/Ctrl`+`Shift`+arrow** preserves aspect. Keyboard resize acts on the **selected element** — it does **not** require focusing an individual handle, so resize is always reachable without a handle-focus mechanism.
  - **Arrange:** `Cmd/Ctrl+]`/`[` forward/backward (`+Shift` = front/back). **Delete:** `Del`/`Backspace`. **`Esc`:** deselect / cancel in-flight drag / exit text edit.
  - Pointer `Shift` while dragging a corner = lock aspect — a distinct *pointer gesture*, not a key-map collision with `Shift`+arrow.
- **Selection & focus across regions AND elements (one canvas, §6):** `Tab`/`Shift+Tab` cycle the canvas's selectable objects — the intrinsic **regions (Title, Body)** and the **elements** together, in **composite paint order** (§2a: z, then Vec index; backmost→frontmost). The selected object's **class (region vs element)** is stated in its accessible name and determines which inspector binds. Overall focus order: **Left rail → Add bar → Canvas objects → Inspector** (matches THEME-MODEL-spec §7).
- **Pointer hit-testing (click-to-select):** the **topmost object at the point** wins by composite paint order — an element in front of the text (`z ≥ 0`) takes precedence over a region it overlaps; an element behind the text (`z < 0`) yields to the region text where they overlap. **`Alt/Option`+click** cycles downward through stacked objects at the point.
- **Resize handles (AT exposure):** the 8 pointer handles are each exposed to assistive tech as a named control (`role="button"`, `aria-label` "resize top-left"…); the **primary keyboard resize is the element-level `Cmd/Ctrl`+arrow above**, so a keyboard/SR user never depends on reaching an individual handle. The selection group carries an accessible name ("{kind} element, {behind/in front of} text, {n} of {m}").
- **Announcements (live region):** selection, z-order change ("moved behind the text"), transform commit ("width 42%"), **add** ("Shape added, selected"), **delete** ("Shape deleted"), missing-media, at-cap, permission-denied ("View only"). Colour is **never the only cue**.
- **Contrast (scope pinned — resolves the §12 open item):** designer chrome is AA (tokens). The **audience** contrast guard (`tokens::contrast_ratio`) is **in scope now for a text region/element over a SOLID backdrop** (the background, or an opaque shape beneath). Warning against a **composited image / translucent-opacity backdrop** (and text-element contrast once `Element::Text` ships) is a **noted seam** — a composited backdrop has no single colour, so it's a later enhancement, not an R1 guarantee.
- **Audience legibility:** the NFR-020 ≥48px-equivalent text floor applies to text; the size control clamps with a warning.

---

## 9. Model ↔ implementation contract

Every control maps to a **shipped** field (no engineer guessing) or a **flagged seam**:

| UI control / interaction | Engine field (shipped) | Mapping / note |
|---|---|---|
| Move (drag / nudge) | `x_permille`, `y_permille` (`u16`) | canvas px → per-mille on commit; clamp keeps ≥5% on-frame |
| Resize (8 handles / lock-aspect) | `w_permille`, `h_permille` (`u16`) | min floor ~20‰; lock-aspect constrains ratio; anchored edge fixed |
| Opacity slider (0–100%) | `opacity: u8` | `round(pct*255/100)`; show % |
| Send-to-back / front / forward / backward | `z: i16` (behind text `<0`, front `≥0`) | **rewrites `z` per §2a** (front = max+1, back = min−1, forward/backward = swap z with the nearest higher/lower neighbour); NOT a `Vec` splice (compose sorts by `z`); UI keeps `z` distinct + renormalizes near the `i16` bound; never shows raw z |
| Add Shape | `Element::Shape` | default centred rect, `z := max+1` (§2a), opacity 255, **visible default fill** (`#3a4150`, no border) |
| Add Image + Replace… | `Element::Image { source: MediaRef }` | host file-pick → **FR-138 canonicalize + confine to media root** → `MediaRef` (host-local path); PNG decodes, else placeholder |
| Shape fill / border / border width | `fill`, `border`, `border_permille` | **RGB (opaque) pickers**; the Opacity slider is the single alpha (engine multiplies opacity into fill/border alpha) |
| **FR-138 import-path confinement** | — (authoring-side) | **this story owns it** — the file-pick canonicalizes + confines before creating a `MediaRef` (the type only bounds length/NUL, not traversal) |
| Missing-media state | the engine's non-black placeholder (FR-070) | preview renders it verbatim (preview == output) |
| Add disabled at cap | `MAX_ELEMENTS = 64` | disable + reason |
| Preview canvas | `compose_slide` + `raster::render` | same compositor as the audience output |
| **Image Fit (contain/cover)** | — | **SEAM** — engine stretches to rect today; control shown disabled |
| **Text element content** | `Element::Text` (not built) | **SEAM** — `86ajq6j64`; interaction specified, kind not yet in the model |
| **Multi-select / group** | — | **SEAM** — single-selection this batch |
| **Undo/redo** | — | **SEAM** — at minimum a delete toast; full history later |
| **Remote image on a controller** | `MediaRef` is a host-local path | **SEAM** — resolves on the render host; remote→host asset transfer later |

---

## 10. Design-system + shell binding

- Extend the existing **Theme Designer shell** (Figma `204-124` / the operator `td-*` DOM): reuse its Left rail · Center canvas (`td-preview`/`td-canvas-box`/`td-sel`) · Right inspector. The Add-content bar + per-element inspector sections are additions **inside** this shell, not a new surface.
- Bind all chrome to `DESIGN-TOKENS.md` / `tokens.rs`: bg/base `#0e1116`, bg/panel `#171b22`, border `#2b323d`, text/primary `#eef1f6`; **PREVIEW** accent for the staging selection outline, **WARN** for safe-area/contrast badges. Audience-output colours (fill/border/text) are **theme data**, authored — not chrome tokens.

---

## 11. Figma frame set — the next phase (post-approval)

After the owner approves this spec, the Figma deliverable (on node `204-124`, bound to the design-system library) is this frame list:

1. **Canvas — element selected** (Shape): overlay + 8 handles + z-badge + inspector bound.
2. **Canvas — image element** + the per-kind image inspector (Replace…, disabled Fit, opacity).
3. **Add-content flow** (bar → placed + auto-selected; the image file-pick step).
4. **Arrange / z-stack**: an element behind vs in front of the verse; the arrange buttons + "n of m".
5. **States**: empty · image-loading · missing-media (placeholder) · drag/resize-in-progress (guides) · out-of-bounds (clamp + safe-area warning) · at-cap · no-displays banner · save-error.
6. **A11y annotations**: focus order, handle roles/names, the live-region announcements, contrast callouts.

Each frame carries redline annotations tracing to the §9 contract. (Requires the Figma MCP connected in-session.)

---

## 12. Handoff → build

- **Interactions (`86ajq6j4p`):** §2 select/move/resize/delete/arrange + §3 snapping + §4 add-flow + §7 states + §8 a11y, on the §10 shell — against the shipped engine model (§9). Preview-only (FR-012).
- **Image element authoring (`86ajq6j49` frontend remainder):** the image add/replace/loading/missing-media UI (§4, §5, §7) — the engine model is already done; this wires the Theme Designer control to `Element::Image`.
- **Text/shape (`86ajq6j64`):** the shape inspector (§5) lands on the shipped `Element::Shape`; the Text element kind + inline edit is the new-model part.
- **Open decisions for the gate:** (a) undo/redo depth now or seam; (b) multi-select in R1 or R2. *(The contrast-guard scope is now decided in §8 — solid backdrop in R1, composited/image backdrop a seam — no longer open.)*
