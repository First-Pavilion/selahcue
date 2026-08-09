# Live Console — Presentation Playback & Slide Picker (Design Spec)

> **Surface:** Operator Console (`crates/selahcue-operator/dist/`, console page `#surface-console`).
> **Epic (home):** Presentation & Slides — ClickUp `86ajp07ce` *(Inferred from `PRESENTATION-MEDIA-STATES-spec.md`; the specific story is **to be created/linked**, not yet known).*
> **Extends, does not restate:** `PRESENTATION-MEDIA-STATES-spec.md` (inspector + auto-switch tab model),
> `RIGHT-PANEL-TABS-handoff.md` (the 2-tab pattern + tokens), `CANVAS-EDITING-spec.md` (element grammar),
> `UX-STATE-MATRIX.md`, `DESIGN-TOKENS.md`. · **ADRs:** ADR-0020 (service-plan content linking),
> ADR-0008 (control plane); a **new ADR (~0022)** is required for Dep 2 (audience routing) — see §5.

## What this is

On the Live Console, clicking a **presentation** item in the Service Plan today stages only its **title** to
the Preview panel (`setPanel()` writes title text; the deck's actual pixels never reach the output path).
There is also **no way to see or pick the other slides** in that presentation. This spec designs a
**tabbed Content panel** in the center zone — `Scriptures | Slides` — whose **Slides** tab is a live
**slide picker** (real rendered thumbnails) that stages any slide to Preview and (via GO LIVE) to Live, plus
a **light inline-edit** affordance for last-second corrections. It designs every state, the keyboard/a11y
model, and the **FE↔BE interface contract** so backend and frontend can build in parallel.

### Why (root cause)
A presentation plan item is a `slide_group` **linked to a deck by id** (ADR-0020). Per the ownership model
(decks live **only** in the operator; the host/Presenter has no deck store), the host stages the item but has
no deck pixels — so Preview shows the title only. The console *can* render deck pixels locally
(`render_deck_slide`), but only for the **editor's** loaded workspace, and it only knows a plan-linked deck's
slide **count** — not its per-slide ids/pixels. Closing the gap needs a small read-only bridge (Dep 1) and,
for the physical audience output, a routing seam (Dep 2). Both are pinned in §5–§6.

### Design decision (owner-approved): **Approach A — tabbed "content source" panel, auto-switching**
The center bottom panel (today `#scriptures`) becomes a 2-tab panel: **`Scriptures`** (unchanged browser) ·
**`Slides`** (the picker). It **auto-switches** on plan selection but keeps manual tabs, reusing the pattern
already shipped in `PRESENTATION-MEDIA-STATES-spec.md` §2 and `RIGHT-PANEL-TABS-handoff.md`. Rejected: a pure
contextual swap (undiscoverable second mode; can't improvise ad-hoc scripture mid-deck) and an
expand-in-plan filmstrip (left column too narrow; no room for the edit surface).

### Tokens (from `DESIGN-TOKENS.md` / `app.css`)
`--sc-surface #14161d` · `--sc-elevated #1c1f28` · `--sc-border #262a34` · `--sc-text #f4f6fb` ·
`--sc-text-secondary #a7aebe` · `--sc-primary #6e5cf0` (active tab + selection chrome) ·
`--sc-preview #35c08a` (staged) · `--sc-live #ff4d4d` (LIVE only) · `--sc-warn #f5a524`. Inter.
**No state is signalled by colour alone.**

---

## 1. Layout & anatomy

```
┌ Preview · STAGED ─────────────┬─ Live · ON AIR ───────────────┐
│  [native composited canvas]    │  [native composited canvas]   │
├────────────────────────────────┴───────────────────────────────┤
│        ◀ Previous          GO LIVE  ⏎           Next ▶           │
├─────────────────────────────────────────────────────────────────┤
│ [ Scriptures ]  [ Slides · 6 ]        ← 2-tab header (tablist)   │
│ ┌ deck name · 6 slides ──────────────────────── PREVIEW: 2 ─────┐│
│ │ ┌1 ▊┐ ┌2 ▊◀┐ ┌3 ▊┐ ┌4 ▊┐ ┌5 ▊┐ ┌6 ▊┐   ← horizontal filmstrip││
│ │ └───┘ └prev.└───┘ └───┘ └───┘ └───┘        real render pixels  ││
│ └───────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
```

- **`Scriptures` tab** — today's browser, unchanged (search, translation, hits, chapter nav, verse list).
- **`Slides` tab** — the picker; **disabled** ("Select a presentation") when no presentation is in play. The
  header shows `deck name · N slides` and the current PREVIEW/LIVE slide numbers.
- **Filmstrip, not grid** — this panel is *wide but short* (under the Preview|Live row). A single horizontal
  scrolling row reads as a playback timeline, keeps height bounded, and avoids the WKWebView grid
  auto-row overflow trap (`operator-webview-wkwebview-layout-traps`). Height must not push the panel past the
  console footer.
- **Auto-switch** (mirrors PM-states §2): selecting a presentation in the Service Plan selects the `Slides`
  tab **and** stages its first/last-staged slide to Preview; selecting a scripture item, or focusing the
  scripture search, returns to `Scriptures`. Manual tabs always override. The auto-switch **never** moves
  focus off the plan/canvas (announce only).
- **The filmstrip drives Preview only.** Clicking slide K stages K to Preview. GO LIVE promotes it. The
  `Next`/`Space`/`◀` console controls stay wired to the existing in-deck advance
  (`controller.rs` in-deck slide sequence); the filmstrip markers visualize that same cursor.

---

## 2. Slide-picker state matrix

Every state carries a **non-colour** cue (text tag / rule + label), never colour alone.

| State | Visual | Interaction | Aria / SR |
|---|---|---|---|
| **Slide — default** | numbered card + real thumbnail | click = stage to Preview | `role="option"`, "Slide n of m — {label}" |
| **Slide — staged (Preview)** | `--sc-preview` ring + **"PREVIEW"** tag | it is the Preview panel's slide | `aria-current="true"`, appends "(preview)" |
| **Slide — live** | `--sc-live` left rule + **"LIVE"** badge | reflects the Live-output slide | appends "(live on the audience output)" |
| **Loading / rendering** | skeleton cell + spinner; thumbs render **on-demand as they scroll in** (windowed), concurrent renders capped | wait; Preview/Live untouched | `aria-busy="true"`; `role="status"` "Rendering slide n" |
| **Empty deck (0 slides)** | "No slides yet — open in Presentations" + link to the editor surface | open editor | defensive (a saved deck normally has ≥1) |
| **Missing deck** (link → deleted deck) | "⚠ Presentation missing — the linked deck was removed" + **Relink** (reuses the plan link modal, FR-007) | re-point the item's content | "Presentation missing — relink" (⚠ + text) |
| **Large deck** | windowed render; off-screen cells drop pixels to placeholders; **bounded LRU** of decoded thumbs | scroll/keyboard re-renders on demand | count in header; no announcement spam |
| **View-only / no present rights** | browse + inspect only; stage/GO LIVE disabled; **"View only"** text chip; edit affordances hidden | host-authoritative — UI reflects the `authorize()` denial | "View only" in text (not colour) |
| **No audience output** | Live panel / GO LIVE show **"Preview only — no audience output"** (`output_connected=false`) | — | honest until Dep 2 lands |

**Bounded memory (NFR):** the filmstrip must not hold unbounded decoded pixels. Only visible (± a small
window) thumbnails retain RGBA; the rest hold lightweight placeholders. A bounded LRU caps decoded thumbs.
This gets a **bounded-memory test** (`no-memory-leaks`).

---

## 3. Light inline editing + the FR-012 guardrail

Playback **+ light edits** (owner choice). This is *last-second correction*, not authoring.

- **In scope (light):** edit a **text element's content** (typo/wrong lyric) and **toggle an element's
  visibility**. Explicit-entry only (a **✏ Edit** affordance) — never editable-by-default on a live surface.
- **Out of scope (stays in the Presentation editor):** add/delete/move/resize elements, image replace,
  backgrounds, transitions. A persistent **"Open in Presentations to edit fully →"** link is the escape hatch.
- **Where:** clicking a slide's **✏ Edit** reveals a *compact inspector* under the filmstrip — the slide's
  text elements (editable field each) + visibility toggles + the full-editor link. Reuses the PM-states
  inspector pattern (§2a), trimmed.

**Safety model (FR-012 is absolute):**
```
edit text ──▶ deck copy + PREVIEW re-render        Live output = UNCHANGED
                                                   (still the last-presented frame)
When the edited slide IS live →  Live panel chip:  ⟳ "Edited — not yet live · Go Live to apply"
```
- An edit **never** reaches Live on its own; it commits to the deck's authored copy and re-renders **Preview**.
  Only an explicit **GO LIVE** pushes it. Re-GO-LIVE clears the "Edited — not yet live" chip.
- Edits are **undoable** (the deck workspace's bounded undo/redo) with a "Slide edited — Undo" toast.
- **Persistence/concurrency** with the Presentation editor's working copy of the same deck is an
  **architecture decision (Dep 3, §5)** — not decided here. Phase 3.

---

## 4. Flow, keyboard, accessibility

**Happy path**
1. Click a presentation row → host stages it; Content panel auto-switches to `Slides`; filmstrip renders;
   slide 1 = **PREVIEW**.
2. Click slide 3 → stage 3 to Preview; Preview panel shows slide 3.
3. **GO LIVE (⏎)** → slide 3 → Live; filmstrip marks 3 **LIVE**.
4. **Next (Space/▶)** → advance within the deck (existing controller in-deck sequence).
5. Improvise mid-deck: click `Scriptures` → stage a verse → GO LIVE → back to `Slides`; the deck cursor is
   preserved where it was left (not reset).

**Keyboard**
- **Tab order:** Service Plan → Preview/Live → GO LIVE row → Content tabs → active tab body.
- **Content tabs** = `role="tablist"`: **←/→ switch tabs** *when a tab has focus*; `aria-selected`; roving
  `tabindex`; `aria-controls` → panel.
- **Filmstrip** = `role="listbox"`, roving `tabindex`; **←/→ move + stage to Preview** *when a slide has
  focus*; **Enter = GO LIVE the focused slide**; **Home/End** jump. Different focus contexts, so tab-arrows
  and slide-arrows never collide; filmstrip keydowns `stopPropagation` so they don't double-fire the global
  ← Space ⏎ console shortcuts. Full pointer/key parity (NFR-019) — no mouse-only control.

**Accessibility**
- Slides `role="option"`, `aria-current` on the staged one, name "Slide n of m — {label}" + "(preview)" /
  "(live on the audience output)".
- Polite live-region announcements: tab auto-switch ("Slides — presentation selected, 6 slides"), stage
  ("Slide 3 staged to Preview"), go-live ("Slide 3 live"), missing/relink, and **"Edited — not yet on the
  live output; Go Live to apply."**
- **Never colour-only:** PREVIEW / LIVE / Edited-not-live all carry text.
- All text/controls **AA** on `--sc-*` (pinned by `test_tokens.rs`); `--sc-primary` is chrome, never the
  sole signal. `NFR-024` never-blank holds — Preview/Live always composite a background.

---

## 5. Architecture handoff, dependencies & phasing

Three items cross out of UI/UX. The experience is designed here; the **seams are owned by architect/backend**.

**Dep 1 — Read-only deck-slide bridge** *(small, additive; enables the picker).*
List + render a **plan-linked saved deck** by id **without disturbing the editor workspace**. New read-only
commands (§6): `plan_deck_slides`, `render_plan_deck_slide`, and `select_slide` (stage slide k of the staged
item to Preview). Operator-local, no host change. *Owner: backend-engineer (shape confirmed by architect).*

**Dep 2 — Deck → audience-output routing** *(the "route now" seam; needs a new ADR ~0022).*
Operator-owned deck pixels never reach the host Presenter today (even the editor's Present is honest routing
is unwired — PM-states §4). Recommended approach: **(a)** operator composites the slide and pushes the frame
to the host Presenter over the control plane (ADR-0008) as an external frame it blits — **preserves** the
ownership model. Rejected: **(b)** teach the host to render authored slides — **breaks** operator-owned decks.
The FE contract is **unchanged** by Dep 2 (GO LIVE stays the same command; its *effect* reaches the audience
output when `output_connected`), which is what lets FE proceed in parallel. *Owner: architect (ADR) →
backend/engine.*

**Dep 3 — Console edit persistence + concurrency** *(enables the light inspector; Phase 3).*
Console edits persist to the deck and stay consistent with the editor's working copy (shared workspace vs.
save-through-with-conflict-handling), with FR-012 holding across the bridge. *Owner: architect → backend.*

**Phasing** (honors "route now" by tracking Dep 2 as first-class parallel work, not a silent deferral):

| Phase | Delivers | Needs | Owner |
|---|---|---|---|
| **1** | Tabbed `Slides` panel, filmstrip, stage-to-Preview, GO LIVE, all §2 states, a11y. Audience output honest "Preview only" until P2. | Dep 1 | frontend + backend (Dep 1) |
| **2** | GO LIVE of a deck slide reaches the **physical audience output**. | Dep 2 (ADR + backend/engine) | architect, backend |
| **3** | Light inline edits (§3 compact inspector). | Dep 3 | architect, backend, frontend |

---

## 6. Interface contract (FE ↔ BE) — pin this for parallel work

Tauri `#[command]`s on the operator (`selahcue-operator/src/main.rs`), mirroring existing shapes
(`render_deck_slide`, `select`). **snake_case** args over IPC; return JSON. All are **read-only** except the
`plan_deck_edit_*` pair (Phase 3). Everything is undefined-safe: an older host / missing deck returns
`available:false` and the FE renders the **Missing deck** / **No output** states — never a crash.

**Dep 1 (Phase 1)**
```
plan_deck_slides(deck_id: u64)
  -> { available: bool, slides: [ { slide_id: u64, label: string|null, has_notes: bool } ] }
     // lists a SAVED plan-linked deck's slides WITHOUT loading the editor workspace.
     // available:false  => deck id not found (render the Missing-deck state).

render_plan_deck_slide(deck_id: u64, slide_id: u64, max_w: u32, max_h: u32)
  -> { available: bool, frame: { w: u32, h: u32, rgba: base64 } | null }
     // read-only render of ONE saved-deck slide; mirrors render_deck_slide's frame shape.

select_slide(item_id: u64, slide_index: u32)  -> OperatorView
     // stage slide_index of the (presentation) plan item to PREVIEW only (FR-115). Never Live.
```

**Dep 2 (Phase 2)** — no new FE command. `go_live` (existing) gains audience-output effect for deck slides
per ADR ~0022. FE keeps using `output_connected` to show honest "Preview only" until wired.

**Dep 3 (Phase 3)** — writes; persistence model per Dep 3 ADR:
```
plan_deck_edit_text(deck_id: u64, slide_id: u64, element_id: u64, text: string)  -> OperatorView
plan_deck_set_element_visible(deck_id: u64, slide_id: u64, element_id: u64, visible: bool) -> OperatorView
     // commit to the deck copy + re-render PREVIEW; Live UNCHANGED until GO LIVE (FR-012).
```

**OperatorView additions (backend `operator.rs`)** — so the FE can render markers without extra round-trips:
- staged/live presentation cursor already exposed via `slide_index` on `ItemView`; ensure the **staged**
  item's `slide_index` is populated for presentations (today it is set for staged/live items).
- add `staged_is_presentation: bool` + `staged_deck_id: u64|null` on the view (or equivalent) so the FE knows
  to auto-switch the Content panel to `Slides` and which deck to list. *(Exact field names: backend's call;
  pin them in the PR and update the Dart cross-language fixtures if the wire protocol is touched.)*

**Cross-language protocol note:** if any change touches the LAN wire protocol (`selahcue-lan`), update the
Rust fixtures **and** `protocol_test.dart` together (`wire_fixtures_are_stable_for_cross_language_clients`).
Console↔host operator commands above are Tauri IPC (not the LAN protocol) and do not touch those fixtures.

---

## 7. Traceability

| Concern | Requirement / ADR |
|---|---|
| Edit never touches Live | FR-012 |
| Operator-confirmed staging (no auto-live) | FR-115 |
| Missing linked content → relink | FR-007 |
| Never-blank output | NFR-024 |
| Full keyboard parity | NFR-019 |
| Service-plan content linking | ADR-0020 |
| Operator↔controller control plane | ADR-0008 |
| Deck → audience routing (new) | **ADR ~0022 (to author)** |
| Bounded filmstrip memory | `no-memory-leaks` + bounded-memory test |

## 8. Open decisions (owner / architect)
1. **Dep 2 routing approach** — recommend (a) push-frame-over-control-plane; architect ratifies via ADR ~0022.
2. **Dep 3 edit persistence** — shared workspace vs. save-through; architect decides before Phase 3.
3. **ClickUp story** — create/link the Phase 1 story under epic `86ajp07ce` and record goal id + engine there.
4. **Figma frames** — author the `Slides` tab + state gallery under the console page as design evidence
   (follow-up; this spec is design-authoritative in the interim).
