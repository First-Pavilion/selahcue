# Presentations Library & "New Presentation" — Design Spec (Design 2.0)

**Role:** UI/UX Designer · **Epic:** Service Planning & Library (86ajp072p) + Presentation & Slides (86ajp07ce)
**Figma file:** `SYQn5hFY8YVQKm3c6rw0eJ` · **New frames:** `547:124` (Library + New), `552:124` (Create & Manage)
**Answers:** "How do we create a new presentation? Is there provision to view my presentations?"

---

## 1. Why this spec exists (the gap)

**Verified — today you can do neither.** The Presentation surface (Figma `329:124`) is a **single-deck editor**: the operator boots one hard-coded demo deck (`DeckWorkspace::demo()`), the top-bar "plan chip" is a static "Presentation" label, and "Add to plan" is a disabled *later* stub. There is **no** create-new, open, browse, rename, duplicate, or delete for whole presentations, and the right-panel "library" is the **media-asset** library, not a presentations library.

**Verified — the intent is already in the product.** PRD **FR-003** requires a "Presentation library of reusable documents" (MVP); FR-001/005 cover creating/duplicating/versioning service plans. Architecture §8 models `service_plan → plan_item → document`, where a **"presentation" = one authored deck = one `document`**.

**Verified — the backend foundation already exists but is unwired.** `selahcue-data/src/deck_repo.rs` persists a **`deck` library table** (schema v16) with `save_all` / `load_all` (one row per deck **name**), round-trip tested. It is simply not connected to the operator — a documented "thin follow-up" (ADR-0020, decision 7: "the deck library is a standalone document set this pass").

So this design **surfaces an existing capability**, it does not invent a new subsystem.

---

## 2. Information architecture & entry points

- **App nav → "Presentations"** becomes the landing surface for the Presentation area (today the nav route "Plan / Library" is a deferred "(later surface)", NAV-IA §2). Opening the Presentation area shows the **Library** (§3), not an editor pre-loaded with a mystery deck.
- **Library → open a card → Editor** (the existing `329:124` single-deck editor, unchanged).
- **Editor → back to Library:** the editor top-bar chip changes from a static label to a **breadcrumb + deck switcher**: `‹ Presentations   ▦ <Deck name> ▾`. The `▾` opens a quick-switch popover (recent decks + "New…" + "Browse all…"); clicking the deck name inline-renames it. This replaces the disabled "Add to plan" stub as the *navigation* entry point. (For the fate of "Add to plan" itself, see §2.1.)
- **Relationship to Service Plans:** a presentation (deck) is one *document*. Once the `PlanItem → deck` reference lands (ADR-0020 follow-up), a plan item can point at a deck from this library. This spec covers the **standalone deck library**; the plan-item link is a separate story.


### 2.1 "Add to plan" — reinstated (owner decision, 2026-08-23)

**Superseding §2 above and audit question Q-14.** This spec originally dropped "Add to plan"
because the deck-switcher replaced it as the way back to the Library, *and* because the
`PlanItem → deck` reference it needed did not exist — §2 records it as a "separate story"
pending the ADR-0020 follow-up.

**That blocker has since cleared.** `set_item_content` is a live host command
(`selahcue-operator/src/main.rs:267`) and the `{ kind: "deck", id, slide_count }` link shape is
already exercised by `planDeckBody`. So the reason for dropping the control no longer holds, and
the owner has reinstated it.

Shipped behaviour (`pm-addtoplan`, `pmAddToPlan` in `dist/app.js`):
- resolves the open deck via `deck_list`, creates a `slide_group` plan item via `add_item`,
  then attaches the deck link via `set_item_content`;
- **rolls the plan item back** if the link fails, rather than leaving a row that misreports what
  it holds;
- guards double-activation, so one click can never produce two plan items;
- hidden in Library mode, shown in Editor mode.

It is a **functional control, not the disabled stub** the regression guard in
`selahcue-present/tests/test_tokens.rs` was written to keep out. That guard bans the old
`id="pm-addplan"` and still passes, because the new control uses `pm-addtoplan` — a distinction
too subtle to rely on. **The guard is to be widened** to ban the dead stub *and* positively
assert the functional control is present and wired.

---

## 3. Screen anatomy — Presentations Library (`547:124`)

```
┌ topbar ──────────────────────────────────────────────────────────────────────┐
│ ▦ Presentations  Your slide decks        [⌕ Search presentations] [Recent ▾] [＋ New Presentation] │
├───────────────────────────────────────────────────────────────────────────────┤
│ 7 presentations                                              [▦ Grid] [☰ List] │
│ ┌ ＋ New ┐ ┌ card ┐ ┌ card ┐ ┌ card ┐                                          │
│ │ dashed │ │thumb │ │thumb │ │thumb │   … responsive wrap, 4-up @1760          │
│ │  tile  │ │name  │ │name  │ │name  │                                          │
│ └────────┘ └──────┘ └──────┘ └──────┘                                          │
└───────────────────────────────────────────────────────────────────────────────┘
```

