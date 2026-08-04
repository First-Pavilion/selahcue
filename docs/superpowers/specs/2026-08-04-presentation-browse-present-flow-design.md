# SelahCue — Presentation Surface: Browse → Present → Edit Flow (Design Spec)

Status: **approved by product owner (2026-08-04) — proceeding to implementation plan** · Role: `/ui-ux-designer`
Surface: operator console webview (`implementation/desktop/crates/selahcue-operator/dist/`)
Related: DESIGN-2.0-HANDOFF.md §5.4 (Presentation & Media, Figma `329:124`) · PRESENTATIONS-LIBRARY-spec.md · PRESENTATION-MEDIA-STATES-spec.md · CANVAS-EDITING-spec.md · UX-STATE-MATRIX.md · PRD FR-002 / FR-009 · ClickUp epic "Presentation & Slides" `86ajp07ce`

> **What this is.** A flow redesign of the operator's **Presentation** surface, inverting it from
> *editor-first* to *browse/present-first* (ProPresenter-style): open the surface → see a **list of
> presentations** → open one → see its **slides as a thumbnail grid** → **double-click a slide to
> present it live** → the on-screen **◀ ▶ transport** steps live forward/back → an **Edit** button
> opens the existing authoring editor. Design + spec only — no code changed by this document.

> **Verification note.** Every concrete code claim below was checked against the codebase by a 6-dimension
> adversarial verification workflow (2026-08-04, 37 agents, each material finding independently re-verified).
> Findings are folded in; §7's feasibility dependency is **resolved**, and §8's state matrix was expanded
> from the verified gaps. Where a claimed gap was **refuted** on re-verification (it was already handled),
> the spec says so rather than duplicating existing design.

---

## 1. Motivation

The Presentation surface today lands the operator **inside the slide editor** of the currently-open
deck. The Presentations *Library* is a secondary overlay reached via a deck-switcher breadcrumb, and
"presenting" means pushing the *currently-selected* editor slide to the audience output. For live
service operation this is backwards: an operator running a service wants to **browse presentations and
fire slides live**, not sit in an authoring canvas. Editing is the occasional task; presenting is the
constant one. This redesign makes **presenting the default** and **editing an explicit, deliberate detour**.

## 2. Decisions locked with the product owner (2026-08-04)

| # | Decision | Choice |
|---|---|---|
| D1 | Double-click a slide → | **Direct to the audience output** (double-click *is* the Go-Live gesture). Single-click only selects/highlights and never touches the audience. |
| D2 | Relationship to the Live Console's live output | **One authoritative live output** shared with the console — presenting a deck slide sets the app's single live channel; the console's Live monitor reflects it. |
| D3 | Where next/previous arrows live | **On the slide grid** — the live slide gets a red LIVE ring; an on-screen ◀ ▶ transport advances live in place. |
| D4 | Save model in the editor | **Autosave + a "Done" button** back to the grid (decks already persist through `deck_*` commands; no explicit Save). |

## 3. Current state (verified against `dist/` + Rust host, 2026-08-04)

Single-page app; six "surfaces" switched by a hand-rolled router.