- **Top bar:** brand/title · **search** (client-filter, PRD FR-003 "<300ms for ≤5k items") · **sort** (Recent · Name · Slide count) · **`＋ New Presentation`** primary (⌘N).
- **Header row:** live count · **Grid/List** view toggle (Grid default; List = a denser table for large libraries).
- **Card (grid):** 16:9 **thumbnail** (first slide, rendered by the existing native compositor `render_deck_slide`), a **slide-count pill** overlay, **name** (Semi Bold, truncates), **meta** (`N slides · edited <relative>`), and a **⋯ menu**. Whole card = Open; ⋯ or right-click = menu. A deck referenced by a service plan shows a small **"In a plan"** chip (post plan-link follow-up).
- **New tile:** the first grid cell is a dashed **`＋ New presentation`** affordance (redundant with the top-bar button — the empty-state pattern that never leaves the user stuck).

**Responsive:** 4-up ≥1600, 3-up ≥1200, 2-up ≥820, 1-up below. List view for very large libraries or narrow widths. Cards keep a 16:9 thumb; names wrap to 2 lines then ellipsize.

---

## 4. Create flow — "New Presentation" dialog (`552:124` ①)

Triggered by the top-bar button, the New tile, or ⌘N. A `role="dialog"` modal (Cancel-focused? No — **Name field focused**, text pre-selected):

- **Name** — text input, pre-filled `"<Service> — <date>"` (e.g. "Sunday Service — Aug 11"), fully selected so typing replaces it. Empty name → falls back to "Untitled presentation" (never blocks Create).
- **Start from** — radio group:
  1. **Blank deck** (default) — one empty slide, ready to edit.
  2. **Duplicate an existing presentation** — reveals a deck picker; copies slides + theme (PRD FR-005 "duplicate produces an independent copy").
  3. **From a template · later** — disabled, honest "later" affordance (themed starters).
- **Actions:** `Cancel` (ghost) · **`Create presentation`** (primary). Create → persists a new deck row, opens it in the editor with the cursor on the first slide.

**Inline-rename** (from a card or the editor breadcrumb) reuses the same Name field pattern as a lightweight popover — no full modal.

---

## 5. Manage — card ⋯ menu + destructive confirm (`552:124` ③)

- **⋯ menu:** `Open` · `Rename` · `Duplicate` · `Present` (straight to live) · `Export deck (.json)…` · —— · **`Delete`** (danger).
- **Delete confirm** — `role="alertdialog"`, Cancel-focused, Esc cancels, focus-trapped (mirrors the existing Presentation destructive-confirm pattern, `PRESENTATION-MEDIA-STATES-spec.md` §6): "Delete "<name>"? Removes the presentation and its N slides from your library. **You can undo it.**" A **⚠ in-plan warning** appears when the deck is referenced by a service plan ("that plan item will show missing"). Delete → toast **"Presentation deleted — Undo"** (`role="status"`, undo-backed), consistent with the element-delete toast already shipped.

---

## 6. State matrix

| State | Trigger | Design | Reference |
|---|---|---|---|
| **Populated** | ≥1 deck | Grid/list of cards | `547:124` |
| **Empty (first run)** | 0 decks | Centered CTA "No presentations yet" + `＋ New Presentation` + `⌘N` hint | `552:124` ② |
| **Loading** | opening the library | Skeleton cards, `aria-busy` on the grid (mirrors the canvas busy pattern already shipped) | spec §7 |
| **Error** | `load_all` fails | `role="alert"` banner "Couldn't load your presentations — Retry" | spec §7 |
| **Search — no results** | filter matches 0 | "No presentations match "<q>" — Clear search" | spec §7 |
| **Creating / saving** | Create pressed | Button shows a spinner; disabled until the new deck opens (optimistic) | §4 |
| **Rename** | menu/breadcrumb | Inline Name popover, Enter commits / Esc cancels | §4 |
| **Delete confirm** | menu → Delete | `role="alertdialog"` + in-plan warning + Undo toast | `552:124` ③ |
| **Duplicate** | menu → Duplicate | New "… copy" card appears, selected | §5 |

*(Loading / error / no-results are documented here and belong on the states board with the built panels — a follow-up frame; the destructive + empty states are already drawn.)*

---

## 7. Accessibility (testable)