- Router `showSurface(name)` — [app.js:1097]; `APP_SURFACES` (six) — [app.js:1069]; nav items carry `data-surface` — [index.html:29–54]; Presentation nav item `data-surface="presentation"` (⌘⇧P, handler app.js:3431) — [index.html:33]; activating the surface calls `pmActivate()` — [app.js:1127, 4295].
- Presentation surface `#surface-presentation` — [index.html:662]. Its **default body is the editor** (`.pm-body`) — [index.html:714]. The **Library** `#pm-library` is a **hidden overlay** — [index.html:684].
- Library: `pmShowLibrary`/`pmHideLibrary` — [app.js:4330/4336]; `pmLibLoad()` → `invoke("deck_list")` — [app.js:4345]; card render `pmLibCard` — [app.js:4390]; open a deck `pmLibOpen(id)` → `invoke("deck_open",{id})` — [app.js:4458]. Existing states: `#pm-lib-empty`, `#pm-lib-error` (deck_list failure only), `#pm-lib-nopersist`. The card ⋯ menu ships Rename/Duplicate/**Delete** with a Cancel-focused alertdialog + Undo toast (`pmLibDelete`/`pmConfirm`), already designed in **PRESENTATIONS-LIBRARY-spec §5/§6** — reused as-is.
- Slides render today as a **vertical list** `#pm-slide-list` (`<ol>`), not a grid — [index.html:718]; `pmRenderSlides(dv)` — [app.js:4849]; select → `invoke("deck_select_slide",{id})` — [app.js:4890]; the LIVE badge is driven by `dv.live` — [app.js:4861].
- Present: `pmPresent()` → `invoke("deck_go_live")` presents the **selected** slide — [app.js:4499]; button `#pm-present` "▶ Present" — [index.html:671, wired app.js:5155]; also a palette action "Present slide" — [app.js:3925].
- Console transport (separate today): `previous`/`next`/`go_live` — [app.js:2842–2846]; console-*gated* keydown maps ArrowLeft/Right/Space/Enter to them — [app.js:3459–3492] (early-returns on any non-console surface).
- **Thumbnail render command:** `render_deck_slide(id: Option<u64>, maxW, maxH)` — [operator/src/main.rs:1214]; JS invoke [app.js:5065]. **Renders any slide by id** (`id:null` = selected fallback), read-only, never changes what is on air [deck_workspace.rs:687]. Returns JSON `{available, frame:{w, h, rgba}}` where `rgba` is base64 **raw RGBA8** (not PNG), consumed by `blitFrame` [app.js:314]. Size **clamped server-side to ≤ 960×540** [deck_workspace.rs:690]. **No batch path** — N thumbnails = N invokes, each taking the deck lock.
- Data: no JS store; everything round-trips to the Rust host. JS holds the last `DeckView` in `pmDv` — [app.js:4089]; helper `pAct(fn, opName)` runs a command, stores, re-renders — [app.js:4112].
- **Live-output ownership (verified):** both `deck_go_live` and console `go_live` dispatch through one shared `AppState.backend` to a single host `Presenter`, and both write the identical live surface `self.live.apply(EngineCommand::SetScene{…})` — `Presenter::go_live` [present.rs:134] and `Presenter::present_authored` [present.rs:164]. **There is one authoritative live output.** Caveat: the deck editor keeps a *separate* local annotation `DeckWorkspace.live` [deck_workspace.rs:39] that is **not** cleared when plan/scripture content is driven from the console — so `DeckView.live` can go stale vs. host truth (see §7).

## 4. Structural approach — A: three modes of the one surface

Keep a single `#surface-presentation` with an explicit **mode** state and swap the default:

```
mode = "library" (NEW default) | "grid" (NEW) | "editor" (existing .pm-body)
```

- **Library** is promoted from hidden overlay to the surface's **default landing mode**: `pmActivate()` must call `pmShowLibrary()` instead of `pmHideLibrary()` [app.js:4295]. The library's "‹ Back to editor" link `#pm-lib-back` is **removed** (nothing to go back to) [index.html:686, app.js:5165]. "Open" a card transitions to **grid**, not editor: `pmLibOpen` currently does `renderPresentation(dv); pmHideLibrary()` (lands in editor) [app.js:4458–4459] — retarget to enter grid mode.
- **Grid** is a **new mode/DOM block** inside `#surface-presentation`: the open deck's slides as a thumbnail grid + a transport bar.
- **Editor** is the **existing** `.pm-body` DOM verbatim, shown only when mode = `editor`, entered via **Edit ▸** from the grid and left via **‹ Done** back to grid.

Rationale: the codebase already models Library as a mode of this surface and already has the full editor + `deck_*` command layer + a native slide renderer that takes an arbitrary slide id; this reuses all of it and confines the change to (a) default mode, (b) a new grid view, (c) two back-links and the entry-point relocations in §11. No router rewrite, no new surface, no deep-link scope. Alternatives — separate routed surfaces (B, router rewrite for no user-visible gain) and grid-as-overlay-on-editor (C, keeps the editor-first flow we are removing) — were rejected.

## 5. Information architecture & flow

```
Presentation (nav ⌘⇧P)  ──lands on──▶  LIBRARY (list)
        LIBRARY  ──click a presentation card──▶  SLIDE GRID (that deck)
        SLIDE GRID  ──‹ Presentations──▶  LIBRARY
        SLIDE GRID  ──Edit ▸──▶  EDITOR
        EDITOR  ──‹ Done──▶  SLIDE GRID
        SLIDE GRID  ──double-click / Enter a slide──▶  GO LIVE (audience)
        SLIDE GRID  ──◀ / ▶ transport──▶  advance live prev/next
```

## 6. The Slide Grid (new)

**Layout.** Top bar: `‹ Presentations` (back to Library) · deck name + "n slides" · **Edit ▸** (primary).
Body: responsive grid of 16:9 slide thumbnails on `--sc-inset` mattes, each numbered, each a natively
composited preview via `render_deck_slide({id, maxW, maxH})` — one call **per slide by its own id**.
Because there is no batch path and each call takes the deck lock, thumbnails are **lazy-rendered for
visible slides only** (IntersectionObserver-style), rendered at ≤ 960×540, and cached by slide id +
revision — a bounded cache, per the project's no-unbounded-memory rule. Bottom: a persistent **transport
bar**, shown only once this deck has a live slide.

**Interaction model (safety-critical — D1/D2/D3):**

| Gesture | Result | Touches audience? |
|---|---|---|
| Single-click a thumbnail | Selects it — **blue cursor ring** (`--sc-primary`) | No |
| Arrow keys ←→↑↓ — **nothing live yet** | Move the selection cursor (roving `tabindex`) — safe | No |
| Arrow keys ← / → (also ↑ / ↓, Space) — **while a slide is live** | **Advance LIVE** to prev/next slide directly, slideshow-style (`deck_go_live_delta ±1`); focus + cursor follow live | **Yes** |
| **Double-click** / **Enter** on a thumbnail | **GO LIVE** that slide (`deck_go_live`) — **red LIVE ring + "● LIVE"** *on success only*. This is how the show STARTS from cold. | **Yes** |
| On-screen **◀ / ▶** transport | Advance **live** to prev/next slide (identical to the live-mode arrows) | **Yes** |
| Blackout / Clear (global footer — exists) | Kills the audience output | Yes |

**Two rings, two meanings.** The **selection cursor** (blue, `--sc-primary`) answers "what will I act
on"; the **LIVE ring** (red, `--sc-live` on `--sc-live-soft`, `--sc-live-border`) answers "what the
audience sees right now." Selecting is always safe; only double-click/Enter and the ◀ ▶ transport change
the audience output. This preserves SelahCue's never-surprise-the-audience invariant while matching the
owner's "double-click presents / side arrows go next-prev" intent.

**The LIVE ring reflects HOST truth, not the editor annotation.** The red ring must be driven by the
**authoritative host live state** (the operator `view()` / OperatorView), not by the local
`DeckWorkspace.live` field, which is not cleared when the console drives plan/scripture content and can
therefore falsely mark a deck slide live (§3, §7). Implementation requirement: the grid derives its LIVE
ring from host live truth, or `DeckView.live` is made to track it.

**Keyboard model — arrows advance live directly (owner decision, 2026-08-04).** Once a slide is live,
keyboard ← / → (and ↑ / ↓, Space) advance the LIVE slide directly, slideshow-style — **every press changes
the audience output**, and focus follows live. **Before anything is live**, arrows are safe cursor
navigation; the show is *started* only by a deliberate **double-click / Enter** (the never-surprise
invariant holds until that first deliberate go-live). Consequence for accessibility: keyboard-only *safe
look-ahead while presenting* is not available on bare arrows (the owner chose direct advance); the **mouse**
retains it — single-click selects a slide without going live, then double-click jumps live to it. An
optional "hold a modifier to move focus without advancing" affordance is noted for the a11y backlog (§9).
Verified: `deck_go_live` has no keyboard binding today, so this mapping is net-new with nothing to collide
with [app.js:3459, 5313, 5370].

**Transport bar copy:** `◀ Previous · ● LIVE — slide n / total · Next ▶`. Mirrors console transport
vocabulary. ◀/▶ are `aria-disabled` at deck ends, and disabled while the host link is reconnecting (§8).

## 7. One live output — console ↔ deck unification (D2) — **RESOLVED**

**Feasibility is confirmed, not assumed.** `deck_go_live` and console `go_live` reach the same single
`Presenter.live` surface through one shared `AppState.backend` (verified: present.rs:134 vs present.rs:164).
Consequences and requirements:

1. **One live channel, last-writer-wins.** `Presenter::present_authored` writes `self.live` and clears the
   plan/scripture model (`live_slide = None`) [present.rs:169–170]; `Presenter::go_live` overwrites the
   same surface and repopulates it [present.rs:139]. Deck-present and plan-present are **mutually exclusive**
   on the one audience surface — exactly D2's "presenting supersedes plan content until Blackout/Clear or
   the operator drives the plan again." No parallel channel, no compositing conflict.
2. **Transport implementation — two viable options:**
   - **(b) Zero-backend-change today:** grid ◀/▶ call the existing `deck_select_slide(prev|next id)` then
     `deck_go_live`. Works unchanged.
   - **(a) Recommended:** add a small host command `deck_go_live_delta(±1)` (~15 lines) that advances the
     deck's live pointer using existing `SlideDeck::index_of`/`get_index` [deck.rs:226–231], clamps at deck
     ends, and reuses the existing `present_payload()` + `present_authored_slide()` route — advancing and
     presenting **atomically under one lock**, avoiding a two-command race. Preferred.
3. **LIVE-ring source (requirement, from §6):** the grid ring reads host live truth, because
   `DeckWorkspace.live` can go stale when the console takes over the live output.
4. **Secondary/NDI mirroring — IN SCOPE this pass (owner decision, 2026-08-04).** Today an authored deck
   present sets `live_slide = None` [present.rs:169] and `compose_screen_live` returns an idle black frame
   when `live_slide` is None [present.rs:283–284], so secondary audience screens / NDI go black while a deck
   slide is live. **This flow must fix that:** presenting an authored deck slide sets the *single live
   content for ALL configured audience outputs*, so the primary output, secondary screens, and NDI all show
   the authored slide. Engine change (`selahcue-present`): generalize the live-content model so the authored
   slide (plus its fallback theme) is **retained** as live content and rendered by `compose_screen_live`
   (with per-screen theme/layer-mask fallback and the never-blank guarantee NFR-024), and recomposed by the
   `set_theme` / `set_main_screen_theme` / `set_main_layer_mask` paths [present.rs:180–264] exactly as the
   title+body model is. This is the one part of the work that reaches **below the webview into the render
   engine**, and it requires: CPU-rasterizer + `selahcue-gpu` **SSIM ≥ 0.99 parity** tests for the
   authored-live path, and a **never-blank fault-injection** test (NFR-024). See §12/§13.

## 8. State matrix

Library states reuse the shipped `#pm-lib-*` blocks; grid/editor states below. Rows marked **NEW** are
additions from the verified state-completeness pass. Rows marked **(exists)** reuse shipped design/code.

| Surface / state | Design | Source |
|---|---|---|
| Library — empty | "No presentations yet" + **+ New Presentation** — now the *landing* empty state | `#pm-lib-empty` (exists) |
| Library — loading | `aria-busy` skeleton on the grid | `#pm-lib-grid` (exists) |
| Library — load error | Inline error + Retry (deck_list failure) | `#pm-lib-error` (exists) |
| Library — no-persist | Amber "changes aren't being saved" banner | `#pm-lib-nopersist` (exists) |
| Library — delete a presentation (confirm) | Cancel-focused alertdialog + Undo toast | PRESENTATIONS-LIBRARY-spec §5/§6 (exists) |
| **Library — open a deck FAILED** | **NEW.** `deck_open` rejected (lock error) **or** silently resolved a stale/unknown id [main.rs:937–947]. **Stay on Library**, show inline `role="alert"` "Couldn't open {name} — Retry"; **never transition to a blank grid**. Guard the silent-stale-deck path (verify the returned view's id matches the requested id). | verified gap |
| Grid — empty deck (0 slides) | "This presentation has no slides yet" + **Edit ▸ to add slides** | NEW |
| Grid — loading thumbnails | Per-thumbnail skeleton until `render_deck_slide` returns; lazy-render visible only | NEW |
| Grid — thumbnail render fail / missing media | "⚠ Can't preview" tile; slide still selectable & live-able | NEW (missing-media styling exists) |
| Grid — nothing live | Transport hidden; hint "Double-click a slide to present it live" | NEW |
| Grid — live | Red LIVE ring (host-truth driven) on the live slide + transport shown | NEW |
| Grid — first/last slide live | ◀ / ▶ `aria-disabled` at deck ends | NEW |
| **Grid — GO-LIVE FAILED** | **NEW (safety).** `deck_go_live`/transport rejected (audience output not reached) [main.rs:1164–1172]. The slide must **NOT** show the red LIVE ring (the audience did not change); keep the *prior* live slide's ring; surface scoped `role="alert"` "Couldn't present — output not reached · Retry". | verified gap |
| **Grid — NO audience output connected** | **NEW (safety).** On the stand-alone/local backend, `present_authored_slide` returns Ok silently with no physical output [main.rs:93, 1492–1512]. The go-live gesture must be **honest**: show a **"Preview only — no audience output"** badge instead of a true red LIVE ring, matching CANVAS-EDITING-spec's "No audience screen — preview only". Never tell the operator the audience sees a slide no display is showing. | verified gap |
| **Grid — Blackout/Clear active while a slide is live** | **NEW.** When blackout/clear is on, the transport/ring must show the audience is **BLACKED OUT / CLEARED** in words + a non-colour cue (per UX-STATE-MATRIX §7 "never an ambiguous blank"), even though slide n is the pending-live slide; include the restore path. | verified gap |
| Grid — host link reconnecting | The existing top-bar connection pill already shows amber **"Reconnecting…"** and re-syncs on reconnect [app.js:4053–4080, app.css:270–278] — **reused, not rebuilt**. Additional grid behaviour: **disable ◀/▶ while reconnecting**, then re-sync the LIVE ring to host truth. | (exists) + small delta |
| **Grid — permission (RBAC)** | The **desktop operator console is the authoritative, full-rights surface** — RBAC gates LAN *peers* (mobile controllers), not the desktop host — so on the desktop grid go-live is **not** gated (N/A, justified). **If this browse/present flow is ever mirrored to a mobile controller**, the go-live gestures and ◀/▶ must **degrade to browse-only** for roles without `GoLive` (Assistant/Viewer), with selection still allowed and a "View only — no live rights" chip — per the existing gate `PresentAuthoredSlide → Permission::GoLive` [rbac.rs, test_rbac.rs]. | verified (claim of a desktop gap was **refuted**; mobile caveat retained) |
| **Grid — recovery on relaunch** | **NEW (small).** Crash-resume of the live *position* is already specified for the console (UX-STATE-MATRIX §4 "Resume last live state", §16). Grid-specific: on surface-reopen the grid **mirrors current host live truth** — restore the red LIVE ring + transport if a deck slide is still live; else "nothing live". **Do not auto-re-present.** | verified (recovery exists; grid rendering is the delta) |
| Grid — offline / no network | **N/A (justified).** Presenting is local: deck composes on the host and routes over loopback/LAN to the output window; the audience output is local hardware. | verified N/A |
| Editor | Unchanged; gains **‹ Done**; the old present entry points (`#pm-present`, palette "Present slide") are relocated to the grid (§11) | `.pm-body` (exists) |

## 9. Accessibility & content

- Grid is `role="grid"` (rows/cells) or a listbox with **roving `tabindex`**. Arrow-key behaviour is
  **mode-dependent** (§6): safe cursor navigation when nothing is live; **direct live-advance** once a slide
  is live (focus follows live). Announce the mode implicitly through the live announcements below.
- **Three visually separable states — verified gap, resolved by geometry not just colour.** There is **no
  focus CSS token**; today focus is `outline: 2px solid var(--sc-primary)` — the *same* violet this spec
  uses for the selection cursor, so colour alone cannot separate focus from selection. A focused, selected,
  non-live thumbnail must show all three legibly at once. Specification:
  - **Selection cursor:** solid **inset** ring (`box-shadow: inset 0 0 0 2px var(--sc-primary)`) + faint primary tint.
  - **Keyboard focus:** **outset** `outline: 2px solid var(--sc-primary-hover)` with `outline-offset: 2px` (offset geometry distinguishes it from the inset selection ring even at the same hue family).
  - **LIVE:** solid `2px var(--sc-live-border)` border + `--sc-live` glow + the **"● LIVE"** text label.
  Distinct *geometry* (inset vs. outset vs. bordered+label) keeps them separable for low-vision users and when stacked.
- Every go-live gesture has a keyboard path (**Enter** to start; arrows to advance while live). Live changes
  announce via `aria-live="polite"` (reuse `#pm-live-region`): *"Now live: slide 4 of 12."* On go-live
  **failure**, announce the error, not a live change; in **preview-only** (no output) announce *"Preview only —
  no audience output."* **A11y backlog:** because bare arrows advance live while presenting, add an optional
  "hold ⌥/Alt to move focus without advancing" affordance so keyboard-only operators keep a safe look-ahead.
- WCAG: LIVE never colour-alone — always the "● LIVE" text label (1.4.1). "Preview only" and
  "BLACKED OUT/CLEARED" states also carry text, never colour alone. Thumbnail + transport targets ≥ 44px.
- Copy: **"‹ Presentations"**, **"Edit ▸"**, **"‹ Done"**, transport **"◀ Previous" / "Next ▶"**, live pill
  **"● LIVE"**, go-live toast *"Now presenting on the audience output"* (exists) — suppressed when
  no-output/preview-only. Empty deck: *"This presentation has no slides yet."*

## 10. Design-system usage (Design 2.0 tokens) — **use the `--sc-*` vars**

Verified against `app.css`. Write the **prefixed** Design-2.0 vars, **not** the legacy aliases:

| Role (spec) | CSS var to use | Trap to avoid |
|---|---|---|
| Selection cursor | `--sc-primary` (#6E5CF0) [app.css:38] | not `--primary`; `--accent` is a deprecated alias |
| Focus ring | `--sc-primary-hover` + `outline-offset` | no `--focus` token exists — use offset geometry (§9) |
| LIVE ring/pill | `--sc-live` (#FF4D4D) [app.css:43] | **`--live` is the WRONG legacy deep-red #a3283a**; `--live-ink` is #ef4444 |
| LIVE tint | `--sc-live-soft` (#2A1416) [app.css:44] | — |
| LIVE border | `--sc-live-border` (#5A2327) [app.css:45] | — |
| Thumbnail matte | `--sc-inset` (#0F1116) [app.css:32] | — |
| Transport surface | `--sc-surface` / `--sc-elevated` [app.css:30/31] | `--panel` is a legacy alias |
| Hairlines | `--sc-border` (#262A34) [app.css:33] | `--line` is a legacy alias |

Thumbnails 16:9, radius per cards (14–16). No new colour tokens; the only new "token" need is the
focus-vs-selection geometry convention in §9.

## 11. Implementation seams — entry points to relocate (verified, for the plan)

| Seam | Today | Change |
|---|---|---|
| `pmPresent()` / `invoke("deck_go_live")` — **sole** site [app.js:4499] | Presents editor's *selected* slide | Relocate to grid; retarget to the grid's chosen thumbnail id (double-click/Enter → `deck_go_live`; transport → `deck_go_live_delta`) |
| `#pm-present` "▶ Present" button [index.html:671, app.js:5155] | Editor top bar | Remove from editor chrome; grid owns presenting |
| Palette "Present slide" [app.js:3925] + "Add slide"/"Undo/Redo" [3924/3926/3927] | Gated on surface-active only (not mode) — fires in Library too | Re-scope to the correct mode (present→grid; add/undo/redo→editor) |
| `pmActivate()` [app.js:4295] | Calls `pmHideLibrary()` → lands **editor** | Call `pmShowLibrary()` → land **Library** (core landing change) |
| `#pm-deckswitch` breadcrumb [index.html:665, app.js:5163] | Opens Library from editor top bar | Reconcile: becomes "back to Library" from grid/editor; the `pmHideLibrary` focus-restore-to-deckswitch [app.js:4343] assumes returning to editor — fix for grid target |
| `#pm-lib-back` "‹ Back to editor" [index.html:686, app.js:5165] | Hides Library → shows editor | **Remove**; `pmLibOpen` [app.js:4458–4459] must enter **grid**, not editor |

**No keyboard collisions (verified):** console transport keydown is console-gated [app.js:3459]; the canvas
element-nudge handler is bound to the canvas node (fires only on editor-canvas focus) [app.js:5313]; the
Media/Inspector and layer-row roving handlers are element-scoped to editor DOM; the surface-wide ⌘Z/⌘N
handler binds no plain arrows/Enter [app.js:5370] (harmless in grid, though the implementer may mode-scope it).

## 12. Out of scope / follow-ups

- On-slide video (`data-later="video"`) stays deferred (ADR-0020) — unchanged.
- Deck→secondary-screen/NDI mirroring (§7.4) — **now IN SCOPE this pass** (engine change in `selahcue-present` + `selahcue-gpu` parity), not a follow-up. This makes the work a multi-crate change (webview + host command + render engine), not a webview-only change.
- No deep-linkable routes for library/grid/editor (desktop app; not required).
- Media Library remains inside the **editor** mode; the grid is presentation-only.
- `deck_go_live_delta(±1)` host command (§7.2a) — small backend task for the plan (or use option b to ship with zero backend change).
- Mobile controller mirror of this flow (RBAC-gated go-live per §8) — separate mobile task if pursued.

## 13. Traceability & completion predicate

- **Requirements:** PRD FR-002 (slide group as plan-item), FR-009 (free-form layered slides);
  DESIGN-2.0-HANDOFF §5.4; PRESENTATIONS-LIBRARY-spec; PRESENTATION-MEDIA-STATES-spec; ClickUp epic
  `86ajp07ce`. A ClickUp story for this flow change (plus the §12 follow-ups) must be created/linked before
  implementation.
- **Design VERIFIED_COMPLETE when:** every mode (Library/Grid/Editor) and every §8 state has linked design
  evidence; the §6 interaction model (selection vs. live, arrows-advance-live, host-truth LIVE ring) is
  specified with keyboard + screen-reader semantics; the §9 three-state geometry resolves the focus-token
  gap; §7 is confirmed, **including authored-slide mirroring to all audience outputs (primary + secondary/NDI)
  with SSIM ≥ 0.99 parity + never-blank fault-injection tests**; copy and the `--sc-*` tokens are pinned; the
  §11 relocation seams are enumerated; and the handoff is precise enough to implement and QA without guessing.

## 14. Open questions / dependencies (post-verification)

1. ~~§7 backend unification~~ — **RESOLVED**: one shared `Presenter.live`; option (b) needs zero backend
   change, option (a) is a ~15-line delta command (recommended).
2. ~~`render_deck_slide` arbitrary-slide capability~~ — **RESOLVED**: renders any slide by id; returns
   raw-RGBA JSON ≤ 960×540; no batch path (lazy-render).
3. ~~§7.4 secondary-screen/NDI mirroring~~ — **RESOLVED (owner, 2026-08-04): build it in this pass.** Now an
   in-scope engine change (`selahcue-present` + `selahcue-gpu` parity), see §7.4 / §12 / §13.
4. ~~keyboard ← → cursor vs. advance-live~~ — **RESOLVED (owner, 2026-08-04): arrows advance live directly**
   (§6). Nothing-live edge stays safe; mouse retains safe look-ahead.