- **Grid semantics:** `role="list"` / cards `role="listitem"`; each card is a link/button with an accessible name = deck name + meta ("Sunday Service — Aug 4, 24 slides, edited 2 hours ago"). The ⋯ button is separately labelled ("More actions for <name>").
- **Keyboard:** Tab reaches every card and its ⋯; Enter/Space opens; `Menu`/⇧F10 or the ⋯ button opens the menu (arrow-navigable, Esc closes, focus returns to ⋯). ⌘N = New. Search is a labelled `type=search`.
- **Dialogs:** New Presentation = `role="dialog"` `aria-modal`, focus on the Name field, focus-trapped, Esc cancels. Delete = `role="alertdialog"`, Cancel-focused, the **warning is in `aria-describedby`** (matches the fix already applied to the Presentation confirms). Focus returns to the invoking control on close.
- **Not colour-only:** the "In a plan" chip carries text; the delete warning pairs ⚠ + text; the selected radio uses a filled dot + border, not colour alone.
- **Contrast (`--sc-*`, AA):** body text `--sc-text` / secondary `--sc-text-secondary` on `--sc-surface`/`--sc-elevated`; the danger button uses **dark text on `--sc-live`** (~5.9:1) — the same AA-correct treatment already applied to `.pm-btn-danger`. Live-red text sits on `--sc-live-soft` (5.31:1) for the warning.
- **Reduced motion:** skeleton shimmer + card hover honour `prefers-reduced-motion`.
- **Touch targets:** cards + ⋯ ≥ 44px; the ⋯ is always reachable (not hover-only) on touch.

---

## 8. Content guidance

- Primary action label: **"New Presentation"** (title case, the noun users think in). Menu verbs: Open / Rename / Duplicate / Present / Export / Delete.
- Empty state: warm + specific — "Create your first slide deck — a sermon, a song set, or announcements."
- Meta uses **relative time** ("edited 2h ago", "yesterday", "last week") with a title-attribute absolute date.
- Destructive copy always names the item and states reversibility ("You can undo it").

---

## 9. Component & token usage (implementation-ready)

- **Reuse** the shipped operator patterns: card = `--sc-elevated` + 1px `--sc-border` + 12px radius; primary button = `--sc-primary`; confirm dialog = the existing `pmConfirm` (`role="alertdialog"`, focus-trap, Esc); toast = the existing `pmToast` (`role="status"`); skeleton/`aria-busy` = the existing `pmSetBusy` shimmer; the media-cell grid + `.pm-asset` hover/focus are the closest existing analog for the card grid.
- **Thumbnails** use the existing native compositor (`render_deck_slide`) — never an HTML render (ADR-0002/0003). A missing/rendering deck shows the never-blank placeholder.
- All colours are `--sc-*` tokens (pinned by `test_tokens.rs`); no new tokens required.

---

## 10. Backend mapping (what implementation needs — mostly wiring)

The persistence exists; the operator just needs thin commands over `deck_repo` (mirrors how themes are saved/loaded):

| UI action | New Tauri command | Backing (exists) |
|---|---|---|
| Open Library | `deck_list()` → `[{id/name, slides, edited, thumb}]` | `deck_repo::load_all()` |
| New Presentation | `deck_new(name, from)` → opens it | `DeckWorkspace` + `deck_repo::save_all` |
| Open a card | `deck_open(id)` | load one row |
| Rename | `deck_rename(id, name)` | (needs a **stable deck id** — see risk) |
| Duplicate | `deck_duplicate(id)` | clone `SlideDeck` |
| Delete (+undo) | `deck_delete(id)` | remove row; undo restores |
| Save | autosave on edit | `deck_repo::save_all` |

**Risk (Verified, ADR-0020):** the deck library is currently **keyed by name**, so a rename is a new key. Implementation should add a **stable deck id** (uuid) before rename/duplicate ship, else renames orphan history. Flagged for the Architect/Backend.

---

## 11. Figma references

- **`547:124`** — "SelahCue — Presentations (Library + New) · Design 2.0" (the library: top bar, search/sort, New tile, 7 cards).
- **`552:124`** — "SelahCue — Presentations · Create & Manage · Design 2.0" (① New Presentation dialog, ② Empty state, ③ card ⋯ menu + delete confirm).
- Follow-up frame (not yet drawn): Loading (skeleton) · Error banner · Search-no-results · List view · the editor breadcrumb/deck-switcher.

---

## 12. Open decisions (for the /build gate)

1. **Presentation vs Service Plan surfacing** — is the landing "Presentations" (decks) or "Plan / Library" (plans that contain decks)? This spec designs the **deck library**; the plan browser is a sibling. Recommend shipping the deck library first (foundation exists), plan-link second.
2. **Stable deck id** before rename/duplicate (§10 risk).
3. **Templates** — deferred (shown as an honest disabled option).
